import time

class Detector:
    def __init__(self, manager): self.manager=manager
    def predict(self,frame,settings,size=None,tracking=False):
        start=time.perf_counter()
        with self.manager.lock:
            if self.manager.model is None: raise ValueError('Load a model before starting detection.')
            # ByteTrack receives lower-score detections for its second association pass.
            result=self.manager.model.predict(frame,imgsz=size or settings.image_size,
                conf=.1 if tracking else settings.confidence,iou=settings.iou,
                device=settings.device,verbose=False,max_det=300)[0]
        return result,(time.perf_counter()-start)*1000
    @staticmethod
    def image_detections(result):
        h,w=result.orig_shape
        return [{'id':i+1,'class_id':int(c),'class_name':result.names[int(c)],'confidence':float(conf),
                 'box':[float(x1/w),float(y1/h),float(x2/w),float(y2/h)],
                 'center':[(float(x1+x2)/2)/w,(float(y1+y2)/2)/h]}
                for i,(x1,y1,x2,y2,conf,c) in enumerate(result.boxes.data.cpu().numpy())]
