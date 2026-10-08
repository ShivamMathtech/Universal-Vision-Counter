import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI,Request,WebSocket,WebSocketDisconnect,HTTPException
from fastapi.responses import FileResponse,JSONResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.config import ROOT,OUTPUTS,UPLOADS
from backend.service import AppService
from backend.utils.logger import setup_logging
from backend.api import routes_detection,routes_video,routes_camera,routes_models,routes_analytics
from backend.api.common import safe_file
setup_logging()

def allowed_origin(origin):
    try:
        url=urlparse(origin)
        return url.scheme in ('http','https') and url.hostname in ('127.0.0.1','localhost','testserver') and url.port in (None,8000,5173)
    except ValueError: return False

@asynccontextmanager
async def lifespan(app):
    app.state.service=AppService()
    yield
    await asyncio.to_thread(app.state.service.stop)

app=FastAPI(title='Universal Vision Counter',version='1.0.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
@app.middleware('http')
async def local_security(request:Request,call_next):
    origin=request.headers.get('origin')
    if origin and not allowed_origin(origin): return JSONResponse({'detail':'Cross-origin access is disabled.'},status_code=403)
    if request.method in ('POST','PUT','DELETE','PATCH') and request.headers.get('sec-fetch-site')=='cross-site':
        return JSONResponse({'detail':'Cross-site changes are disabled.'},status_code=403)
    length=request.headers.get('content-length')
    if length:
        try:
            if int(length)>1024*1024*1024+1024*1024: return JSONResponse({'detail':'Upload exceeds 1 GB.'},status_code=413)
        except ValueError: return JSONResponse({'detail':'Invalid content length.'},status_code=400)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    return response
@app.exception_handler(ValueError)
async def invalid(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)
@app.exception_handler(Exception)
async def unexpected(request,exc):
    logging.exception('Request failed')
    return JSONResponse({'detail':f'Operation failed: {str(exc)[:400]}'},status_code=500)
for router in (routes_detection.router,routes_video.router,routes_camera.router,routes_models.router,routes_analytics.router): app.include_router(router)
@app.get('/api/health')
def health(request:Request):
    return {'status':'online','model':request.app.state.service.manager.info(),'version':'1.0.0','scope':'local workstation'}
@app.get('/api/stream')
async def stream(request:Request):
    async def frames():
        previous=None
        while not await request.is_disconnected():
            pipeline=request.app.state.service.pipeline
            with pipeline.lock: jpg=pipeline.jpeg; key=(pipeline.sid,pipeline.jpeg_seq)
            if jpg and key!=previous:
                previous=key
                yield b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpg)).encode()+b'\r\n\r\n'+jpg+b'\r\n'
            await asyncio.sleep(.02)
    return StreamingResponse(frames(),media_type='multipart/x-mixed-replace; boundary=frame',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
@app.websocket('/api/ws')
async def websocket(ws:WebSocket):
    origin=ws.headers.get('origin')
    if origin and not allowed_origin(origin): await ws.close(code=1008);return
    await ws.accept()
    try:
        while True:
            await ws.send_json(ws.app.state.service.stats())
            await asyncio.sleep(.3)
    except (WebSocketDisconnect,RuntimeError): pass
@app.get('/api/files/{name}')
def output(name:str):
    path=safe_file(OUTPUTS,name)
    return FileResponse(path,filename=name,content_disposition_type='inline' if path.suffix=='.jpg' else 'attachment')
@app.get('/api/media/{name}')
def media(name:str): return FileResponse(safe_file(UPLOADS,name))
dist=ROOT/'frontend'/'dist'
if dist.is_dir():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path:str):
        if path.startswith('api/'): raise HTTPException(404,'Endpoint not found.')
        return FileResponse(dist/'index.html')
else:
    @app.get('/')
    def root(): return {'message':'Run npm install && npm run build, then restart the backend; or use npm run dev on port 5173.','docs':'/docs'}
