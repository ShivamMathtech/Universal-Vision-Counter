import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.chdir(root);sys.path.insert(0,str(root))
os.environ.setdefault('YOLO_AUTOINSTALL','false')
os.environ.setdefault('YOLO_CONFIG_DIR',str(root/'data'/'ultralytics'))

def open_browser():
    for _ in range(90):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1):
                webbrowser.open('http://127.0.0.1:8000');return
        except Exception:time.sleep(1)
if __name__=='__main__':
    import uvicorn
    if '--no-browser' not in sys.argv:threading.Thread(target=open_browser,daemon=True).start()
    uvicorn.run('backend.main:app',host='127.0.0.1',port=8000,workers=1,log_level='info')
