"""DOC: contributing#checks"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PARTS = {'.hardening', 'backups', 'openclaw-backup', 'infonetenv', '.venv', 'venv',
                 '__pycache__', 'staticfiles', 'node_modules', '.local', 'private', 'local-data'}
BLOCKED_NAMES = {'secrets.json', 'owners.json', 'devices.json', 'den-runtime.json',
                 'household-owners.json', 'tailscale-policy.json', 'live-url.txt', '.env', 'local.ps1'}
SECRET = re.compile(r'sk-(?:ant|or)-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|'
                    r'github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
TEXT_SUFFIXES = {'.py', '.ps1', '.bat', '.md', '.json', '.yml', '.yaml', '.toml', '.ini',
                 '.cfg', '.txt', '.html', '.js', '.css', '.csv'}


def run_git(*arguments):
    return subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def candidate_files():
    probe = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, capture_output=True)
    if probe.returncode == 0 and Path(os.fsdecode(probe.stdout).strip()).resolve() == ROOT:
        raw = run_git('ls-files', '-z', '--cached', '--others', '--exclude-standard')
    else:
        with tempfile.TemporaryDirectory(prefix='den-git-check-') as directory:
            run_git('init', '--bare', directory)
            raw = run_git('--git-dir='+directory, '--work-tree='+str(ROOT),
                          'ls-files', '-z', '--others', '--exclude-standard')
    return sorted({os.fsdecode(name) for name in raw.split(b'\0') if name})


def private_markers():
    markers = set()
    for path in [ROOT/'deploy/household-owners.json', ROOT/'config/household-owners.json']:
        if path.exists():
            markers.update(json.loads(path.read_text(encoding='utf-8-sig')).keys())
    policy = ROOT/'deploy/tailscale-policy.json'
    if policy.exists():
        markers.update(json.loads(policy.read_text(encoding='utf-8-sig')).get('hosts', {}).values())
    bookmark = ROOT/'deploy/live-url.txt'
    if bookmark.exists():
        markers.add(urlsplit(bookmark.read_text().strip()).hostname or '')
    return {value for value in markers if isinstance(value, str) and len(value) >= 8}


def check_files(names):
    findings = []
    markers = private_markers()
    for name in names:
        path = ROOT/name
        parts = Path(name).parts
        if (set(parts) & BLOCKED_PARTS or path.name in BLOCKED_NAMES
                or (path.name.startswith('.env.') and path.name != '.env.example')
                or (parts[0] == 'config' and '.example.' not in path.name)
                or re.search(r'\.(sqlite3.*|sqlite|db|zip|log|dpapi|pem|key|pyc)$', name, re.I)):
            findings.append({'file': name, 'category': 'private or generated file'})
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            findings.append({'file': name, 'category': 'symlink or escaped path'})
            continue
        if not path.exists():
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {'LICENSE', '.gitignore', '.gitattributes'}:
            text = path.read_text(encoding='utf-8-sig')
            if SECRET.search(text):
                findings.append({'file': name, 'category': 'credential pattern'})
            if any(marker.casefold() in text.casefold() for marker in markers):
                findings.append({'file': name, 'category': 'private configuration value'})
            if re.search(r'C:[/\\]Users[/\\][A-Za-z0-9_-]+', text, re.I):
                findings.append({'file': name, 'category': 'personal Windows profile path'})
    return findings


def main():
    parser = argparse.ArgumentParser(description='Check the exact repository candidate file set without publishing.')
    parser.add_argument('--list', action='store_true', help='Also print candidate paths.')
    args = parser.parse_args()
    names = candidate_files()
    findings = check_files(names)
    result = {'passed': not findings, 'candidate_files': len(names), 'findings': findings,
              'scope': 'Git candidates, forbidden private files, selected credential patterns, known local identifiers.'}
    if args.list:
        result['files'] = names
    print(json.dumps(result, indent=2))
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
