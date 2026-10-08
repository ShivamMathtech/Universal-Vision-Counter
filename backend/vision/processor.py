import cv2
import numpy as np

PALETTE=[(240,145,59),(170,211,40),(63,189,247),(237,139,177),(189,186,51),(194,115,244)]

def annotate(frame,detections,settings,line=None,zones=None):
    image=frame.copy(); h,w=image.shape[:2]
    def point(p): return (int(p[0]*w),int(p[1]*h))
    for zone in zones or []:
        poly=np.array([point(p) for p in zone['points']],np.int32)
        tint=image.copy(); cv2.fillPoly(tint,[poly],(120,80,20)); image=cv2.addWeighted(tint,.18,image,.82,0)
        cv2.polylines(image,[poly],True,(235,175,80),2)
        cv2.putText(image,zone['name'],point(zone['points'][0]),cv2.FONT_HERSHEY_SIMPLEX,.55,(235,175,80),2)
    if line:
        a,b=map(point,line); cv2.arrowedLine(image,a,b,(50,220,255),2,tipLength=.025)
        cv2.putText(image,'COUNT LINE / + SIDE = IN',(a[0],max(20,a[1]-10)),cv2.FONT_HERSHEY_SIMPLEX,.45,(50,220,255),1)
    for d in detections:
        color=PALETTE[d['class_id']%len(PALETTE)]
        x1,y1,x2,y2=d['box']; a,b=point((x1,y1)),point((x2,y2))
        if settings.trajectories and len(d.get('trajectory',[]))>1:
            cv2.polylines(image,[np.array([point(p) for p in d['trajectory']],np.int32)],False,color,2)
        if settings.centers: cv2.circle(image,point(d['center']),3,color,-1)
        if settings.boxes:
            cv2.rectangle(image,a,b,color,2)
            label=d['class_name']
            if settings.track_ids: label+=f" #{d['id']}"
            if settings.show_confidence: label+=f" {d['confidence']:.0%}"
            (tw,th),_=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.48,1)
            top=max(0,a[1]-th-8)
            cv2.rectangle(image,(a[0],top),(min(w,a[0]+tw+8),top+th+8),color,-1)
            cv2.putText(image,label,(a[0]+4,top+th+3),cv2.FONT_HERSHEY_SIMPLEX,.48,(15,20,25),1,cv2.LINE_AA)
    return image
