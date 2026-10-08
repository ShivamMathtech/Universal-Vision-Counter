import torch
from ultralytics.nn.tasks import DetectionModel
from backend.models.model_manager import ModelManager
from backend.config import Settings

def test_custom_detection_checkpoint_reads_its_own_classes(tmp_path,monkeypatch):
    import backend.models.model_manager as module
    monkeypatch.setattr(module,'MODELS',tmp_path)
    network=DetectionModel('yolo11n.yaml',nc=3,verbose=False)
    network.names={0:'apple',1:'orange',2:'banana'}
    torch.save({'model':network},tmp_path/'best.pt')
    manager=ModelManager();info=manager.load('best.pt',Settings())
    assert info['classes']=={0:'apple',1:'orange',2:'banana'}
    manager.unload();assert not manager.info()['loaded']
