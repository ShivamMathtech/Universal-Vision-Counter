"""Cross-platform first-run installer. Every external command fails fast."""
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.chdir(root)
if sys.version_info[:2] not in ((3,11),(3,12)):
    raise SystemExit('Use Python 3.11 or 3.12. On Windows: py -3.12 scripts/setup.py')
if not (root/'frontend'/'dist'/'index.html').is_file() and not shutil.which('npm'):
    raise SystemExit('Node.js 22 or 24 LTS is required. Install it, then reopen your terminal.')
venv.EnvBuilder(with_pip=True).create(root/'.venv')
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def run(*args):
    print('\n>', ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,shell=False)
run(python,'-m','pip','install','--upgrade','pip')
run(python,'-m','pip','install','torch==2.14.1','torchvision==0.29.1','--index-url','https://download.pytorch.org/whl/cpu')
run(python,'-m','pip','install','-r','requirements.txt')
run(python,'scripts/download_model.py')
# Built frontend is bundled. Node is needed only to rebuild edited source.
if not (root/'frontend'/'dist'/'index.html').is_file():
    npm=shutil.which('npm')
    if os.name=='nt':
        subprocess.run(['cmd','/c',npm,'install'],check=True)
        subprocess.run(['cmd','/c',npm,'run','build'],check=True)
    else:
        run(npm,'install');run(npm,'run','build')
print('\nSetup complete. Run start.bat (Windows) or ./start.sh (Linux).')
