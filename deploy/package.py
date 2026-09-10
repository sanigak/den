"""DOC: deployment#installation"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def package(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    names = (source/'deploy/package-files.txt').read_text().splitlines()
    paths = []
    for name in names:
        relative = Path(name)
        if not name or relative.is_absolute() or '..' in relative.parts or ':' in name:
            raise ValueError('Invalid package allowlist entry.')
        path = source/'infonet'/relative
        if not path.resolve().is_relative_to((source/'infonet').resolve()):
            raise ValueError('Package entry escapes the source directory.')
        paths.append(path)
    manifest = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError('Package cannot contain symbolic links.')
        relative = path.relative_to(source/'infonet')
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        manifest[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (destination/'package-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    package(args.source, args.destination)
