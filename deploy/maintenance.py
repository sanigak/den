"""DOC: deployment#recovery"""
import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

TABLES = ('myapp_item', 'myapp_recipe', 'myapp_mealplan', 'myapp_householdproject', 'myapp_projectcomment')


def fingerprint(path):
    result = {}
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        for table in TABLES:
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists and table != 'myapp_projectcomment':
                raise ValueError('Required household table missing.')
            rows = connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall() if exists else []
            payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()
            result[table] = {'count': len(rows), 'sha256': hashlib.sha256(payload).hexdigest()}
    return result


def copy_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('Source and destination must differ.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst, pages=256, sleep=0.05)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity check failed.')
    return fingerprint(destination)


def backup(root):
    root = Path(root).resolve()
    directory = root / 'backups'
    now = datetime.now(timezone.utc)
    target = directory / ('den-'+now.strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
    evidence = copy_database(root/'data/db.sqlite3', target)
    target.with_suffix('.json').write_text(json.dumps(evidence, indent=2)+'\n')
    cutoff = now - timedelta(days=30)
    for old in directory.glob('den-*.sqlite3'):
        if old.is_symlink():
            continue
        if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
            old.unlink()
            old.with_suffix('.json').unlink(missing_ok=True)
    print(json.dumps({'backup': str(target), 'fingerprints': evidence}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('backup','copy','fingerprint'))
    parser.add_argument('--root', default=r'C:\ProgramData\DenHub')
    parser.add_argument('--source')
    parser.add_argument('--destination')
    args = parser.parse_args()
    if args.action == 'backup':
        backup(args.root)
    elif args.action == 'copy':
        print(json.dumps(copy_database(args.source, args.destination)))
    else:
        print(json.dumps(fingerprint(args.source)))


if __name__ == '__main__':
    main()
