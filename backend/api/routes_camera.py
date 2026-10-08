import cv2
import os
from fastapi import APIRouter,Request
from pydantic import BaseModel,Field
router=APIRouter(prefix='/api/camera',tags=['Camera'])
class CameraStart(BaseModel):
    index:int=Field(default=0,ge=0,le=16)
@router.get('')
def cameras(request:Request):
    request.app.state.service.idle_required()
    found=[]
    for index in range(4):
        cap=cv2.VideoCapture(index,cv2.CAP_DSHOW if os.name=='nt' else cv2.CAP_ANY)
        if cap.isOpened(): found.append({'index':index,'name':f'Camera {index}'})
        cap.release()
    return {'cameras':found}
@router.post('/start')
def start(body:CameraStart,request:Request): return request.app.state.service.start(body.index,'camera')
@router.post('/stop')
def stop(request:Request): return request.app.state.service.stop()
