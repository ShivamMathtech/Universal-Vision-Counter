from types import SimpleNamespace

class ByteTrackAdapter:
    def __init__(self,settings):
        from ultralytics.trackers.byte_tracker import BYTETracker
        self.tracker=BYTETracker(SimpleNamespace(track_high_thresh=settings.confidence,
            track_low_thresh=.1,new_track_thresh=settings.confidence,
            track_buffer=settings.track_buffer,match_thresh=.8,fuse_score=True),frame_rate=30)
        self.tracker.reset()
    def update(self,result,frame):
        rows=self.tracker.update(result.boxes.cpu().numpy(),frame)
        h,w=frame.shape[:2]
        output=[]
        for row in rows:
            x1,y1,x2,y2,tid,conf,cls=row[:7]
            cls=int(cls)
            output.append({'id':int(tid),'class_id':cls,'class_name':result.names[cls],
                'confidence':float(conf),'box':[float(x1/w),float(y1/h),float(x2/w),float(y2/h)],
                'center':[float((x1+x2)/2/w),float((y1+y2)/2/h)]})
        return output
