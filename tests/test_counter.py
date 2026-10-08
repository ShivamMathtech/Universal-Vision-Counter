from backend.analytics.history import History
from backend.vision.counter import ObjectCounter,inside_polygon

def detection(tid,x=.4,y=.3,name='apple'):
    return {'id':tid,'class_id':0,'class_name':name,'confidence':.9,'box':[x-.03,y-.03,x+.03,y+.03],'center':[x,y]}

def counter(line=None,zones=None): return ObjectCounter(History(':memory:'),'test',line,zones)

def test_same_object_100_frames_counts_once():
    c=counter()
    for i in range(100): c.update([detection(17)],i*.1,i*.1)
    assert c.snapshot()['total_unique']==1
    assert c.snapshot()['classes']=={'apple':1}
    assert len(c.active[17]['trajectory'])==30

def test_ten_objects_five_leave_three_enter():
    c=counter();c.update([detection(i) for i in range(10)],0,0)
    c.update([detection(i) for i in range(5,10)]+[detection(i) for i in range(10,13)],1,1)
    assert c.snapshot()['total_unique']==13
    assert c.snapshot()['current_total']==8

def test_bidirectional_line_crossing_and_hysteresis():
    c=counter([(.2,.5),(.8,.5)])
    for t,y in enumerate([.4,.499,.501,.6,.502,.498,.4]): c.update([detection(1,y=y)],t,t)
    assert c.entered==1 and c.exited==1
    assert c.snapshot()['currently_inside']==0

def test_infinite_line_extension_does_not_count():
    c=counter([(.2,.5),(.8,.5)])
    c.update([detection(1,x=.95,y=.4)],0,0);c.update([detection(1,x=.95,y=.6)],1,1)
    assert c.entered==0 and c.exited==0

def test_multiple_zone_occupancy_and_exit_events():
    zones=[{'name':'A','points':[(0,0),(.5,0),(.5,1),(0,1)]},{'name':'B','points':[(.5,0),(1,0),(1,1),(.5,1)]}]
    c=counter(zones=zones);c.update([detection(1,x=.2),detection(2,x=.8)],0,0)
    assert c.zone_counts=={'A':1,'B':1}
    c.update([detection(1,x=.8)],1,1)
    assert c.zone_counts=={'A':0,'B':1}
    assert len(c.history.rows("SELECT * FROM count_events WHERE event='zone_exit'"))==1

def test_long_inactivity_prunes_trajectories_but_never_recounts_same_id():
    c=counter();c.update([detection(1)],0,0);c.update([],40,40)
    assert not c.active
    c.update([detection(1)],41,41)
    assert c.total==1

def test_class_jitter_does_not_double_count():
    c=counter();c.update([detection(1,name='apple')],0,0);c.update([detection(1,name='orange')],1,1)
    assert c.classes=={'apple':1} and c.current=={'apple':1}

def test_polygon_membership():
    p=[(0,0),(1,0),(1,1),(0,1)]
    assert inside_polygon((.5,.5),p)
    assert not inside_polygon((2,.5),p)
