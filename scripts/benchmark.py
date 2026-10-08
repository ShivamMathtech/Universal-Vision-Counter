"""Measure the actual asynchronous pipeline; no synthetic FPS values."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.service import AppService
parser=argparse.ArgumentParser();parser.add_argument('--video',required=True);parser.add_argument('--seconds',type=float,default=10)
args=parser.parse_args();service=AppService()
try:
    service.start(str(Path(args.video).resolve()),'video')
    deadline=time.monotonic()+args.seconds
    samples=[]
    while time.monotonic()<deadline and service.pipeline.status=='running':
        time.sleep(.5);samples.append(service.stats())
    keys=['video_fps','display_fps','inference_fps','inference_ms','latency_ms','cpu','ram_gb','dropped_frames','queue_size','total_unique']
    report={'source':str(args.video),'samples':len(samples),'last':{k:samples[-1][k] for k in keys} if samples else {},
            'mean':{k:round(sum(values)/len(values),2) if (values:=[s[k] for s in samples if s[k] is not None]) else None for k in keys[:7]} if samples else {}}
    print(json.dumps(report,indent=2))
finally:service.stop()
