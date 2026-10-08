from fastapi import APIRouter,Request,UploadFile,File
from starlette.concurrency import run_in_threadpool
from backend.config import UPLOADS
from backend.api.common import IMAGE_EXT,save_upload
router=APIRouter(prefix='/api/detection',tags=['Detection'])
@router.post('/image')
async def image(request:Request,file:UploadFile=File(...)):
    path=await save_upload(file,UPLOADS,IMAGE_EXT,20*1024*1024)
    try: return await run_in_threadpool(request.app.state.service.image,path)
    except Exception:
        path.unlink(missing_ok=True);raise
