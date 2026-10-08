import time
from collections import deque
class Rate:
    def __init__(self): self.times=deque(maxlen=180)
    def tick(self): self.times.append(time.monotonic())
    def value(self):
        t=list(self.times)
        return round((len(t)-1)/(t[-1]-t[0]),1) if len(t)>1 and time.monotonic()-t[-1]<2 else 0.0
class AdaptiveController:
    def __init__(self, size, fps):
        self.base_size,self.base_fps=size,fps
        self.size,self.fps=size,fps
        self.last=0.; self.level=0
    def update(self,cpu,now):
        if now-self.last<5: return self.size,self.fps
        self.last=now
        target=3 if cpu>90 else 2 if cpu>80 else 1 if cpu>60 else 0
        if target<self.level and cpu>55: target=self.level
        self.level=target
        self.size=min(self.base_size,320 if target==3 else 416 if target==2 else self.base_size)
        self.fps=max(1,self.base_fps*(1,.8,.6,.4)[target])
        return self.size,self.fps


def process_memory_gb():
    import os
    import psutil
    try:
        return psutil.Process().memory_info().rss / 1024**3
    except (psutil.Error, OSError):
        # PID namespaces can hide the numeric PID while /proc/self remains valid.
        try:
            with open('/proc/self/statm') as f:
                pages=int(f.read().split()[1])
            return pages*os.sysconf('SC_PAGE_SIZE')/1024**3
        except (OSError, ValueError, IndexError):
            return None
