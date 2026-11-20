"""Authentication strategies selected from discovery hints (never brute-forced blindly)."""
from __future__ import annotations

import base64
import hashlib
import urllib.parse

from session.manager import ConnectionFailure, SessionExpired

LOCKOUT_MARKERS = ('lefttimes', 'islocked', 'try again', 'attempts left', 'locked')


def looks_locked(text):
    low = text.lower()
    return any(m in low for m in LOCKOUT_MARKERS) or \
        any(('"errcode":%d' % n) in low.replace(' ', '') for n in range(10, 15))


def accepted(response):
    if response.status == 302:
        return True
    text = response.text[:500]
    low = text.lower().replace(' ', '')
    if looks_locked(text):
        return False
    if '"errcode":' in low and '"errcode":0' not in low:
        return False
    if '<!doctype' in low or 'login.html' in low:
        return False
    if '"errcode":0' in low:
        return True
    return response.status == 200 and len(text.strip()) > 0


class AuthManager:
    def __init__(self, transport, session, password, username='admin'):
        self.transport = transport
        self.session = session
        self.session.username = username
        self.password = password or ''
        self.attempts = 0
        self.stop = False

    def _post(self, path, data):
        response = self.transport.request(path, method='POST', data=data,
                                          headers=self.session.headers())
        self._last_text = response.text
        return response

    def _get(self, path):
        response = self.transport.request(path, headers=self.session.headers())
        self._last_text = response.text
        return response

    def _probe(self, discovery):
        for path in ('/goform/getStatus', '/goform/getWifi', '/goform/getProduct'):
            if path in discovery.get('endpoints_ok', []):
                response = self._get(path)
                if accepted(response):
                    return True
        return False

    def strategy_none(self, discovery):
        if self._probe(discovery):
            self.session.auth_method = 'none'
            self.session.authenticated = True
            return True
        return False

    def strategy_basic(self, discovery):
        token = base64.b64encode(
            ('%s:%s' % (self.session.username, self.password)).encode()).decode()
        self.session.basic_token = token
        if self._probe(discovery):
            self.session.auth_method = 'http_basic'
            self.session.authenticated = True
            return True
        self.session.basic_token = None
        return False

    def strategy_base64(self, discovery):
        value = base64.b64encode(self.password.encode()).decode()
        response = self._post('/login/Auth', {'password': value})
        self.session.absorb(response)
        if accepted(response) and self._probe(discovery):
            self.session.auth_method = 'base64'
            self.session.authenticated = True
            return True
        return False

    def strategy_legacy(self, discovery):
        response = self._get('/goform/getstok?0.1')
        obj = response.json() or {}
        token = obj.get('random')
        if not token:
            return False
        b64 = base64.b64encode(self.password.encode()).decode()
        digest = hashlib.md5((b64 + token).encode()).hexdigest()
        response = self._post('/login/Auth', {'password': digest})
        self.session.absorb(response)
        if accepted(response) and self._probe(discovery):
            self.session.token = token
            self.session.auth_method = 'getstok_md5'
            self.session.authenticated = True
            return True
        return False

    def strategy_aes(self, discovery):
        digest = hashlib.md5(self.password.encode()).hexdigest()
        response = self._post('/login/Auth', {
            'username': self.session.username, 'password': digest})
        self.session.absorb(response)
        if not accepted(response):
            return False
        cfg = self._get('/goform/stokCfg?0.1')
        obj = cfg.json() or {}
        sign = obj.get('sign')
        if not sign:
            return False
        self.session.sign = sign
        self.session.auth_method = 'md5+aes_sign'
        self.session.authenticated = True
        return True

    def strategy_plain(self, discovery):
        response = self._post('/login/Auth', {'password': self.password})
        self.session.absorb(response)
        if accepted(response) and self._probe(discovery):
            self.session.auth_method = 'plain'
            self.session.authenticated = True
            return True
        return False

    def order(self, discovery):
        hints = ' '.join(discovery.get('auth_hints', [])).lower()
        family = discovery.get('api_family', 'unknown')
        if family == 'aes_goahead' or 'aes_sign' in hints:
            return ['aes', 'legacy', 'base64', 'basic', 'plain', 'none']
        if family == 'legacy_ecos' or 'getstok' in hints:
            return ['legacy', 'base64', 'aes', 'basic', 'plain', 'none']
        if 'http_basic' in hints:
            return ['basic', 'base64', 'plain', 'none']
        return ['none', 'base64', 'legacy', 'aes', 'basic', 'plain']

    def authenticate(self, discovery):
        attempts = []
        for name in self.order(discovery):
            if self.stop or self.attempts >= 8:
                break
            self.attempts += 1
            try:
                ok = getattr(self, 'strategy_' + name)(discovery)
            except (ConnectionFailure, SessionExpired):
                raise
            except Exception as e:
                ok = False
                attempts.append('%s: %s' % (name, type(e).__name__))
            if ok:
                return {'method': self.session.auth_method, 'attempts': attempts}
            attempts.append('%s: rejected' % name)
            # Never keep guessing into a router-side lockout.
            last = getattr(self, '_last_text', '')
            if looks_locked(last):
                self.stop = True
                attempts.append('lockout detected; stopping')
                break
        return {'method': None, 'attempts': attempts}
