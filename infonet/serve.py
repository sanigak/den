"""DOC: deployment#service"""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'infonet.settings')


def main():
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from waitress import serve
    application = get_wsgi_application()
    if os.environ.get('DEN_LOG_DIR'):
        log = logging.getLogger('den.audit')
        log.disabled = False
        log.propagate = False
        log.setLevel(logging.INFO)
        handler = RotatingFileHandler(Path(os.environ['DEN_LOG_DIR']) / 'requests.log',
                                      maxBytes=2_000_000, backupCount=4, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        log.addHandler(handler)
    serve(application, host='127.0.0.1', port=8082, threads=4, connection_limit=32,
          channel_timeout=30, cleanup_interval=5, max_request_header_size=16384,
          max_request_body_size=262144, expose_tracebacks=False,
          clear_untrusted_proxy_headers=True, ident='Den',
          trusted_proxy='127.0.0.1' if settings.PRODUCTION else None,
          trusted_proxy_headers={'x-forwarded-for'} if settings.PRODUCTION else set(),
          trusted_proxy_count=1,
          url_scheme='https' if settings.PRODUCTION else 'http')


if __name__ == '__main__':
    main()
