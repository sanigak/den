"""DOC: household_projects#comment-verification"""
from contextlib import closing
from datetime import datetime, timezone
from html import escape
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import uuid

import httpx

ROOT = Path(r'C:\ProgramData\DenHub')
SOURCE = Path(__file__).resolve().parent.parent


def main():
    state = json.loads((ROOT/'den-runtime.json').read_text(encoding='utf-8-sig'))
    origin = state['productionOrigin']
    registry = json.loads((ROOT/'identity/devices.json').read_text())
    tailscale = subprocess.run([r'C:\Program Files\Tailscale\tailscale.exe', 'status', '--json'],
        check=True, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    self_id = json.loads(tailscale.stdout)['Self']['ID']
    host = next(node for node in registry['devices'] if node['id'] == self_id)
    author = host['author']
    spec = importlib.util.spec_from_file_location('den_comment_maintenance', ROOT/'tools/maintenance.py')
    maintenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maintenance)
    title = 'Den comment verification ' + uuid.uuid4().hex[:12]
    body = 'Synthetic comment verification.\n<script>alert("data only")</script>'
    project_id = None
    evidence = {'passed': False}
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        def post(path, values, headers=None):
            client.get(origin+'/projects/').raise_for_status()
            return client.post(origin+path, data={**values, 'csrfmiddlewaretoken': client.cookies['csrftoken']},
                headers={'Referer': origin+'/projects/', **(headers or {})})
        try:
            response = post('/projects/', {'name': title, 'project_type': 'other', 'urgency': '2'})
            assert response.status_code == 302, 'Synthetic project creation failed.'
            with closing(sqlite3.connect(ROOT/'data/db.sqlite3')) as db:
                project_id = db.execute('SELECT id FROM myapp_householdproject WHERE name=?', (title,)).fetchone()[0]
            detail = f'/projects/{project_id}/'
            response = client.get(origin+detail)
            assert f'Posting as <strong>{escape(author)}</strong>' in response.text, 'Actual device attribution failed.'
            response = post(detail+'comments/', {'body': body, 'author': 'Forged author', 'device_id': 'forged'},
                {'Tailscale-User-Login': 'spoof@example.invalid', 'X-Forwarded-For': '100.64.0.222',
                 'Tailscale-User-Name': 'Forged author', 'Forwarded': 'for=100.64.0.222;proto=http'})
            assert response.status_code == 302, 'Comment POST failed.'
            with closing(sqlite3.connect(ROOT/'data/db.sqlite3')) as db:
                row = db.execute('SELECT body,author,device_id,created_at FROM myapp_projectcomment WHERE project_id=?',
                                 (project_id,)).fetchone()
            assert row[:3] == (body, author, host['id']), 'Spoofed headers changed attribution.'
            timestamp = datetime.fromisoformat(row[3]).replace(tzinfo=timezone.utc)
            assert abs((datetime.now(timezone.utc)-timestamp).total_seconds()) < 60, 'Timestamp incorrect.'
            response = client.get(origin+detail)
            assert '&lt;script&gt;' in response.text and '<script>alert' not in response.text, 'Escaping failed.'
            assert 'script-src \'self\'' in response.headers['content-security-policy'], 'CSP missing.'
            assert post(detail+'comments/', {'body': ' '*4}).status_code == 400, 'Empty comment accepted.'
            assert client.post(origin+detail+'comments/', data={'body': 'no token'}).status_code == 403, 'CSRF bypass.'
            assert client.get(origin+detail+'comments/').status_code == 405, 'Write method bypass.'
            with httpx.Client(timeout=10, trust_env=False) as direct:
                denied = direct.get('http://127.0.0.1:8082'+detail, headers={'Host': origin.removeprefix('https://')})
                assert 'Posting as <strong>' not in denied.text, 'Direct anonymous connection gained identity.'
            directory = ROOT/'comment-restore-check'
            directory.mkdir(exist_ok=True)
            backup = directory/'backup.sqlite3'
            restored = directory/'restored.sqlite3'
            expected = maintenance.copy_database(ROOT/'data/db.sqlite3', backup)
            actual = maintenance.copy_database(backup, restored)
            assert actual == expected, 'Restored data fingerprints differ.'
            with closing(sqlite3.connect(restored)) as db:
                saved = db.execute('SELECT body,author,device_id FROM myapp_projectcomment WHERE project_id=?',
                                   (project_id,)).fetchone()
            assert saved == row[:3], 'Restored comment contents differ.'
            evidence.update(passed=True, author=author, deviceId=host['id'], spoofedHeadersOverwritten=True,
                timestampCorrect=True, cspEnforced=True, csrfEnforced=True, malformedRejected=True,
                unsupportedMethodRejected=True, anonymousOriginHasNoIdentity=True, restoredCommentMatches=True,
                restoredTableCount=len(actual))
        finally:
            if project_id is not None:
                response = post(f'/projects/{project_id}/delete/', {})
                assert response.status_code == 302, 'Synthetic project cleanup failed.'
                with closing(sqlite3.connect(ROOT/'data/db.sqlite3')) as db:
                    assert not db.execute('SELECT 1 FROM myapp_projectcomment WHERE project_id=?', (project_id,)).fetchone()
                evidence['syntheticProjectRemoved'] = True
            (SOURCE/'.hardening/comments-live-evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
