"""Download and validate the official pretrained YOLO11 nano checkpoint."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.models.model_manager import ModelManager
if __name__=='__main__':
    manager=ModelManager();name=manager.download_pretrained()
    print(f'Ready: models/{name} ({len(manager.validate(Path("models")/name))} classes)')
