from types import SimpleNamespace
import numpy as np
from ultralytics.engine.results import Boxes
from backend.vision.tracker import ByteTrackAdapter
from backend.config import Settings

def result(x=100,confidence=.9):
    return SimpleNamespace(boxes=Boxes(np.array([[x,100,x+70,200,confidence,0]],dtype=np.float32),(480,640)),names={0:'custom-fruit'})

def test_real_bytetrack_keeps_id_for_100_frames():
    tracker=ByteTrackAdapter(Settings());frame=np.zeros((480,640,3),dtype=np.uint8)
    ids=[]
    for i in range(100):
        tracks=tracker.update(result(x=100+i*.4),frame)
        assert len(tracks)==1
        ids.append(tracks[0]['id'])
    assert len(set(ids))==1
    assert tracks[0]['class_name']=='custom-fruit'

def test_low_confidence_association_preserves_id():
    tracker=ByteTrackAdapter(Settings());frame=np.zeros((480,640,3),dtype=np.uint8)
    first=tracker.update(result(),frame)[0]['id']
    for i in range(5):
        tracks=tracker.update(result(x=101+i,confidence=.2),frame)
        assert tracks[0]['id']==first
