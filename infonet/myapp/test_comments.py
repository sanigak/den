"""DOC: household_projects#comment-verification"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import time

from django.conf import settings
from django.db import close_old_connections, connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from unittest.mock import patch

from .device_identity import comment_identity
from .models import HouseholdProject, ProjectComment, SecurityState


def identity_map():
    return {'version': 1, 'generated_at': time.time(), 'devices': [
        {'id': 'alex-node', 'author': 'Alex', 'login': 'alex@example.test',
         'addresses': ['100.64.0.1', 'fd7a:115c:a1e0::1']},
        {'id': 'sam-node', 'author': 'Sam', 'login': 'sam@example.test',
         'addresses': ['100.64.0.2', 'fd7a:115c:a1e0::2']}]}


def person_headers(person='alex'):
    return {'REMOTE_ADDR': '100.64.0.1' if person == 'alex' else '100.64.0.2',
            'HTTP_TAILSCALE_USER_LOGIN': person + '@example.test'}


class CommentTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'devices.json'
        self.path.write_text(json.dumps(identity_map()))
        override = self.settings(DEN_DEVICE_MAP_FILE=str(self.path))
        override.enable()
        self.addCleanup(override.disable)
        self.project = HouseholdProject.objects.create(name='Test project')
        self.url = f'/projects/{self.project.pk}/comments/'
        self.detail = f'/projects/{self.project.pk}/'

    def post(self, body='Update', person='alex', **extra):
        return self.client.post(self.url, {'body': body, **extra}, secure=True, **person_headers(person))

    def test_author_timestamp_and_device_are_server_assigned(self):
        instant = datetime(2026, 9, 10, 13, 30, tzinfo=timezone.utc)
        with patch('django.utils.timezone.now', return_value=instant):
            response = self.post('First\nSecond', author='Sam', device_id='forged', created_at='1900-01-01')
        self.assertEqual(response.status_code, 302)
        comment = ProjectComment.objects.get()
        self.assertEqual((comment.author, comment.device_id, comment.created_at), ('Alex', 'alex-node', instant))
        self.assertEqual(comment.body, 'First\nSecond')
        self.assertIn(f'#comment-{comment.pk}', response.url)
        self.assertEqual(self.post('Reply', person='sam').status_code, 302)
        self.assertEqual(ProjectComment.objects.get(body='Reply').author, 'Sam')
        page = self.client.get(self.detail, secure=True, **person_headers())
        self.assertContains(page, 'Sep 10, 2026 · 9:30 AM EDT')
        self.assertContains(page, 'Posting as <strong>Alex</strong>', html=True)
        self.assertContains(self.client.get('/projects/'), 'Comments (2)')

    def test_unknown_missing_mismatched_and_funnel_identity_fail_closed(self):
        for headers in [{}, {'REMOTE_ADDR': '100.64.0.3', 'HTTP_TAILSCALE_USER_LOGIN': 'alex@example.test'},
                        {**person_headers(), 'HTTP_TAILSCALE_USER_LOGIN': 'sam@example.test'},
                        {**person_headers(), 'HTTP_TAILSCALE_FUNNEL_REQUEST': '?1'}]:
            response = self.client.post(self.url, {'body': 'Keep this draft'}, secure=True, **headers)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, 'Keep this draft', status_code=403)
        self.assertFalse(ProjectComment.objects.exists())
        self.assertEqual(self.client.post(self.url, {'body': 'HTTP'}, **person_headers()).status_code, 403)
        self.assertContains(self.client.get(self.detail), 'disabled')

    def test_identity_map_validation_and_ipv6(self):
        request = RequestFactory().get('/', secure=True, **person_headers())
        self.assertEqual(comment_identity(request).author, 'Alex')
        request.META['REMOTE_ADDR'] = 'fd7a:115c:a1e0::1'
        self.assertEqual(comment_identity(request).device_id, 'alex-node')
        for change in [{'generated_at': time.time()-301}, {'generated_at': time.time()+60},
                       {'generated_at': float('nan')}, {'version': 2}, {'devices': 'bad'},
                       {'devices': identity_map()['devices']*2}]:
            self.path.write_text(json.dumps({**identity_map(), **change}))
            self.assertIsNone(comment_identity(request))
        for raw in ['bad json', '[]', 'x'*65537]:
            self.path.write_text(raw)
            self.assertIsNone(comment_identity(request))
        self.path.unlink()
        self.assertIsNone(comment_identity(request))

    def test_text_escaping_and_body_limits(self):
        attack = '<script>alert(1)</script>\n\"; DROP TABLE myapp_householdproject;--'
        self.assertEqual(self.post(attack).status_code, 302)
        page = self.client.get(self.detail)
        self.assertContains(page, '&lt;script&gt;')
        self.assertNotContains(page, '<script>alert(1)</script>')
        for body in ['', '   \n ', 'x'*4001]:
            self.assertEqual(self.post(body).status_code, 400)
        self.assertEqual(self.post('x'*4000).status_code, 302)
        self.assertEqual(ProjectComment.objects.count(), 2)
        self.assertEqual(HouseholdProject.objects.count(), 1)

    def test_csrf_methods_bad_ids_and_global_budget(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(self.url, {'body': 'no token'}, secure=True, **person_headers()).status_code, 403)
        strict.get(self.detail, secure=True, **person_headers())
        token = strict.cookies['csrftoken'].value
        self.assertEqual(strict.post(self.url, {'body': 'Valid token', 'csrfmiddlewaretoken': token},
            secure=True, HTTP_REFERER='https://testserver'+self.detail, **person_headers()).status_code, 302)
        ProjectComment.objects.all().delete()
        for method in ('get', 'head', 'put', 'patch', 'delete', 'options'):
            self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)
        for value in ('0', '-1', '1 OR 1=1', '999999999999999999999999'):
            self.assertEqual(self.client.post(f'/projects/{value}/comments/', {'body': 'bad'}).status_code, 404)
        SecurityState.objects.update(minute=int(time.time()//60), writes=60)
        response = self.post('limited')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertFalse(ProjectComment.objects.exists())

    def test_project_cap_completed_threads_and_cascade(self):
        self.project.is_completed = True
        self.project.save()
        ProjectComment.objects.bulk_create([ProjectComment(project=self.project, body='Existing', author='Alex',
                                                          device_id='alex-node') for _ in range(199)])
        self.assertEqual(self.post('Last slot').status_code, 302)
        self.assertEqual(self.post('Overflow').status_code, 400)
        response = self.client.get(self.detail)
        self.assertEqual(len(response.context['comment_page']), 50)
        self.assertContains(response, 'Last slot')
        self.assertEqual(response.context['comment_page'].number, 4)
        self.assertEqual(self.client.get(self.detail+'?page=1').context['comment_page'].number, 1)
        self.assertEqual(self.client.post(f'/projects/{self.project.pk}/delete/').status_code, 302)
        self.assertFalse(ProjectComment.objects.exists())

    def test_global_comment_cap(self):
        other = HouseholdProject.objects.create(name='Other')
        ProjectComment.objects.bulk_create([ProjectComment(project=other, body='Existing', author='Sam',
                                                          device_id='sam-node') for _ in range(10000)])
        self.assertEqual(self.post('Overflow').status_code, 400)
        self.assertFalse(self.project.comments.exists())


class ConcurrentCommentTests(TransactionTestCase):
    def test_backup_restore_includes_comment_contents_and_legacy_empty_table(self):
        import sqlite3
        path = settings.BASE_DIR.parent / 'deploy/maintenance.py'
        spec = importlib.util.spec_from_file_location('comment_maintenance_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        project = HouseholdProject.objects.create(name='Backup test')
        comment = ProjectComment.objects.create(project=project, body='Preserve this comment\n<script>data</script>',
                                                author='Sam', device_id='sam-node')
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'backup.sqlite3'
            restore = Path(directory) / 'restore.sqlite3'
            expected = module.copy_database(connection.settings_dict['NAME'], backup)
            actual = module.copy_database(backup, restore)
            self.assertEqual(expected, actual)
            self.assertEqual(actual['myapp_projectcomment']['count'], 1)
            with closing(sqlite3.connect(restore)) as db:
                self.assertEqual(db.execute('SELECT body,author,device_id FROM myapp_projectcomment').fetchone(),
                                 (comment.body, 'Sam', 'sam-node'))
                schema = db.execute("SELECT sql FROM sqlite_master WHERE name='myapp_projectcomment'").fetchone()[0]
                db.execute('DROP TABLE myapp_projectcomment')
                db.commit()
                before = module.fingerprint(restore)
                db.execute(schema)
                db.commit()
            self.assertEqual(before, module.fingerprint(restore))

    def test_last_project_slot_is_transactional(self):
        if connection.is_in_memory_db():
            self.skipTest('Requires DEN_TEST_DB.')
        SecurityState.objects.get_or_create(pk=1)
        project = HouseholdProject.objects.create(name='Concurrent comments')
        ProjectComment.objects.bulk_create([ProjectComment(project=project, body='Existing', author='Alex',
                                                          device_id='alex-node') for _ in range(199)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'devices.json'
            path.write_text(json.dumps(identity_map()))
            with self.settings(DEN_DEVICE_MAP_FILE=str(path)):
                def post(_):
                    close_old_connections()
                    try:
                        return Client().post(f'/projects/{project.pk}/comments/', {'body': 'New'},
                                             secure=True, **person_headers()).status_code
                    finally:
                        close_old_connections()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    statuses = list(pool.map(post, range(8)))
        self.assertEqual(statuses.count(302), 1, statuses)
        self.assertEqual(statuses.count(400), 7, statuses)
        self.assertEqual(project.comments.count(), 200)


class DeviceMapSyncTests(TestCase):
    def test_only_loopback_forwarded_address_is_trusted(self):
        from waitress.proxy_headers import proxy_headers_middleware
        captured = {}
        def application(environ, start_response):
            captured.update(environ)
            return []
        middleware = proxy_headers_middleware(application, trusted_proxy='127.0.0.1',
            trusted_proxy_headers={'x-forwarded-for'}, trusted_proxy_count=1, clear_untrusted=True)
        for peer, expected in [('127.0.0.1', '100.64.0.1'), ('10.0.0.99', '10.0.0.99')]:
            captured.clear()
            middleware({'REMOTE_ADDR': peer, 'HTTP_X_FORWARDED_FOR': '100.64.0.2, 100.64.0.1',
                        'HTTP_HOST': 'den.example', 'HTTP_X_FORWARDED_HOST': 'evil.example',
                        'HTTP_X_FORWARDED_PROTO': 'http', 'wsgi.url_scheme': 'https'}, lambda *args: None)
            self.assertEqual(captured['REMOTE_ADDR'], expected)
            self.assertEqual(captured['HTTP_HOST'], 'den.example')
            self.assertEqual(captured['wsgi.url_scheme'], 'https')
            self.assertNotIn('HTTP_X_FORWARDED_HOST', captured)
            self.assertNotIn('HTTP_X_FORWARDED_PROTO', captured)

    def test_owner_mapping_excludes_unrecognized_tagged_and_removed_devices(self):
        path = settings.BASE_DIR.parent / 'deploy/sync_devices.py'
        spec = importlib.util.spec_from_file_location('sync_devices_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def node(identifier, user, ip, **extra):
            return {'ID': identifier, 'UserID': user, 'TailscaleIPs': [ip], 'InNetworkMap': True, **extra}
        status = {'BackendState': 'Running', 'Self': node('host', 1, '100.64.0.1'),
                  'User': {'1': {'LoginName': 'alex@example.test'}, '2': {'LoginName': 'sam@example.test'}},
                  'Peer': {'a': node('member', 2, '100.64.0.2'), 'b': node('stranger', 3, '100.64.0.3'),
                           'c': node('server', 1, '100.64.0.4', Tags=['tag:server']),
                           'd': node('removed', 1, '100.64.0.5', InNetworkMap=False)}}
        owners = {'alex@example.test': 'Alex', 'sam@example.test': 'Sam'}
        document = module.build_map(status, owners, now=1000)
        self.assertEqual([(row['id'], row['author']) for row in document['devices']], [('host', 'Alex'), ('member', 'Sam')])
        owners['alex@example.test'] = 'Alexandra Household'
        self.assertEqual(module.build_map(status, owners)['devices'][0]['author'], 'Alexandra Household')
        for invalid in ['', ' ', ' Leading', 'Line\nBreak', 'x'*65, 123]:
            with self.assertRaises(ValueError):
                module.build_map(status, {'alex@example.test': invalid})
        status['Peer']['a']['TailscaleIPs'] = ['100.64.0.1']
        with self.assertRaises(ValueError):
            module.build_map(status, owners)
        status['BackendState'] = 'Stopped'
        with self.assertRaises(ValueError):
            module.build_map(status, owners)
