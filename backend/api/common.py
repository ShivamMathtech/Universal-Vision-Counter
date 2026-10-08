import re
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from backend.config import UPLOADS

IMAGE_EXT={'.jpg','.jpeg','.png','.webp'}
VIDEO_EXT={'.mp4','.avi','.mov','.mkv','.webm'}

def safe_file(folder: Path,name: str):
    if Path(name).name!=name or not re.fullmatch(r'[a-zA-Z0-9_.-]+',name):
        raise HTTPException(400,'Invalid file identifier.')
    path=folder/name
    if not path.is_file(): raise HTTPException(404,'File not found.')
    return path

async def save_upload(file: UploadFile,folder: Path,extensions: set[str],limit: int):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in extensions: raise HTTPException(415,'Unsupported file type.')
    path=folder/(uuid.uuid4().hex+suffix)
    size=0
    try:
        with path.open('wb') as output:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>limit: raise HTTPException(413,f'File exceeds {limit//1024//1024} MB.')
                output.write(chunk)
        if not size: raise HTTPException(400,'Empty file.')
        return path
    except Exception:
        path.unlink(missing_ok=True);raise
    finally: await file.close()
