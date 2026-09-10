"""DOC: contributing#checks"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='den-check-') as directory:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('DEN_') and key != 'OPENROUTER_API_KEY'}
        environment.update(DEN_ENV='development', DEN_AI_ENABLED='0', DEN_DATA_DIR=directory,
                           DEN_TEST_DB=str(Path(directory)/'tests.sqlite3'), PYTHONUTF8='1')
        manage = [sys.executable, '-B', 'manage.py']
        for arguments in [['check'], ['makemigrations', '--check', '--dry-run'], ['test', 'myapp', '--noinput']]:
            subprocess.run(manage+arguments, cwd=ROOT/'infonet', env=environment, check=True)
        subprocess.run([sys.executable, '-B', 'deploy/source_checks.py'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
