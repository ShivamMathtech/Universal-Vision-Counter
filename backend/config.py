from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator
import os

os.environ.setdefault('YOLO_AUTOINSTALL','false')
ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('VC_DATA_DIR', str(ROOT / 'data'))).resolve()
UPLOADS, OUTPUTS, MODELS = (ROOT / name for name in ('uploads', 'outputs', 'models'))
for path in (DATA, UPLOADS, OUTPUTS, MODELS):
    path.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    model: str = 'yolo11n.pt'
    device: Literal['cpu', 'cuda:0'] = 'cpu'
    image_size: Literal[320, 416, 480, 640] = 416
    confidence: float = Field(default=.35, ge=.1, le=.95)
    iou: float = Field(default=.45, ge=.1, le=.95)
    display_fps: int = Field(default=24, ge=5, le=60)
    inference_fps: float = Field(default=8, ge=1, le=30)
    frame_skip: int = Field(default=0, ge=0, le=30)
    queue_size: int = Field(default=2, ge=1, le=4)
    tracker: Literal['bytetrack'] = 'bytetrack'
    track_buffer: int = Field(default=30, ge=5, le=120)
    adaptive: bool = True
    performance: Literal['Quality','Balanced','Performance'] = 'Balanced'
    cpu_threads: int = Field(default=4, ge=1, le=16)
    boxes: bool = True
    track_ids: bool = True
    show_confidence: bool = True
    trajectories: bool = False
    centers: bool = False
    theme: Literal['dark','light'] = 'dark'
    initial_inside: int = Field(default=0, ge=0, le=1000000)
    camera_index: int = Field(default=0, ge=0, le=16)
    camera_width: int = Field(default=640, ge=160, le=1920)
    camera_height: int = Field(default=480, ge=120, le=1080)
    camera_fps: int = Field(default=24, ge=5, le=60)

class Point(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)

class LineConfig(BaseModel):
    points: list[Point] = Field(min_length=2, max_length=2)
    @model_validator(mode='after')
    def distinct(self):
        a,b=self.points
        if (a.x-b.x)**2+(a.y-b.y)**2 < .0001:
            raise ValueError('Draw a line at least 1% of the image width long.')
        return self

class ZoneConfig(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=r'^[\w -]+$')
    points: list[Point] = Field(min_length=3, max_length=20)
    @model_validator(mode='after')
    def area(self):
        p=self.points
        area=abs(sum(a.x*b.y-b.x*a.y for a,b in zip(p,p[1:]+p[:1])))/2
        if area < .0001:
            raise ValueError('Zone must have a nonzero area; draw vertices in boundary order.')
        return self
