"""HTTP transport and session state shared by all adapters."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ConnectionFailure(Exception):
    pass


class SessionExpired(Exception):
    pass


class Response:
    def __init__(self, status, text, headers):
        self.status = status
        self.text = text
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError:
            return None

    def __repr__(self):
        return '<Response %d len=%d>' % (self.status, len(self.text))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Transport:
    def __init__(self, host, timeout=8):
        self.host = str(host).replace('http://', '').replace('https://', '').rstrip('/')
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, method='GET', data=None, params=None, headers=None):
        url = 'http://' + self.host + '/' + str(path).lstrip('/')
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        hdrs = {'User-Agent': 'tenda-universal/1.0', 'Accept': '*/*'}
        if headers:
            hdrs.update(headers)
        body = None
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
            hdrs.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        elif isinstance(data, (bytes, str)):
            body = data.encode() if isinstance(data, str) else data
            hdrs.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                return Response(r.status, r.read().decode('utf-8', 'replace'), dict(r.headers))
        except urllib.error.HTTPError as e:
            return Response(e.code, e.read().decode('utf-8', 'replace'), dict(e.headers))
        except urllib.error.URLError as e:
            raise ConnectionFailure('router unreachable: %s' % e.reason)
        except Exception as e:
            raise ConnectionFailure('request failed: %s' % e)


class Session:
    def __init__(self):
        self.cookies = {}
        self.basic_token = None
        self.token = None
        self.sign = None
        self.auth_method = 'none'
        self.username = 'admin'
        self.authenticated = False

    def headers(self, extra=None):
        h = dict(extra or {})
        if self.cookies:
            h['Cookie'] = '; '.join('%s=%s' % kv for kv in self.cookies.items())
        if self.basic_token:
            h['Authorization'] = 'Basic ' + self.basic_token
        return h

    def absorb(self, response):
        raw = response.headers.get('set-cookie', '')
        for part in raw.split(','):
            chunk = part.split(';')[0].strip()
            if '=' in chunk:
                k, v = chunk.split('=', 1)
                self.cookies[k.strip()] = v.strip()

    def public(self):
        return {'auth_method': self.auth_method, 'username': self.username,
                'authenticated': self.authenticated,
                'cookie_names': sorted(self.cookies.keys()),
                'has_token': bool(self.token), 'sign_length': len(self.sign or '')}
