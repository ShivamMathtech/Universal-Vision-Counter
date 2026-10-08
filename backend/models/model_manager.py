"""Restricted checkpoint loading: never call unrestricted pickle on an upload."""
from pathlib import Path
import inspect
import logging
import threading
import urllib.request
import os
from backend.config import MODELS

log=logging.getLogger(__name__)

class ModelManager:
    def __init__(self):
        self.lock=threading.RLock()
        self.model=None
        self.name=None
        self.names={}
    def available(self):
        return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(MODELS.glob('*.pt'))]
    def download_pretrained(self):
        path=MODELS/'yolo11n.pt'
        if path.exists(): return path.name
        tmp=path.with_suffix('.download')
        url='https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt'
        try:
            with urllib.request.urlopen(url,timeout=60) as response, tmp.open('wb') as f:
                size=0
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>30*1024*1024: raise ValueError('Unexpected pretrained model size.')
                    f.write(chunk)
            self.validate(tmp)
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
        return path.name
    @staticmethod
    def safe_checkpoint(path):
        import torch
        import torch.nn as nn
        from ultralytics.nn import modules
        from ultralytics.nn.modules import block, conv, head, transformer
        from ultralytics.nn.tasks import DetectionModel
        # Explicitly restricted to installed torch/Ultralytics neural-network classes.
        # Unknown Python functions, custom classes and pickle reducers stay forbidden.
        allowed=[DetectionModel]
        for module in (nn,modules,block,conv,head,transformer):
            for _,value in vars(module).items():
                if inspect.isclass(value) and issubclass(value,nn.Module) and value.__module__.startswith(('torch.nn.','ultralytics.nn.modules.')):
                    allowed.append(value)
        try:
            with torch.serialization.safe_globals(allowed):
                checkpoint=torch.load(path,map_location='cpu',weights_only=True)
        except Exception as exc:
            raise ValueError('Unsupported or invalid checkpoint. Use a standard Ultralytics detection .pt file without custom Python classes.') from exc
        if not isinstance(checkpoint,dict): raise ValueError('Expected an Ultralytics detection checkpoint dictionary.')
        model=checkpoint.get('ema') or checkpoint.get('model')
        if type(model) is not DetectionModel:
            raise ValueError('Only compatible Ultralytics object-detection .pt models are supported.')
        names=getattr(model,'names',None)
        if isinstance(names,list): names=dict(enumerate(names))
        if not isinstance(names,dict) or not names or len(names)>10000 or any(not isinstance(k,int) or not isinstance(v,str) or len(v)>200 for k,v in names.items()):
            raise ValueError('Checkpoint has invalid class names.')
        if set(names)!=set(range(len(names))): raise ValueError('Class indices must be contiguous from zero.')
        return model, names
    def validate(self,path):
        with self.lock:
            model,names=self.safe_checkpoint(path)
            del model
            return names
    def load(self,name,settings):
        import torch
        from ultralytics import YOLO
        from ultralytics.utils import DEFAULT_CFG_DICT
        if Path(name).name!=name or not name.endswith('.pt'): raise ValueError('Choose a .pt filename from the model list.')
        path=MODELS/name
        if not path.is_file(): raise ValueError('Model missing. Install YOLO11 nano or upload a compatible .pt model in Settings.')
        with self.lock:
            if settings.device!='cpu' and not torch.cuda.is_available(): raise ValueError('CUDA is unavailable. Select CPU.')
            torch.set_num_threads(settings.cpu_threads)
            network,names=self.safe_checkpoint(path)
            network=network.float().eval()
            network.args={**DEFAULT_CFG_DICT,**getattr(network,'args',{}),'task':'detect'}
            network.task='detect'
            network.pt_path=str(path)
            # Construct only from bundled YAML; assign the restricted, validated network.
            wrapper=YOLO('yolo11n.yaml',task='detect',verbose=False)
            wrapper.model=network
            wrapper.task='detect'
            wrapper.overrides={'task':'detect','model':str(path),'device':settings.device}
            wrapper.ckpt_path=str(path)
            wrapper.predictor=None
            self.model,self.names,self.name=wrapper,names,name
            log.info('Model loaded: %s (%d classes)',name,len(names))
        return self.info()
    def unload(self):
        with self.lock:
            self.model=None; self.names={}; self.name=None
    def info(self):
        return {'name':self.name,'classes':self.names,'type':'YOLO detection','loaded':self.model is not None}
