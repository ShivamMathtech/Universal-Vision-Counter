"""Independent capture, inference and rendering workers with bounded latest-frame queues."""
import logging
import queue
import threading
import time
import uuid
from collections import deque
import cv2
import psutil
from backend.config import OUTPUTS
from backend.vision.detector import Detector
from backend.vision.tracker import ByteTrackAdapter
from backend.vision.counter import ObjectCounter
from backend.vision.processor import annotate
from backend.vision.preprocessing import display_frame
from backend.utils.performance import Rate, AdaptiveController, process_memory_gb

log=logging.getLogger(__name__)

class FramePipeline:
    def __init__(self,manager,history,settings,line=None,zones=None):
        self.manager,self.history,self.settings=manager,history,settings
        self.line,self.zones=line,zones or []
        self.lock=threading.RLock()
        self.record_lock=threading.Lock()
        self.stop_event=threading.Event(); self.paused=threading.Event(); self.eof=threading.Event()
        self.queue=queue.Queue(maxsize=settings.queue_size)
        self.threads=[]; self.latest=None; self.result=[]; self.result_time=0
        self.jpeg=None; self.jpeg_seq=0; self.status='idle'; self.error=None
        self.sid=None; self.counter=None; self.cap=None; self.source=None; self.kind=None
        self.duration=0.; self.position=0.; self.speed=1.; self.offset=0.
        self.reader_rate=Rate(); self.render_rate=Rate(); self.infer_rate=Rate()
        self.timings=deque(maxlen=60); self.series=deque(maxlen=180)
        self.skipped=0; self.dropped=0; self.latency=0.; self.cpu=0.; self.ram=0.
        self.writer=None; self.record_path=None; self.last_record_path=None
        self.adaptive=AdaptiveController(settings.image_size,settings.inference_fps)
        self.last_sample=0.; self.last_sequence=-1
    def start(self,source,kind,offset=0):
        if self.manager.model is None: raise ValueError('Load a model in Settings first.')
        self.cap=cv2.VideoCapture(source,cv2.CAP_DSHOW if kind=='camera' and __import__('os').name=='nt' else cv2.CAP_ANY)
        if not self.cap.isOpened():
            self.cap.release(); raise ValueError('Camera unavailable or video cannot be decoded. Check its format and camera permissions.')
        if kind=='camera':
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,self.settings.camera_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,self.settings.camera_height)
            self.cap.set(cv2.CAP_PROP_FPS,self.settings.camera_fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
        fps=self.cap.get(cv2.CAP_PROP_FPS)
        self.source_fps=fps if 1<=fps<=240 else self.settings.camera_fps if kind=='camera' else 25
        count=self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.duration=count/self.source_fps if kind=='video' and count>0 else 0
        if offset and kind=='video': self.cap.set(cv2.CAP_PROP_POS_MSEC,offset*1000)
        ok,first=self.cap.read()
        if not ok or first is None:
            self.cap.release(); raise ValueError('Input opened, but no valid frames were found.')
        self.first=display_frame(first)
        self.source,self.kind,self.offset=source,kind,offset
        self.sid=uuid.uuid4().hex
        self.counter=ObjectCounter(self.history,self.sid,self.line,self.zones,self.settings.initial_inside)
        self.history.start(self.sid,str(source) if kind=='camera' else __import__('pathlib').Path(source).name)
        self.status='running'
        self.tracker=ByteTrackAdapter(self.settings)
        for target,name in ((self._read,'reader'),(self._infer,'inference'),(self._render,'renderer')):
            t=threading.Thread(target=target,name=f'vision-{name}',daemon=True);self.threads.append(t); t.start()
        log.info('Session started: %s / %s',self.sid,kind)
        return self.sid
    def _fail(self,message):
        log.exception(message)
        with self.lock: self.error=message; self.status='error'
        self.stop_event.set()
    def _read(self):
        index=0; first=True
        try:
            while not self.stop_event.is_set():
                if self.paused.is_set(): self.stop_event.wait(.02); continue
                start=time.monotonic()
                if first: frame=self.first; first=False
                else:
                    ok,frame=self.cap.read()
                    if not ok or frame is None:
                        if self.kind=='camera': raise RuntimeError('Camera stopped returning frames. Reconnect it and start again.')
                        break
                    frame=display_frame(frame)
                source_time=self.offset+index/self.source_fps
                packet=(index,start,source_time,frame)
                with self.lock: self.latest=packet; self.position=source_time
                self.reader_rate.tick()
                if self.settings.frame_skip==0 or index%(self.settings.frame_skip+1)==0:
                    try: self.queue.put_nowait(packet)
                    except queue.Full:
                        try: self.queue.get_nowait(); self.dropped+=1
                        except queue.Empty: pass
                        try: self.queue.put_nowait(packet)
                        except queue.Full: self.dropped+=1
                else: self.skipped+=1
                index+=1
                period=1/(self.source_fps*self.speed) if self.kind=='video' else 1/self.settings.camera_fps
                self.stop_event.wait(max(0,period-(time.monotonic()-start)))
        except Exception as exc: self._fail(str(exc))
        finally:
            self.eof.set()
            if self.cap is not None: self.cap.release()
    def _infer(self):
        detector=Detector(self.manager); next_at=0
        try:
            while not self.stop_event.is_set():
                if self.paused.is_set(): self.stop_event.wait(.02); continue
                wait=next_at-time.monotonic()
                if wait>0: self.stop_event.wait(min(wait,.03)); continue
                try: packet=self.queue.get(timeout=.1)
                except queue.Empty:
                    if self.eof.is_set(): break
                    continue
                while True:
                    try: packet=self.queue.get_nowait(); self.dropped+=1
                    except queue.Empty: break
                _,captured,position,frame=packet
                begin=time.monotonic()
                result,ms=detector.predict(frame,self.settings,self.adaptive.size,tracking=True)
                detections=self.tracker.update(result,frame)
                with self.lock:
                    self.counter.update(detections,time.time(),position)
                    self.result=detections; self.result_time=time.monotonic()
                    self.timings.append(ms); self.latency=(time.monotonic()-captured)*1000
                self.infer_rate.tick()
                next_at=begin+1/self.adaptive.fps
            if self.eof.is_set() and not self.stop_event.is_set(): self.status='completed'
        except Exception as exc: self._fail(f'Inference failed: {exc}')
        finally: self.stop_event.set()
    def _render_one(self):
        with self.lock:
            packet=self.latest; detections=self.result
            result_time=self.result_time
        if packet is None: return
        index,_,_,frame=packet
        # Stale boxes disappear rather than following an unrelated scene indefinitely.
        if time.monotonic()-result_time>max(2,2/self.adaptive.fps): detections=[]
        image=annotate(frame,detections,self.settings,self.line,self.zones)
        ok,jpeg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,82])
        if ok:
            with self.lock: self.jpeg=jpeg.tobytes(); self.jpeg_seq+=1
            self.render_rate.tick()
        with self.record_lock:
            if self.record_path and self.writer is None:
                h,w=image.shape[:2]
                self.writer=cv2.VideoWriter(str(self.record_path),cv2.VideoWriter_fourcc(*'MJPG'),self.settings.display_fps,(w,h))
                if not self.writer.isOpened():
                    self.writer.release();self.writer=None;self.record_path=None
                    raise RuntimeError('Recording codec MJPG is unavailable.')
            if self.writer is not None: self.writer.write(image)
        self.last_sequence=index
    def _render(self):
        try:
            while not self.stop_event.is_set():
                start=time.monotonic()
                if not self.paused.is_set(): self._render_one()
                if start-self.last_sample>=1:
                    self.cpu=psutil.cpu_percent(); self.ram=process_memory_gb()
                    if self.settings.adaptive: self.adaptive.update(self.cpu,start)
                    snapshot=self.snapshot()
                    sample={'time':time.time(),'current':snapshot.get('current_total',0),'unique':snapshot.get('total_unique',0)}
                    with self.lock: self.series.append(sample)
                    self.history.execute('INSERT INTO analytics(session,timestamp,payload) VALUES(?,?,?)',(self.sid,time.time(),__import__('json').dumps(snapshot)))
                    self.last_sample=start
                self.stop_event.wait(max(.001,1/self.settings.display_fps-(time.monotonic()-start)))
            self._render_one()
        except Exception as exc: self._fail(f'Rendering failed: {exc}')
        finally:
            self.record(False)
            # The inference worker is the only writer of counters; stop() joins it before final summary as well.
            if self.sid: self.history.finish(self.sid,self.snapshot())
    def stop(self):
        self.stop_event.set()
        for t in self.threads:
            if t is not threading.current_thread(): t.join(timeout=30)
        if any(t.is_alive() for t in self.threads): raise RuntimeError('A worker is still shutting down; wait before restarting.')
        if self.status not in ('error','completed'): self.status='stopped'
        if self.sid: self.history.finish(self.sid,self.snapshot())
    def pause(self,paused):
        if self.status not in ('running','paused'): raise ValueError('No running analysis to pause or resume.')
        if paused: self.paused.set(); self.status='paused'
        else: self.paused.clear(); self.status='running'
    def record(self,enabled):
        with self.record_lock:
            if enabled:
                if self.status not in ('running','paused'): raise ValueError('Start a camera or video before recording.')
                if self.record_path is None: self.record_path=OUTPUTS/f'recording-{self.sid}-{int(time.time())}.avi'
                return self.record_path.name
            if self.writer is not None: self.writer.release(); self.writer=None
            if self.record_path: self.last_record_path=self.record_path.name
            self.record_path=None
            return self.last_record_path
    def snapshot(self):
        with self.lock:
            counts=self.counter.snapshot() if self.counter else {'total_unique':0,'current_total':0,'classes':{},'current_classes':{},'recent':[],'zones':{},'entered':0,'exited':0,'currently_inside':0,'net_flow':0}
            return {**counts,'session_id':self.sid,'status':self.status,'error':self.error,
                'source_kind':self.kind,'position':round(self.position,2),'duration':self.duration,'speed':self.speed,
                'video_fps':self.reader_rate.value(),'display_fps':self.render_rate.value(),'inference_fps':self.infer_rate.value(),
                'inference_ms':round(sum(self.timings)/len(self.timings),1) if self.timings else 0,
                'latency_ms':round(self.latency,1),'cpu':round(self.cpu,1),'ram_gb':round(self.ram,2) if self.ram is not None else None,
                'system_ram_percent':psutil.virtual_memory().percent,'dropped_frames':self.dropped,'skipped_frames':self.skipped,'queue_size':self.queue.qsize(),
                'image_size':self.adaptive.size,'target_inference_fps':self.adaptive.fps,
                'model':self.manager.name,'backend':self.settings.device,'tracker':'ByteTrack','recording':self.record_path is not None,
                'recording_file':self.last_record_path,'confidence':round(sum(d['confidence'] for d in self.result)/len(self.result),3) if self.result else 0,
                'series':list(self.series),'detections':self.result,'line':self.line,'zone_config':self.zones}
