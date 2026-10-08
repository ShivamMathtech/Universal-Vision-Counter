from collections import Counter, deque
import math
from backend.analytics.history import History


def inside_polygon(p, poly):
    x,y=p; inside=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside=not inside
    return inside


def side(p,a,b):
    return ((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))/max(math.dist(a,b),1e-9)


def crosses_segment(p,q,a,b):
    # Both segments must intersect; crossing the infinite extension does not count.
    return side(p,a,b)*side(q,a,b)<0 and side(a,p,q)*side(b,p,q)<=0


class ObjectCounter:
    def __init__(self, history: History, sid: str, line=None, zones=None, initial_inside=0):
        self.history,self.sid=history,sid
        self.line=line
        self.zones=zones or []
        self.initial_inside=initial_inside
        self.active={}
        self.entered=self.exited=0
        self.current={}
        self.zone_counts={}
        self.recent=deque(maxlen=30)
        self.classes={}
        self.total=0
    def configure(self,line,zones):
        self.line,self.zones=line,zones
        import json, time
        self.history.execute('INSERT INTO count_events(session,timestamp,track_id,event,region) VALUES(?,?,?,?,?)',
            (self.sid,time.time(),0,'geometry_reset',json.dumps({'line':line,'zones':zones})))
        self.active.clear()
        self.entered=self.exited=0
    def update(self, detections: list[dict], timestamp: float, source_time: float):
        current=Counter(); zones=Counter(); emitted=[]
        with self.history.lock, self.history.db:
            db=self.history.db
            for d in detections:
                tid=int(d['id']); p=tuple(d['center'])
                old=self.active.get(tid)
                # Class is fixed to the first confirmed classification for unique-count consistency.
                known=db.execute('SELECT class_name FROM tracks WHERE session=? AND id=?',(self.sid,tid)).fetchone()
                name=known[0] if known else d['class_name']
                d['class_name']=name
                current[name]+=1
                if known is None:
                    db.execute('INSERT INTO tracks VALUES(?,?,?,?,?,?,?)',(self.sid,tid,d['class_id'],name,timestamp,timestamp,d['confidence']))
                    self.classes[name]=self.classes.get(name,0)+1
                    self.total+=1
                    self.recent.appendleft({'timestamp':timestamp,'class_name':name,'id':tid,'confidence':d['confidence']})
                    emitted.append((tid,'first_seen',''))
                else:
                    db.execute('UPDATE tracks SET last_seen=?,confidence=? WHERE session=? AND id=?',(timestamp,d['confidence'],self.sid,tid))
                trail=old['trajectory'] if old else deque(maxlen=30)
                trail.append(p)
                significant=old.get('significant') if old else None
                last_cross=old.get('last_cross',-1e9) if old else -1e9
                if self.line:
                    a,b=self.line
                    if abs(side(p,a,b))>.008:
                        if significant and crosses_segment(significant,p,a,b) and timestamp-last_cross>.5:
                            event='in' if side(p,a,b)>0 else 'out'
                            if event=='in': self.entered+=1
                            else: self.exited+=1
                            emitted.append((tid,event,'line'))
                            last_cross=timestamp
                        significant=p
                memberships=set()
                for zone in self.zones:
                    if inside_polygon(p,zone['points']):
                        memberships.add(zone['name']); zones[zone['name']]+=1
                        if not old or zone['name'] not in old['zones']:
                            emitted.append((tid,'zone_enter',zone['name']))
                if old:
                    for z in old['zones']-memberships:
                        emitted.append((tid,'zone_exit',z))
                self.active[tid]={'last_seen':timestamp,'trajectory':trail,'significant':significant,'last_cross':last_cross,'zones':memberships}
                d['trajectory']=list(trail)
                db.execute('INSERT INTO detections(session,timestamp,source_time,track_id,class,confidence,x,y,x1,y1,x2,y2) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (self.sid,timestamp,source_time,tid,name,d['confidence'],*p,*d['box']))
            db.executemany('INSERT INTO count_events(session,timestamp,track_id,event,region) VALUES(?,?,?,?,?)',[(self.sid,timestamp,*e) for e in emitted])
        self.current=dict(current)
        self.zone_counts={z['name']:zones[z['name']] for z in self.zones}
        # Keep trajectories only for recent tracks; durable ID membership remains in SQLite.
        self.active={k:v for k,v in self.active.items() if timestamp-v['last_seen']<30}
        return self.snapshot()
    def snapshot(self):
        return {'total_unique':self.total,'current_total':sum(self.current.values()),'classes':dict(self.classes),
                'current_classes':self.current,'entered':self.entered,'exited':self.exited,
                'currently_inside':max(0,self.initial_inside+self.entered-self.exited),
                'net_flow':self.entered-self.exited,'zones':self.zone_counts,'recent':list(self.recent)}
