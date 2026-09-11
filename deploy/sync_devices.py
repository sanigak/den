"""DOC: deployment#device-map"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(r'C:\ProgramData\DenHub')
TAILSCALE = r'C:\Program Files\Tailscale\tailscale.exe'


def validate_device_owners(assignments):
    if not isinstance(assignments, dict) or len(assignments) > 64:
        raise ValueError('Invalid device owner assignments.')
    for node_id, assignment in assignments.items():
        if (not isinstance(node_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', node_id)
                or not isinstance(assignment, dict) or set(assignment) != {'login', 'author'}):
            raise ValueError('Invalid device owner assignment.')
        login, author = assignment['login'], assignment['author']
        if (not isinstance(login, str) or not 1 <= len(login) <= 254
                or login != login.strip().lower() or not login.isprintable()
                or not isinstance(author, str) or not 1 <= len(author) <= 64
                or author != author.strip() or not author.isprintable()):
            raise ValueError('Invalid device owner assignment.')


def build_map(status, owners, now=None, device_owners=None):
    if (status.get('BackendState') != 'Running' or not isinstance(owners, dict)
            or not 1 <= len(owners) <= 64):
        raise ValueError('Invalid identity configuration.')
    for login, name in owners.items():
        if (not isinstance(login, str) or not 1 <= len(login) <= 254
                or login != login.strip().lower() or not login.isprintable()
                or not isinstance(name, str) or not 1 <= len(name) <= 64
                or name != name.strip() or not name.isprintable()):
            raise ValueError('Invalid identity configuration.')
    device_owners = {} if device_owners is None else device_owners
    validate_device_owners(device_owners)
    users = status.get('User', {})
    nodes = [status.get('Self', {})] + list(status.get('Peer', {}).values())
    devices, addresses, ids = [], set(), set()
    for node in nodes:
        login = users.get(str(node.get('UserID')), {}).get('LoginName', '').lower()
        if login not in owners or node.get('Tags') or not node.get('InNetworkMap'):
            continue
        node_id = node.get('ID', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', node_id) or node_id in ids:
            raise ValueError('Invalid device identifier.')
        ids.add(node_id)
        assignment = device_owners.get(node_id)
        if assignment and assignment['login'] != login:
            continue
        ips = node.get('TailscaleIPs', [])
        if not 1 <= len(ips) <= 2:
            raise ValueError('Invalid device addresses.')
        clean_ips = []
        for address in ips:
            ip = ipaddress.ip_address(address)
            network = ipaddress.ip_network('100.64.0.0/10' if ip.version == 4 else 'fd7a:115c:a1e0::/48')
            if ip not in network or str(ip) in addresses:
                raise ValueError('Invalid device address.')
            addresses.add(str(ip))
            clean_ips.append(str(ip))
        author = assignment['author'] if assignment else owners[login]
        devices.append({'id': node_id, 'addresses': clean_ips, 'login': login, 'author': author})
    if len(devices) > 64:
        raise ValueError('Too many household devices.')
    return {'version': 1, 'generated_at': time.time() if now is None else now,
            'devices': sorted(devices, key=lambda device: device['id'])}


def main():
    pending = ROOT / 'identity/devices.pending'
    try:
        owners = json.loads((ROOT / 'identity/owners.json').read_text(encoding='utf-8-sig'))
        assignment_path = ROOT / 'identity/device-owners.json'
        device_owners = json.loads(assignment_path.read_text(encoding='utf-8-sig')) if assignment_path.exists() else {}
        validate_device_owners(device_owners)
        result = subprocess.run([TAILSCALE, 'status', '--json'], capture_output=True,
                                timeout=15, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if len(result.stdout) > 1048576:
            raise ValueError('Device status too large.')
        document = build_map(json.loads(result.stdout), owners, device_owners=device_owners)
        with pending.open('w', encoding='utf-8') as stream:
            json.dump(document, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, ROOT / 'identity/devices.json')
        print('Household device map refreshed.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('Household device map refresh failed.')
        return 1
    finally:
        pending.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-owners', type=Path)
    parser.add_argument('--validate-device-owners', type=Path)
    args = parser.parse_args()
    if args.validate_device_owners:
        try:
            validate_device_owners(json.loads(args.validate_device_owners.read_text(encoding='utf-8-sig')))
            print('Device owner assignments are valid.')
        except (OSError, ValueError, TypeError):
            print('Invalid device owner assignments.')
            raise SystemExit(1)
    elif args.validate_owners:
        try:
            owners = json.loads(args.validate_owners.read_text(encoding='utf-8-sig'))
            build_map({'BackendState': 'Running'}, owners)
            print('Owner mapping is valid.')
        except (OSError, ValueError, TypeError):
            print('Invalid owner mapping.')
            raise SystemExit(1)
    else:
        raise SystemExit(main())
