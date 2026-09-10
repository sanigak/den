"""DOC: deployment#service"""
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import os
from pathlib import Path
import threading

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'infonet.settings')


def serve_application():
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from waitress import serve
    application = get_wsgi_application()
    if os.environ.get('DEN_LOG_DIR'):
        log = logging.getLogger('den.audit')
        log.disabled = False
        log.propagate = False
        log.setLevel(logging.INFO)
        filename = 'requests-lan.log' if settings.LAN else 'requests.log'
        handler = RotatingFileHandler(Path(os.environ['DEN_LOG_DIR']) / filename,
                                      maxBytes=2_000_000, backupCount=4, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        log.addHandler(handler)
    proxy = ({'trusted_proxy': '127.0.0.1', 'trusted_proxy_headers': {'x-forwarded-for'},
              'trusted_proxy_count': 1} if settings.PRODUCTION else {})
    serve(application, host=settings.DEN_LAN_HOST if settings.LAN else '127.0.0.1',
          port=settings.DEN_LAN_PORT if settings.LAN else 8082, threads=4, connection_limit=32,
          channel_timeout=30, cleanup_interval=5, max_request_header_size=16384,
          max_request_body_size=262144, expose_tracebacks=False,
          clear_untrusted_proxy_headers=True, ident='Den',
          url_scheme='https' if settings.PRODUCTION else 'http', **proxy)


# DOC: deployment#home-network-access
def lan_worker():
    os.environ['DEN_ENV'] = 'lan'
    serve_application()


def maintain_lan(stop):
    context = multiprocessing.get_context('spawn')
    while not stop.is_set():
        process = context.Process(target=lan_worker, name='Den LAN', daemon=True)
        try:
            process.start()
            while not stop.wait(1) and process.is_alive():
                pass
        except OSError:
            logging.getLogger('den.audit').error('lan_listener_start_failed')
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                process.close()
        if stop.wait(10):
            return


def main():
    from django.conf import settings
    stop = threading.Event()
    worker = None
    if settings.PRODUCTION and settings.DEN_LAN_ORIGIN:
        worker = threading.Thread(target=maintain_lan, args=(stop,), name='Den LAN supervisor', daemon=True)
        worker.start()
    try:
        serve_application()
    finally:
        stop.set()
        if worker:
            worker.join(timeout=15)


if __name__ == '__main__':
    main()
