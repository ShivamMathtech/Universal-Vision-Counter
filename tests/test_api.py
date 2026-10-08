from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import MODELS
@pytest.fixture
def client(tmp_path,monkeypatch):
    import backend.service as service
    monkeypatch.setattr(service,'DATA',tmp_path)
    with TestClient(app,raise_server_exceptions=False) as c: yield c

def test_health_settings_and_validation(client):
    assert client.get('/api/health').json()['status']=='online'
    settings=client.get('/api/settings').json();assert settings['device']=='cpu'
    settings['image_size']=416
    assert client.put('/api/settings',json=settings).status_code==200
    settings['image_size']=999
    assert client.put('/api/settings',json=settings).status_code==422
    assert client.post('/api/counting/line',json={'points':[{'x':.2,'y':.5},{'x':.8,'y':.5}]}).status_code==200

def test_missing_model_and_invalid_upload_are_clear_errors(client):
    assert client.post('/api/models/load',json={'name':'missing.pt'}).status_code==400
    assert client.post('/api/video/upload',files={'file':('script.exe',b'bad')}).status_code==415
    assert client.get('/api/export/missing.csv').status_code==404

def test_cross_origin_write_denied(client):
    assert client.post('/api/video/stop',headers={'Origin':'https://evil.example'}).status_code==403

def test_websocket_metadata(client):
    with client.websocket_connect('/api/ws') as ws:
        stats=ws.receive_json();assert stats['total_unique']==0 and stats['status']=='idle'

@pytest.mark.integration
def test_real_image_detection_custom_classes_export_history(client):
    if not (MODELS/'yolo11n.pt').exists():pytest.skip('Run scripts/download_model.py first')
    loaded=client.post('/api/models/load',json={'name':'yolo11n.pt'})
    assert loaded.status_code==200,loaded.text
    assert len(loaded.json()['classes'])==80
    with open(Path(__file__).parent/'assets/bus.jpg','rb') as f:
        response=client.post('/api/detection/image',files={'file':('bus.jpg',f,'image/jpeg')})
    assert response.status_code==200,response.text
    data=response.json();assert data['total_unique']>=3
    assert data['classes'].get('person',0)>=1
    assert client.get(data['image_url']).headers['content-type']=='image/jpeg'
    sid=data['session_id'];export=client.get(f'/api/export/{sid}.json').json()
    assert len(export['detections'])==data['total_unique']
    assert 'track_id' in client.get(f'/api/export/{sid}.csv').text
    assert len(client.get('/api/history').json())==1

@pytest.mark.integration
def test_real_video_stream_pause_seek_record_export(client,tmp_path):
    import cv2
    import time
    import numpy as np
    from backend.config import OUTPUTS
    if not (MODELS/'yolo11n.pt').exists():pytest.skip('Model not installed')
    assert client.post('/api/models/load',json={'name':'yolo11n.pt'}).status_code==200
    frame=cv2.imread(str(Path(__file__).parent/'assets/bus.jpg'))
    frame=cv2.resize(frame,(480,640))
    path=tmp_path/'bus.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),24,(480,640))
    for i in range(72):writer.write(frame)
    writer.release()
    with path.open('rb') as f:data=client.post('/api/video/upload',files={'file':('bus.avi',f)}).json()
    response=client.post('/api/video/start',json={'file':data['file']});assert response.status_code==200,response.text
    sid=response.json()['session_id'];time.sleep(.8)
    assert client.post('/api/record',json={'enabled':True}).status_code==200
    time.sleep(.3)
    assert client.post('/api/video/control',json={'action':'pause'}).status_code==200
    stats=client.get('/api/stats').json()
    assert stats['total_unique']>=3
    assert stats['display_fps']>10
    assert client.post('/api/snapshot').status_code==200
    position=stats['position'];time.sleep(.1)
    assert client.get('/api/stats').json()['position']==position
    assert client.post('/api/video/control',json={'action':'resume'}).status_code==200
    recording=client.post('/api/record',json={'enabled':False}).json()
    assert (OUTPUTS/recording['file']).stat().st_size>1000
    sought=client.post('/api/video/control',json={'action':'seek','value':1}).json()
    assert sought['session_id']!=sid
    assert client.post('/api/video/stop').status_code==200
    response=client.post('/api/video/export',json={'file':data['file']});assert response.status_code==200,response.text
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        job=client.get('/api/video/export').json()
        if job['status']!='running':break
        time.sleep(.1)
    assert job['status']=='completed',job
    cap=cv2.VideoCapture(str(OUTPUTS/job['file']))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==72
    cap.release()
