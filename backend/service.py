import json
import logging
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
import cv2
from backend.config import DATA, MODELS, OUTPUTS, UPLOADS, Settings
from backend.analytics.history import History
from backend.models.model_manager import ModelManager
from backend.vision.detector import Detector
from backend.vision.counter import ObjectCounter, inside_polygon
from backend.vision.frame_pipeline import FramePipeline
from backend.vision.processor import annotate
from backend.vision.tracker import ByteTrackAdapter

class AppService:
    def __init__(self):
        self.lock=threading.RLock()
        self.history=History(DATA/'visioncounter.sqlite3')
        self.settings=Settings(**self.history.get('settings',{}))
        self.line=self.history.get('line',None)
        self.zones=self.history.get('zones',[])
        self.manager=ModelManager()
        self.pipeline=self.new_pipeline()
        self.image_result=None
        self.job={'status':'idle','progress':0}
    def new_pipeline(self):
        return FramePipeline(self.manager,self.history,self.settings.model_copy(),self.line,self.zones)
    def idle_required(self):
        if self.pipeline.status in ('running','paused'):
            raise ValueError('Stop the current analysis before changing the source, model, or performance settings.')
        if self.job['status']=='running': raise ValueError('Wait for the annotated-video export to finish.')
    def load_model(self,name):
        with self.lock:
            self.idle_required()
            self.pipeline.stop()
            info=self.manager.load(name,self.settings)
            self.settings.model=name; self.history.set('settings',self.settings.model_dump())
            return info
    def ensure_model(self):
        if self.manager.name!=self.settings.model or self.manager.model is None:
            self.manager.load(self.settings.model,self.settings)
    def start(self,source,kind,offset=0):
        with self.lock:
            self.idle_required(); self.pipeline.stop(); self.ensure_model()
            self.image_result=None; self.pipeline=self.new_pipeline()
            self.pipeline.start(source,kind,offset)
            return self.pipeline.snapshot()
    def stop(self):
        with self.lock: self.pipeline.stop(); return self.stats()
    def stats(self):
        import psutil
        from backend.utils.performance import process_memory_gb
        result=dict(self.image_result or self.pipeline.snapshot())
        memory=process_memory_gb()
        result.update(cpu=round(psutil.cpu_percent(),1),ram_gb=round(memory,2) if memory is not None else None,system_ram_percent=psutil.virtual_memory().percent)
        return result
    def image(self,path):
        with self.lock:
            self.idle_required(); self.pipeline.stop(); self.ensure_model()
            from PIL import Image
            try:
                with Image.open(path) as header:
                    if header.width*header.height>25_000_000: raise ValueError('Use an image under 25 megapixels.')
                    header.verify()
            except OSError as exc:
                raise ValueError('This image is corrupt or unsupported.') from exc
            frame=cv2.imread(str(path))
            if frame is None: raise ValueError('This image is corrupt or unsupported.')
            if frame.shape[0]*frame.shape[1]>25_000_000: raise ValueError('Use an image under 25 megapixels.')
            result,ms=Detector(self.manager).predict(frame,self.settings)
            detections=Detector.image_detections(result)
            sid=uuid.uuid4().hex; self.history.start(sid,path.name)
            counter=ObjectCounter(self.history,sid,self.line,self.zones,self.settings.initial_inside)
            counts=counter.update(detections,time.time(),0)
            file=OUTPUTS/f'image-{sid}.jpg'
            if not cv2.imwrite(str(file),annotate(frame,detections,self.settings,self.line,self.zones)):
                raise ValueError('Could not save the annotated image.')
            self.image_result={**self.pipeline.snapshot(),**counts,'session_id':sid,'status':'completed','source_kind':'image',
                'image_url':f'/api/files/{file.name}','original_url':f'/api/media/{path.name}','inference_ms':round(ms,1),
                'model':self.manager.name,'confidence':sum(d['confidence'] for d in detections)/len(detections) if detections else 0,
                'detections':detections,'series':[],'duration':0,'position':0,'error':None}
            self.history.finish(sid,self.image_result)
            return self.image_result
    def save_settings(self,data):
        with self.lock:
            self.idle_required()
            changed=(data.model!=self.settings.model or data.device!=self.settings.device or data.cpu_threads!=self.settings.cpu_threads)
            self.settings=data
            self.history.set('settings',data.model_dump())
            if changed: self.manager.unload()
            return data.model_dump()
    def geometry(self,line=None,zones=None):
        with self.lock:
            if self.job['status']=='running': raise ValueError('Wait for export to finish before editing regions.')
            if line is not None: self.line=line or None; self.history.set('line',self.line)
            if zones is not None: self.zones=zones;self.history.set('zones',zones)
            with self.pipeline.lock:
                self.pipeline.line,self.pipeline.zones=self.line,self.zones
                if self.pipeline.counter: self.pipeline.counter.configure(self.line,self.zones)
            self.refresh_image_render()
            return {'line':self.line,'zones':self.zones}
    def refresh_image_render(self):
        if not self.image_result: return
        result=self.image_result
        frame=cv2.imread(str(UPLOADS/Path(result['original_url']).name))
        if frame is None: return
        output=OUTPUTS/f"image-{result['session_id']}.jpg"
        cv2.imwrite(str(output),annotate(frame,result['detections'],self.settings,self.line,self.zones))
        result['image_url']=f'/api/files/{output.name}?v={time.time_ns()}'
        result['line']=self.line;result['zone_config']=self.zones
        result['zones']={z['name']:sum(inside_polygon(d['center'],z['points']) for d in result['detections']) for z in self.zones}
        self.history.finish(result['session_id'],result)
    def export_video(self,path):
        with self.lock:
            self.idle_required(); self.pipeline.stop(); self.ensure_model()
            self.job={'status':'running','progress':0,'error':None,'file':None}
            thread=threading.Thread(target=self._export,args=(path,self.settings.model_copy(),self.line,list(self.zones)),daemon=True)
            thread.start()
            return dict(self.job)
    def _export(self,path,settings,line,zones):
        cap=cv2.VideoCapture(str(path)); writer=None; sid=uuid.uuid4().hex
        try:
            if not cap.isOpened(): raise ValueError('Cannot open video for export.')
            fps=cap.get(cv2.CAP_PROP_FPS); fps=fps if 1<=fps<=240 else 25
            n=max(1,int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            tracker=ByteTrackAdapter(settings); detector=Detector(self.manager)
            self.history.start(sid,'Full export: '+path.name)
            counter=ObjectCounter(self.history,sid,line,zones,settings.initial_inside)
            out=OUTPUTS/f'annotated-{sid}.avi'
            i=0; detections=[]; interval=max(1,round(fps/settings.inference_fps),settings.frame_skip+1)
            while True:
                ok,frame=cap.read()
                if not ok: break
                if writer is None:
                    h,w=frame.shape[:2]; writer=cv2.VideoWriter(str(out),cv2.VideoWriter_fourcc(*'MJPG'),fps,(w,h))
                    if not writer.isOpened(): raise ValueError('MJPG video encoder unavailable.')
                if i%interval==0:
                    result,_=detector.predict(frame,settings,tracking=True)
                    detections=tracker.update(result,frame)
                    counter.update(detections,time.time(),i/fps)
                writer.write(annotate(frame,detections,settings,line,zones))
                i+=1;self.job['progress']=round(min(99,i/n*100),1)
            if i==0: raise ValueError('Video has no decodable frames.')
            writer.release();writer=None
            summary=counter.snapshot(); self.history.finish(sid,summary)
            self.job.update(status='completed',progress=100,file=out.name,session_id=sid)
        except Exception as exc:
            logging.exception('Video export failed')
            self.job.update(status='error',error=str(exc))
        finally:
            cap.release()
            if writer is not None: writer.release()
