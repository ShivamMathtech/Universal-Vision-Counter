from typing import Literal
from fastapi import APIRouter,Request,UploadFile,File
from pydantic import BaseModel,Field
from backend.api.common import VIDEO_EXT,save_upload,safe_file
from backend.config import UPLOADS
router=APIRouter(prefix='/api/video',tags=['Video'])
class VideoStart(BaseModel):
    file: str
class Control(BaseModel):
    action: Literal['pause','resume','seek','speed']
    value: float=Field(default=0,ge=0,le=10000000)
@router.post('/upload')
async def upload(file:UploadFile=File(...)):
    path=await save_upload(file,UPLOADS,VIDEO_EXT,1024*1024*1024)
    return {'file':path.name,'url':f'/api/media/{path.name}'}
@router.post('/start')
def start(body:VideoStart,request:Request):
    path=safe_file(UPLOADS,body.file)
    if path.suffix not in VIDEO_EXT: raise ValueError('Choose a video file.')
    return request.app.state.service.start(str(path),'video')
@router.post('/stop')
def stop(request:Request): return request.app.state.service.stop()
@router.post('/control')
def control(body:Control,request:Request):
    s=request.app.state.service;p=s.pipeline
    with s.lock:
        if body.action=='pause': p.pause(True)
        elif body.action=='resume': p.pause(False)
        elif body.action=='speed':
            if body.value not in (.5,1,1.5,2): raise ValueError('Speed must be 0.5, 1, 1.5 or 2.')
            p.speed=body.value
        elif body.action=='seek':
            if p.kind!='video': raise ValueError('Seeking is available for uploaded video only.')
            if body.value>=p.duration: raise ValueError('Seek position must be within the video duration.')
            source=p.source;speed=p.speed;p.stop()
            s.start(source,'video',body.value);s.pipeline.speed=speed
        return s.stats()
@router.post('/export')
def export(body:VideoStart,request:Request):
    return request.app.state.service.export_video(safe_file(UPLOADS,body.file))
@router.get('/export')
def progress(request:Request): return request.app.state.service.job
