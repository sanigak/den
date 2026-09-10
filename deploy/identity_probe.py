"""DOC: deployment#identity-verification"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sqlite3
import subprocess


def access_allowed(path, write=False, delete=False):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    access = 0x10000 if delete else (0x40000000 if write else 0x80000000)
    handle = kernel.CreateFileW(str(path), access,
                                7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        return {'allowed': False, 'error': error}
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(handle)
    return {'allowed': True, 'error': 0}


def main():
    root = Path(os.environ['DEN_RUNTIME_ROOT'])
    config = json.loads((root/'probe-config.json').read_text(encoding='utf-8-sig'))
    results = {'identity': subprocess.check_output(['whoami'], text=True).strip(),
               'privileges': subprocess.check_output(['whoami', '/priv'], text=True).strip(), 'checks': {}}
    for name, path in config['deny_read'].items():
        results['checks'][name] = access_allowed(path)
    for name, path in config['deny_write'].items():
        results['checks'][name] = access_allowed(path, True)
    for name, path in config['deny_delete'].items():
        results['checks'][name] = access_allowed(path, delete=True)
    marker = root/'tmp/probe-write.txt'
    marker.write_text('synthetic probe')
    marker.unlink()
    with sqlite3.connect(root/'data/db.sqlite3') as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS den_identity_probe (value INTEGER)')
        connection.execute('INSERT INTO den_identity_probe VALUES (1)')
        connection.execute('DROP TABLE den_identity_probe')
    results['database_write'] = True
    results['device_map_read'] = access_allowed(root/'identity/devices.json')['allowed']
    results['pass'] = (results['identity'].lower() == 'nt service\\denhub'
                       and results['device_map_read']
                       and all(not value['allowed'] and value['error'] == 5
                               for value in results['checks'].values())
                       and 'SeImpersonatePrivilege' not in results['privileges']
                       and 'SeDebugPrivilege' not in results['privileges'])
    (root/'logs/identity-probe.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
