"""DOC: security#ai-export"""
import json
from pathlib import Path
import subprocess
import sys
import sysconfig

WORKER = Path(__file__).with_name('ai_worker.py')
BOOTSTRAP = "import runpy,sys; sys.path.insert(0,sys.argv[1]); runpy.run_path(sys.argv[2],run_name='__main__')"


def organize(raw_list, api_key):
    if len(raw_list.encode('utf-8')) > 32768:
        raise ValueError('Input limit exceeded.')
    result = subprocess.run(
        [getattr(sys, '_base_executable', sys.executable), '-I', '-X', 'utf8', '-c', BOOTSTRAP,
         sysconfig.get_path('purelib'), str(WORKER)],
        input=json.dumps({'text': raw_list, 'key': api_key}),
        text=True, encoding='utf-8', capture_output=True, timeout=30,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True,
    )
    if len(result.stdout.encode('utf-8')) > 32768:
        raise ValueError('Output limit exceeded.')
    return result.stdout.strip()
