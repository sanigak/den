"""DOC: configuration#home-network-access"""
from ipaddress import IPv4Address, IPv4Network
from urllib.parse import urlsplit

PRIVATE_NETWORKS = tuple(IPv4Network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def lan_configuration(origin, subnet):
    try:
        parsed = urlsplit(origin)
        address = IPv4Address(parsed.hostname)
        network = IPv4Network(subnet)
        port = parsed.port
        if (parsed.scheme != 'http' or port is None or not 1024 <= port <= 65535 or port == 8082
                or origin != f'http://{address}:{port}' or str(network) != subnet
                or not any(network.subnet_of(private) for private in PRIVATE_NETWORKS)
                or address not in network or address in (network.network_address, network.broadcast_address)):
            raise ValueError
        return str(address), port, network
    except (ValueError, TypeError):
        raise ValueError('LAN access requires an exact private IPv4 HTTP origin and its canonical private subnet.') from None
