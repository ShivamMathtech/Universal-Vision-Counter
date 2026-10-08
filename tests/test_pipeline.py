import time
import numpy as np
import cv2
from types import SimpleNamespace
from backend.config import Settings
from backend.analytics.history import History
from backend.vision.frame_pipeline import FramePipeline
from backend.vision.detector import Detector
from backend.vision.tracker import ByteTrackAdapter

def create_clip(path,frames=36,fps=24):
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(320,240))
    assert writer.isOpened()
    for i in range(frames):
        frame=np.zeros((240,320,3),np.uint8);cv2.rectangle(frame,(i*2,60),(i*2+35,140),(255,255,255),-1);writer.write(frame)
    writer.release()

def test_slow_inference_does_not_block_rendering_and_queue_bounded(tmp_path,monkeypatch):
    path=tmp_path/'video.avi';create_clip(path)
    def slow(self,frame,settings,size=None,tracking=False):time.sleep(.25);return None,250
    monkeypatch.setattr(Detector,'predict',slow)
    monkeypatch.setattr(ByteTrackAdapter,'update',lambda self,r,f:[])
    manager=SimpleNamespace(model=object(),name='slow-test')
    p=FramePipeline(manager,History(tmp_path/'test.db'),Settings(adaptive=False));p.start(str(path),'video')
    time.sleep(.9)
    stats=p.snapshot()
    assert stats['display_fps']>15
    assert stats['inference_fps']<6
    assert stats['queue_size']<=2
    assert stats['dropped_frames']>0
    assert p.jpeg is not None
    p.stop()
    assert not any(t.is_alive() for t in p.threads)

def test_pause_keeps_video_position_stable(tmp_path,monkeypatch):
    path=tmp_path/'pause.avi';create_clip(path,120)
    monkeypatch.setattr(Detector,'predict',lambda *a,**kw:(None,1))
    monkeypatch.setattr(ByteTrackAdapter,'update',lambda *a:[])
    p=FramePipeline(SimpleNamespace(model=object(),name='test'),History(':memory:'),Settings());p.start(str(path),'video')
    time.sleep(.15);p.pause(True);time.sleep(.08);pos=p.position;time.sleep(.2)
    assert p.position==pos
    p.pause(False);time.sleep(.15);assert p.position>pos;p.stop()
