import json
import time
import zipfile
from fastapi import APIRouter, Request, UploadFile, File
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from backend.config import MODELS
from backend.api.common import save_upload
router=APIRouter(prefix='/api/models',tags=['Models'])
class ModelChoice(BaseModel):
    name: str=Field(min_length=1,max_length=120)
@router.get('')
def models(request:Request):
    s=request.app.state.service
    return {'available':s.manager.available(),'active':s.manager.info(),'selected':s.settings.model}
@router.post('/pretrained')
def pretrained(request:Request):
    s=request.app.state.service
    with s.lock:
        s.idle_required();name=s.manager.download_pretrained();return s.load_model(name)
@router.post('/load')
def load(body:ModelChoice,request:Request): return request.app.state.service.load_model(body.name)
@router.post('/unload')
def unload(request:Request):
    s=request.app.state.service
    with s.lock: s.idle_required();s.pipeline.stop();s.manager.unload();return {'unloaded':True}
@router.post('/upload')
async def upload(request:Request,file:UploadFile=File(...)):
    s=request.app.state.service
    s.idle_required()
    path=await save_upload(file,MODELS,{'.pt'},100*1024*1024)
    try:
        if not zipfile.is_zipfile(path): raise ValueError('Use a current torch ZIP-format .pt checkpoint.')
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>600*1024*1024: raise ValueError('Expanded model is too large.')
        info=await run_in_threadpool(s.load_model,path.name)
        s.history.execute('INSERT INTO uploaded_models VALUES(?,?,?)',(path.name,time.time(),json.dumps(info['classes'])))
        return info
    except Exception:
        path.unlink(missing_ok=True);raise
