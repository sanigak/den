"""DOC: security#requests-and-limits"""
from datetime import date, timedelta
from ipaddress import ip_address
import logging
import math
import time
import uuid

from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent, TooManyFilesSent
from django.conf import settings
from django.db import OperationalError, transaction
from django.http import HttpResponse, HttpResponseNotAllowed
from django.utils.deprecation import MiddlewareMixin

from .models import SecurityState

MIN_DATE = date(1900, 1, 1)
MAX_DATE = date(2100, 12, 31)
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; "
       "object-src 'none'; frame-ancestors 'none'")


class InputError(ValueError):
    pass


class LimitError(Exception):
    def __init__(self, retry=60):
        self.retry = max(1, math.ceil(retry))


def error_response(status, message=None):
    messages = {400: 'Invalid request.', 403: 'Request not permitted.', 404: 'Not found.',
                413: 'Request too large.', 429: 'Please wait before trying again.',
                500: 'Unable to complete the request.', 503: 'Temporarily unavailable.'}
    return HttpResponse(message or messages[status], status=status, content_type='text/plain; charset=utf-8')


def bad_request(request, exception):
    return error_response(400)


def forbidden(request, exception):
    return error_response(403)


def not_found(request, exception):
    return error_response(404)


def server_error(request):
    return error_response(500)


def csrf_failure(request, reason=''):
    category = 'origin' if reason.startswith('Origin') else ('referer' if reason.startswith('Referer') else 'token')
    logging.getLogger('den.audit').info('csrf_rejected category=%s', category)
    return error_response(403)


def limited(exc):
    response = error_response(429)
    response['Retry-After'] = str(exc.retry)
    return response


def valid_date(value):
    if not isinstance(value, date) or not MIN_DATE <= value <= MAX_DATE:
        raise InputError('Dates must be between 1900 and 2100.')
    return value


def parse_date(value):
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return valid_date(parsed)
    except (ValueError, TypeError):
        raise InputError('Enter a valid date between 1900 and 2100.') from None


def positive_int(value, maximum):
    text = str(value)
    if not text.isascii() or not text.isdecimal() or len(text) > 19:
        raise InputError('Enter a valid positive number.')
    number = int(text)
    if not 1 <= number <= maximum:
        raise InputError('Number is outside the allowed range.')
    return number


def valid_range(start, days):
    valid_date(start)
    days = positive_int(days, 365)
    valid_date(start + timedelta(days=days - 1))
    return days


def ensure_capacity(model, additional, cap):
    if model.objects.count() + additional > cap:
        raise InputError('The list is full. Remove entries before adding more.')


def consume_write(heavy=False, now=None):
    now = time.time() if now is None else now
    window = int(now // 60)
    with transaction.atomic():
        state = SecurityState.objects.get(pk=1)
        if state.minute != window:
            state.minute, state.writes, state.heavy = window, 0, 0
        if state.writes >= 60 or (heavy and state.heavy >= 6):
            raise LimitError(60 - now % 60)
        state.writes += 1
        state.heavy += int(heavy)
        state.save(update_fields=['minute', 'writes', 'heavy'])


def acquire_ai(now=None):
    now = time.time() if now is None else now
    day = int(now // 86400)
    with transaction.atomic():
        state = SecurityState.objects.get(pk=1)
        if state.ai_until > now:
            raise LimitError(state.ai_until - now)
        if state.ai_day != day:
            state.ai_day, state.ai_attempts = day, 0
        if state.ai_attempts >= 20:
            raise LimitError(86400 - now % 86400)
        token = uuid.uuid4().hex
        state.ai_attempts += 1
        state.ai_owner, state.ai_until = token, now + 35
        state.save(update_fields=['ai_day', 'ai_attempts', 'ai_owner', 'ai_until'])
    return token


def release_ai(token):
    SecurityState.objects.filter(pk=1, ai_owner=token).update(ai_owner='', ai_until=0)


# DOC: security#home-network-access
class LanBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            peer = ip_address(request.META.get('REMOTE_ADDR', ''))
            allowed = peer in settings.DEN_LAN_NETWORK
        except (ValueError, TypeError):
            allowed = False
        if (not allowed or request.META.get('HTTP_HOST') != f'{settings.DEN_LAN_HOST}:{settings.DEN_LAN_PORT}'):
            response = error_response(403)
            response['Cache-Control'] = 'no-store'
            return response
        for key in list(request.META):
            if key.startswith(('HTTP_TAILSCALE_', 'HTTP_X_FORWARDED_')) or key == 'HTTP_FORWARDED':
                request.META.pop(key)
        return self.get_response(request)


class EnvelopeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        try:
            request.get_host()
            size = request.META.get('CONTENT_LENGTH', '')
            if request.method not in ('GET', 'HEAD', 'POST'):
                response = HttpResponseNotAllowed(['GET', 'HEAD', 'POST'])
            elif size and (not size.isdecimal() or int(size) > 262144):
                response = error_response(413)
            elif request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and len(request.body) > 262144:
                response = error_response(413)
            elif request.method == 'POST' and request.FILES:
                response = error_response(400, 'File uploads are not supported.')
            else:
                response = self.get_response(request)
        except RequestDataTooBig:
            response = error_response(413)
        except (TooManyFieldsSent, TooManyFilesSent):
            response = error_response(400)
        response['Content-Security-Policy'] = CSP
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        response['Cache-Control'] = 'no-store' if not request.path.startswith('/static/') else 'public, max-age=3600'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        logging.getLogger('den.audit').info('status=%d elapsed_ms=%d', response.status_code,
                                           int((time.monotonic() - started) * 1000))
        return response


class WriteBudgetMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'POST':
            return None
        try:
            consume_write(request.resolver_match.url_name in ('meal_regenerate', 'meal_skip'))
        except LimitError as exc:
            return limited(exc)
        except OperationalError:
            return error_response(503)

    def process_exception(self, request, exception):
        if isinstance(exception, InputError):
            return error_response(400, str(exception))
        if isinstance(exception, LimitError):
            return limited(exception)
        if isinstance(exception, OperationalError):
            return error_response(503)
