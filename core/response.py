"""Stable response envelope and redaction for the universal Tenda API."""
from __future__ import annotations

import re

SECRET_KEY = re.compile(
    r'(password|passwd|pwd|psk|secret|token|sign|cookie|private|credential)',
    re.IGNORECASE,
)
SAFE_KEYS = {'key', 'keys', 'top_keys', 'sign_length', 'auth_method', 'features'}


def redact(value, key=None):
    if isinstance(value, dict):
        return {k: ('<redacted>' if SECRET_KEY.search(str(k)) and str(k) not in SAFE_KEYS
                    else redact(v, str(k))) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, key) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)(Cookie|Authorization)\s*[:=]\s*[^\s;,]+',
                       r'\1=<redacted>', value)
        return '<redacted>' if key and SECRET_KEY.search(key) and key not in SAFE_KEYS else value
    return value


def success(action, data, router, *, meta=None):
    return {
        'success': True,
        'router': router,
        'action': action,
        'data': redact(data),
        'error': None,
        'meta': redact(meta or {}),
    }


def error(action, kind, message, router=None, feature=None, details=None):
    return {
        'success': False,
        'router': router or {'vendor': 'Tenda', 'model': None, 'firmware': None},
        'action': action,
        'data': None,
        'error': {
            'kind': kind,
            'feature': feature,
            'message': message,
            'details': redact(details or {}),
        },
    }
