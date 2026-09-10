"""DOC: household_projects#device-attribution"""
from dataclasses import dataclass
import ipaddress
import json
import math
from pathlib import Path
import re
import time

from django.conf import settings


@dataclass(frozen=True)
class CommentIdentity:
    author: str
    device_id: str


def comment_identity(request):
    path = settings.DEN_DEVICE_MAP_FILE
    if (settings.DEN_ENV == 'lan' or not path or not request.is_secure()
            or request.META.get('HTTP_TAILSCALE_FUNNEL_REQUEST')):
        return None
    try:
        address = str(ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')))
        login = request.META.get('HTTP_TAILSCALE_USER_LOGIN', '').strip().lower()
        with Path(path).open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return None
        document = json.loads(raw)
        age = time.time() - document['generated_at']
        if document['version'] != 1 or not math.isfinite(age) or not -30 <= age <= 300:
            return None
        devices = document['devices']
        if not isinstance(devices, list) or len(devices) > 64:
            return None
        addresses, ids, matched = set(), set(), None
        for device in devices:
            node_id = device['id']
            if (not isinstance(node_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', node_id)
                    or node_id in ids or not isinstance(device['author'], str)
                    or not 1 <= len(device['author']) <= 64 or device['author'] != device['author'].strip()
                    or not device['author'].isprintable() or not isinstance(device['login'], str)
                    or not 1 <= len(device['login']) <= 254 or device['login'] != device['login'].strip().lower()
                    or not device['login'].isprintable()):
                return None
            ids.add(node_id)
            ips = device['addresses']
            if not isinstance(ips, list) or not 1 <= len(ips) <= 2:
                return None
            for ip in ips:
                ip = str(ipaddress.ip_address(ip))
                if ip in addresses:
                    return None
                addresses.add(ip)
                if ip == address and login and login == device['login']:
                    matched = CommentIdentity(device['author'], node_id)
        return matched
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None
