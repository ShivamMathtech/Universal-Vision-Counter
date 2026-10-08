import os
import pickle
from pathlib import Path
import pytest
from backend.models.model_manager import ModelManager
from backend.config import LineConfig,ZoneConfig
from backend.main import allowed_origin

class Malicious:
    def __reduce__(self):
        return (os.system,('touch /tmp/visioncounter_must_never_execute',))

def test_uploaded_pickle_cannot_execute(tmp_path):
    import torch
    path=tmp_path/'evil.pt';marker=Path('/tmp/visioncounter_must_never_execute');marker.unlink(missing_ok=True)
    torch.save({'model':Malicious()},path)
    with pytest.raises(Exception): ModelManager.safe_checkpoint(path)
    assert not marker.exists()

def test_invalid_region_validation():
    with pytest.raises(ValueError): LineConfig(points=[{'x':.5,'y':.5},{'x':.5,'y':.5}])
    with pytest.raises(ValueError): ZoneConfig(name='Flat',points=[{'x':0,'y':0},{'x':.5,'y':.5},{'x':1,'y':1}])

def test_origin_guard():
    assert allowed_origin('http://127.0.0.1:5173')
    assert not allowed_origin('http://evil.example')
    assert not allowed_origin('http://127.0.0.1.evil.example:5173')
