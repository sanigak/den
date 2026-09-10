"""DOC: security#home-network-access"""
from ipaddress import IPv4Network
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from infonet.lan import lan_configuration
from .device_identity import comment_identity
from .models import HouseholdProject, ProjectComment
from .test_comments import identity_map, person_headers


class LanConfigurationTests(SimpleTestCase):
    def test_waitress_accepts_real_listener_configuration_in_each_mode(self):
        import serve
        from waitress.adjustments import Adjustments
        for mode in ['staging', 'production', 'lan']:
            with self.subTest(mode=mode), self.settings(PRODUCTION=mode=='production', LAN=mode=='lan',
                    DEN_LAN_HOST='192.168.50.10', DEN_LAN_PORT=8080), patch('waitress.serve') as run:
                serve.serve_application()
                configuration = Adjustments(**run.call_args.kwargs)
                self.assertEqual(configuration.url_scheme, 'https' if mode=='production' else 'http')
                self.assertEqual(configuration.trusted_proxy, '127.0.0.1' if mode=='production' else None)

    def test_only_explicit_private_ipv4_bindings_are_accepted(self):
        origin, subnet = 'http://192.168.50.10:8080', '192.168.50.0/24'
        self.assertEqual(lan_configuration(origin, subnet), ('192.168.50.10', 8080, IPv4Network(subnet)))
        for invalid in ['http://0.0.0.0:8080', 'http://127.0.0.1:8080', 'http://8.8.8.8:8080',
                        'http://192.168.50.10', 'https://192.168.50.10:8080', origin+'/',
                        'http://user@192.168.50.10:8080', 'http://192.168.50.10:8082',
                        'http://192.168.50.0:8080', 'http://192.168.50.255:8080',
                        'http://localhost:8080', 'http://[::1]:8080', origin+'?query=1']:
            with self.subTest(origin=invalid), self.assertRaises(ValueError):
                lan_configuration(invalid, subnet)
        for invalid in ['', '0.0.0.0/0', '192.168.51.0/24', '192.168.50.10/24', '192.168.50.0/33']:
            with self.subTest(subnet=invalid), self.assertRaises(ValueError):
                lan_configuration(origin, invalid)

    def test_lan_settings_require_deployed_secrets_and_keep_tls_settings_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_file = Path(directory)/'secrets.json'
            secret_file.write_text(json.dumps({'django_secret': secrets.token_urlsafe(64)}))
            environment = {k:v for k,v in os.environ.items() if not k.startswith('DEN_')}
            environment.update(DEN_ENV='lan', DEN_LAN_ORIGIN='http://192.168.50.10:8080',
                               DEN_LAN_SUBNET='192.168.50.0/24', DEN_SECRET_FILE=str(secret_file),
                               DEN_DATA_DIR=directory, DEN_PUBLIC_ORIGIN='https://den.example')
            script = ('from infonet import settings as s; import json; '
                      'print(json.dumps([s.ALLOWED_HOSTS,s.CSRF_COOKIE_SECURE,s.SECURE_SSL_REDIRECT,s.SECURE_HSTS_SECONDS]))')
            command = [sys.executable, '-B', '-c', script]
            def run(overrides):
                return subprocess.run(command, cwd=settings.BASE_DIR, env={**environment, **overrides},
                                      capture_output=True, text=True, timeout=10)
            result = run({})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [['192.168.50.10'], False, False, 0])
            result = run({'DEN_ENV':'production'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [['den.example'], True, True, 31536000])
            for invalid in [{'DEN_SECRET_FILE':''}, {'DEN_DATA_DIR':''}, {'DEN_LAN_SUBNET':''},
                            {'DEN_LAN_ORIGIN':'http://0.0.0.0:8080'}]:
                self.assertNotEqual(run(invalid).returncode, 0)


class LanRequestTests(TestCase):
    def setUp(self):
        override = self.settings(DEN_ENV='lan', LAN=True, DEN_LAN_HOST='192.168.50.10', DEN_LAN_PORT=8080,
            DEN_LAN_NETWORK=IPv4Network('192.168.50.0/24'), ALLOWED_HOSTS=['192.168.50.10'],
            MIDDLEWARE=['myapp.security.LanBoundaryMiddleware', *settings.MIDDLEWARE])
        override.enable()
        self.addCleanup(override.disable)
        self.headers = {'HTTP_HOST':'192.168.50.10:8080', 'REMOTE_ADDR':'192.168.50.20'}

    def test_lan_forms_require_csrf_and_an_exact_origin(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get('/projects/', **self.headers)
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.cookies['csrftoken']['secure'])
        self.assertNotIn('Strict-Transport-Security', page)
        form = {'name':'LAN project', 'project_type':'other', 'urgency':'2', 'description':'Shared household data'}
        self.assertEqual(client.post('/projects/', form, **self.headers).status_code, 403)
        token = client.cookies['csrftoken'].value
        form['csrfmiddlewaretoken'] = token
        rejected = client.post('/projects/', form, HTTP_ORIGIN='http://untrusted.example', **self.headers)
        self.assertEqual(rejected.status_code, 403)
        accepted = client.post('/projects/', form, HTTP_ORIGIN='http://192.168.50.10:8080', **self.headers)
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(HouseholdProject.objects.get().name, 'LAN project')

    def test_peers_hosts_and_forwarded_identity_cannot_bypass_the_boundary(self):
        for peer in ['192.168.51.20', '100.64.0.1', '127.0.0.1', '8.8.8.8', '::1', 'invalid']:
            page = self.client.get('/projects/', HTTP_HOST=self.headers['HTTP_HOST'], REMOTE_ADDR=peer,
                                   HTTP_X_FORWARDED_FOR='192.168.50.20')
            self.assertEqual(page.status_code, 403)
        for host in ['untrusted.example', '192.168.50.10', '192.168.50.10:8081']:
            self.assertEqual(self.client.get('/projects/', HTTP_HOST=host, REMOTE_ADDR='192.168.50.20').status_code, 403)
        project = HouseholdProject.objects.create(name='Identity check')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'devices.json'
            path.write_text(json.dumps(identity_map()))
            with self.settings(DEN_DEVICE_MAP_FILE=str(path)):
                request = RequestFactory().get('/', secure=True, **person_headers())
                self.assertIsNone(comment_identity(request))
                forged = self.client.post(f'/projects/{project.pk}/comments/', {'body':'Forged'},
                    secure=True, HTTP_TAILSCALE_USER_LOGIN='alex@example.test',
                    HTTP_X_FORWARDED_FOR='100.64.0.1', **self.headers)
                self.assertEqual(forged.status_code, 403)
        self.assertEqual(ProjectComment.objects.count(), 0)
