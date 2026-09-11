"""DOC: configuration#device-specific-names"""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase


class DeviceOwnerAssignmentTests(SimpleTestCase):
    def setUp(self):
        path = settings.BASE_DIR.parent/'deploy/sync_devices.py'
        spec = importlib.util.spec_from_file_location('device_assignment_test', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.owners = {'alex@example.test':'Alex', 'sam@example.test':'Sam'}
        self.status = {'BackendState':'Running', 'User':{
            '1':{'LoginName':'alex@example.test'}, '2':{'LoginName':'sam@example.test'}},
            'Self':{'ID':'desktop', 'UserID':1, 'InNetworkMap':True, 'TailscaleIPs':['100.64.0.1']},
            'Peer':{'phone':{'ID':'phone', 'UserID':1, 'InNetworkMap':True, 'TailscaleIPs':['100.64.0.2']}}}
        self.assignments = {'phone':{'login':'alex@example.test', 'author':'Sam'}}

    def authors(self):
        document = self.module.build_map(self.status, self.owners, device_owners=self.assignments)
        return {node['id']:node['author'] for node in document['devices']}

    def test_assignment_changes_only_one_node_and_survives_rename_and_address_change(self):
        self.assertEqual(self.authors(), {'desktop':'Alex', 'phone':'Sam'})
        phone = self.status['Peer']['phone']
        phone.update(HostName='New device name', TailscaleIPs=['100.64.0.3'])
        self.assertEqual(self.authors(), {'desktop':'Alex', 'phone':'Sam'})
        phone['ID'] = 'replacement-node'
        self.assertEqual(self.authors(), {'desktop':'Alex', 'replacement-node':'Alex'})

    def test_assignment_cannot_admit_reassigned_unknown_tagged_or_removed_devices(self):
        phone = self.status['Peer']['phone']
        for changed in [{'UserID':2}, {'UserID':3}, {'Tags':['tag:server']}, {'InNetworkMap':False}]:
            with self.subTest(changed=changed), patch.dict(phone, changed):
                self.assertEqual(self.authors(), {'desktop':'Alex'})

    def test_invalid_assignments_are_rejected(self):
        for invalid in [[], False, {'bad id':self.assignments['phone']}, {'phone':None},
                        {'phone':{'login':'alex@example.test','author':'Sam','unexpected':True}},
                        {str(n):self.assignments['phone'] for n in range(65)}]:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.module.validate_device_owners(invalid)
        for field, values in [('login',['','Alex@example.test',' alex@example.test',123]),
                              ('author',['',' Sam','Sam\n','x'*65,123])]:
            for value in values:
                with self.subTest(field=field, value=value), patch.dict(self.assignments['phone'], {field:value}):
                    with self.assertRaises(ValueError):
                        self.authors()

    def test_disk_assignment_persists_across_refreshes_and_invalid_file_preserves_last_map(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'identity').mkdir()
            (root/'identity/owners.json').write_text(json.dumps(self.owners))
            assignments = root/'identity/device-owners.json'
            assignments.write_text(json.dumps(self.assignments))
            result = SimpleNamespace(stdout=json.dumps(self.status).encode())
            with patch.object(self.module,'ROOT',root), patch.object(self.module.subprocess,'run',return_value=result):
                for _ in range(2):
                    self.assertEqual(self.module.main(), 0)
                    document = json.loads((root/'identity/devices.json').read_text())
                    self.assertEqual({node['id']:node['author'] for node in document['devices']},
                                     {'desktop':'Alex','phone':'Sam'})
                before = (root/'identity/devices.json').read_bytes()
                for invalid in ['{invalid', 'null', '[]']:
                    assignments.write_text(invalid)
                    self.assertEqual(self.module.main(), 1)
                    self.assertEqual((root/'identity/devices.json').read_bytes(), before)
                    self.assertFalse((root/'identity/devices.pending').exists())
