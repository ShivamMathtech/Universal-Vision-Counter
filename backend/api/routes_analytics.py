import csv
import io
import json
import time
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import StreamingResponse,FileResponse
from pydantic import BaseModel
from typing import Literal
from backend.config import LineConfig,ZoneConfig,Settings,OUTPUTS
router=APIRouter(prefix='/api',tags=['Analytics and settings'])
@router.get('/stats')
def stats(request:Request): return request.app.state.service.stats()
@router.get('/counts')
def counts(request:Request):
    data=request.app.state.service.stats()
    return {k:data.get(k) for k in ('total_unique','current_total','classes','current_classes','entered','exited','currently_inside','zones')}
@router.get('/history')
def history(request:Request): return request.app.state.service.history.sessions()
@router.get('/settings')
def settings(request:Request): return request.app.state.service.settings
@router.put('/settings')
def save_settings(body:Settings,request:Request): return request.app.state.service.save_settings(body)
@router.get('/counting')
def geometry(request:Request):
    s=request.app.state.service;return {'line':s.line,'zones':s.zones}
@router.post('/counting/line')
def line(body:LineConfig,request:Request): return request.app.state.service.geometry(line=[(p.x,p.y) for p in body.points])
@router.delete('/counting/line')
def clear_line(request:Request): return request.app.state.service.geometry(line=[])
class Zones(BaseModel):
    zones:list[ZoneConfig]
@router.post('/counting/zone')
def zones(body:Zones,request:Request):
    if len(body.zones)>10: raise ValueError('A maximum of ten zones is supported.')
    if len({z.name for z in body.zones})!=len(body.zones): raise ValueError('Zone names must be unique.')
    return request.app.state.service.geometry(zones=[{'name':z.name,'points':[(p.x,p.y) for p in z.points]} for z in body.zones])
@router.post('/snapshot')
def snapshot(request:Request):
    s=request.app.state.service
    if s.image_result: return {'url':s.image_result['image_url']}
    with s.pipeline.lock: jpeg=s.pipeline.jpeg
    if jpeg is None: raise ValueError('Start a stream before taking a snapshot.')
    path=OUTPUTS/f'snapshot-{s.pipeline.sid}-{time.time_ns()}.jpg'; path.write_bytes(jpeg)
    return {'url':f'/api/files/{path.name}'}
class Recording(BaseModel):
    enabled:bool
@router.post('/record')
def record(body:Recording,request:Request):
    name=request.app.state.service.pipeline.record(body.enabled)
    return {'file':name,'url':f'/api/files/{name}' if name and not body.enabled else None}
@router.get('/export/{sid}.{kind}')
def export(sid:str,kind:str,request:Request):
    h=request.app.state.service.history
    sessions=h.rows('SELECT * FROM sessions WHERE id=?',(sid,))
    if not sessions: raise HTTPException(404,'Session not found.')
    if kind not in ('csv','json'): raise HTTPException(400,'Use csv or json.')
    def csv_stream():
        buffer=io.StringIO(); writer=csv.writer(buffer)
        keys=['timestamp','source_time','class','track_id','confidence','x','y','x1','y1','x2','y2']
        writer.writerow(keys);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
        for row in h.iter_detections(sid):
            values=[row[k] for k in keys]
            values=["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values]
            writer.writerow(values);yield buffer.getvalue();buffer.seek(0);buffer.truncate(0)
    def json_stream():
        session=sessions[0];session['summary']=json.loads(session['summary']) if session['summary'] else None
        yield '{"session":'+json.dumps(session)+',"detections":['
        first=True
        for row in h.iter_detections(sid):
            yield ('' if first else ',')+json.dumps(row);first=False
        yield '],"count_events":['
        last=0;first=True
        while True:
            rows=h.rows('SELECT * FROM count_events WHERE session=? AND id>? ORDER BY id LIMIT 500',(sid,last))
            if not rows: break
            for row in rows: yield ('' if first else ',')+json.dumps(row);first=False
            last=rows[-1]['id']
        yield ']}'
    return StreamingResponse(csv_stream() if kind=='csv' else json_stream(),media_type='text/csv' if kind=='csv' else 'application/json',
                             headers={'Content-Disposition':f'attachment; filename="session-{sid}.{kind}"'})
class Overlays(BaseModel):
    boxes:bool=True
    track_ids:bool=True
    show_confidence:bool=True
    trajectories:bool=False
    centers:bool=False
@router.put('/overlays')
def overlays(body:Overlays,request:Request):
    s=request.app.state.service
    with s.lock,s.pipeline.lock:
        for key,value in body.model_dump().items():
            setattr(s.settings,key,value);setattr(s.pipeline.settings,key,value)
        s.history.set('settings',s.settings.model_dump())
        s.refresh_image_render()
        return s.settings
class Theme(BaseModel):
    theme:Literal['dark','light']
@router.put('/theme')
def theme(body:Theme,request:Request):
    s=request.app.state.service
    with s.lock:
        s.settings.theme=body.theme
        s.history.set('settings',s.settings.model_dump())
        return s.settings
