"""DOC: configuration#development"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description='Run Den locally with a separate database.')
    parser.add_argument('--port', type=int, default=8085)
    parser.add_argument('--check', action='store_true', help='Initialize and check without starting a server.')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use a port between 1024 and 65535.')
    if os.environ.get('DEN_ENV', 'development') != 'development':
        parser.error('Development launcher requires DEN_ENV=development.')
    data = Path(os.environ.get('DEN_DATA_DIR', str(ROOT/'.local/data'))).resolve()
    if data == (ROOT/'infonet').resolve() or 'DenHub' in data.parts:
        parser.error('Use a separate development data directory.')
    data.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, 'DEN_ENV': 'development', 'DEN_DATA_DIR': str(data)}
    command = [sys.executable, '-B', str(ROOT/'infonet/manage.py')]
    subprocess.run(command+['migrate', '--noinput'], env=environment, check=True)
    subprocess.run(command+['collectstatic', '--noinput', '--verbosity', '0'], env=environment, check=True)
    subprocess.run(command+['check'], env=environment, check=True)
    if not args.check:
        subprocess.run(command+['runserver', f'127.0.0.1:{args.port}', '--noreload', '--insecure'],
                       env=environment, check=True)


if __name__ == '__main__':
    main()
