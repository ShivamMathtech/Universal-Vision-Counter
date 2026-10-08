"""Create a short, explicitly synthetic pan of the bundled sample photograph."""
from pathlib import Path
import cv2
import numpy as np
root=Path(__file__).resolve().parents[1]
image=cv2.imread(str(root/'tests/assets/bus.jpg'))
if image is None:raise SystemExit('Sample image missing.')
image=cv2.resize(image,(480,640))
path=root/'outputs/demo.avi';path.parent.mkdir(exist_ok=True)
writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),24,(480,640))
if not writer.isOpened():raise SystemExit('MJPG encoder unavailable.')
for i in range(144):
    dx=round(10*np.sin(i/35));matrix=np.float32([[1,0,dx],[0,1,0]])
    writer.write(cv2.warpAffine(image,matrix,(480,640),borderMode=cv2.BORDER_REFLECT))
writer.release();print(path)
