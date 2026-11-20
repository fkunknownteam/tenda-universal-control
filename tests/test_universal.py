"""Mock-based tests for every layer. No physical router is contacted."""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from adapters.mock import SimulatedTransport  # noqa: E402
from auth.strategies import AuthManager, looks_locked  # noqa: E402
from core.capabilities import FEATURES, for_family  # noqa: E402
from core.client import TendaUniversal  # noqa: E402
from session.manager import SessionExpired, Transport  # noqa: E402

FAMILIES = ('aes_goahead', 'legacy_ecos', 'module_goform', 'basic_http', 'unknown')


class FakeTransport:
    def __init__(self, family, invalid=False, expire_once=False):
        self.family = family
        self.invalid = invalid
        self.expire_once = expire_once
        self.used = False
        self.calls = []

    def request(self, path, method='GET', data=None, params=None, headers=None):
        key = path.split('?')[0]
        self.calls.append((method, key, data, params))
        if key in ('/', '/login.html'):
            if self.family == 'unknown':
                return R(200, '<html>UnknownRouter</html>')
            html = '<html>Tenda Router js/aes/aes.js GOAHEAD_AES_CRYPT="y"</html>'
            return R(200, html)
        if key == '/goform/stokCfg':
            if self.family == 'aes_goahead':
                return R(200, '{"sign":"SIMULATEDSIGN16"}')
            return R(404, 'not found')
        if key == '/goform/getstok':
            if self.family == 'legacy_ecos':
                return R(200, '{"random":"abcdef1234567890"}')
            return R(404, 'not found')
        if key == '/login/Auth' and method == 'POST':
            if self.invalid:
                return R(200, '{"errCode":1}')
            return R(302, '', {'Location': '/main.html'})
        if key == '/goform/goform_get_cmd_process':
            if self.family == 'basic_http':
                return R(200, json.dumps({'model': 'Basic', 'version': 'V1.0'}))
            return R(404, 'not found')
        if key.startswith('/goform/') and self.family == 'unknown':
            return R(404, 'not found')
        if key in ('/goform/getStatus', '/goform/getWifi', '/goform/getProduct',
                   '/goform/GetSystemStatus', '/goform/getOnlineList',
                   '/goform/WifiBasicGet', '/goform/getWAN', '/goform/getNAT'):
            if self.family == 'basic_http':
                return R(404, 'not found')
            if self.invalid:
                return R(200, '<!DOCTYPE html><html><login>')
            if self.expire_once and not self.used:
                self.used = True
                return R(302, '', {'Location': '/login.html'})
            if key == '/goform/getStatus':
                models = {'aes_goahead': ('AC10', 'V16.03.10.10_multi'),
                          'legacy_ecos': ('N301', 'V03.03.16.11'),
                          'module_goform': ('AC15', 'V15.03.06.50_multi'),
                          'basic_http': ('Basic', 'V1.0'),
                          'unknown': ('Unknown', 'V0.0')}
                model, version = models[self.family]
                return R(200, json.dumps({'model': model, 'version': version,
                                          'ssid': 'SimNet', 'clientNum': 1}))
            return R(200, json.dumps({'ssid': 'SimNet', 'channel': 6, 'list': []}))
        if key == '/goform/sysReboot':
            return R(200, '{"errCode":0}')
        return R(404, 'not found')


class R:
    def __init__(self, status, text, headers=None):
        self.status = status
        self.text = text
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError:
            return None


class UniversalTests(unittest.TestCase):
    def client(self, family, **kwargs):
        c = TendaUniversal(simulate=None, transport=FakeTransport(family, **kwargs))
        c.connect()
        return c

    def test_auth_and_model_detection_aes(self):
        c = self.client('aes_goahead')
        self.assertEqual(c.discovery['api_family'], 'aes_goahead')
        self.assertEqual(c.discovery['model'], 'AC10')
        self.assertEqual(c.discovery['firmware'], 'V16.03.10.10_multi')
        self.assertIn('aes', c.auth_result['method'])
        self.assertEqual(c.router_info()['vendor'], 'Tenda')

    def test_legacy_auth(self):
        c = self.client('legacy_ecos')
        self.assertEqual(c.discovery['api_family'], 'legacy_ecos')
        self.assertIn('getstok', c.auth_result['method'])
        self.assertEqual(c.discovery['model'], 'N301')

    def test_module_family_open_detection(self):
        c = self.client('module_goform')
        self.assertEqual(c.discovery['api_family'], 'module_goform')
        self.assertEqual(c.session.auth_method, 'none')

    def test_basic_family_detection(self):
        c = self.client('basic_http')
        self.assertEqual(c.discovery['api_family'], 'basic_http')

    def test_unknown_model_safe_mode(self):
        c = self.client('unknown')
        self.assertEqual(c.discovery['api_family'], 'unknown')
        caps = c.capabilities()
        self.assertTrue(caps['status'])
        self.assertFalse(caps.get('qos', False))
        result = c.execute('qos')
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['kind'], 'unsupported')

    def test_invalid_credentials(self):
        c = TendaUniversal(transport=FakeTransport('aes_goahead', invalid=True))
        c.connect()
        self.assertIsNone(c.auth_result['method'])
        self.assertFalse(c.session.authenticated)

    def test_unreachable(self):
        def boom(*a, **kw):
            from session.manager import ConnectionFailure
            raise ConnectionFailure('unreachable: test')
        transport = FakeTransport('aes_goahead')
        transport.request = boom
        result = TendaUniversal(transport=transport).execute('status')
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['kind'], 'unreachable')

    def test_response_parsing_js_object(self):
        c = self.client('aes_goahead')
        parsed = c.adapter.decode('{model:"AC10", list:[1,2,],}')
        self.assertEqual(parsed['model'], 'AC10')

    def test_status_clients_wifi(self):
        c = self.client('aes_goahead')
        for feature in ('status', 'clients', 'wifi'):
            result = c.execute(feature)
            self.assertTrue(result['success'], result)
            self.assertEqual(result['action'], feature)
            self.assertIsInstance(result['data'], dict)

    def test_reboot_safety(self):
        c = self.client('aes_goahead')
        denied = c.execute('reboot', 'set')
        self.assertFalse(denied['success'])
        self.assertEqual(denied['error']['kind'], 'confirmation_required')
        allowed = c.execute('reboot', 'set', confirm=True)
        self.assertTrue(allowed['success'])

    def test_unsupported_feature(self):
        c = self.client('aes_goahead')
        result = c.execute('diagnostics')
        self.assertFalse(result['success'])
        self.assertEqual(result['error']['feature'], 'diagnostics')

    def test_session_expiry(self):
        from adapters import make_adapter
        from session.manager import Session
        transport = FakeTransport('aes_goahead', expire_once=True)
        session = Session()
        session.authenticated = True
        adapter = make_adapter(transport, session, {'api_family': 'aes_goahead'})
        with self.assertRaises(SessionExpired):
            adapter.read('status')

    def test_diagnose_redaction(self):
        c = self.client('aes_goahead')
        report = c.diagnose()
        blob = json.dumps(report)
        self.assertNotIn('SIMULATEDSIGN16', blob)
        self.assertTrue(report['reachable'])
        self.assertIn('unsupported_features', report)

    def test_simulated_transport(self):
        c = TendaUniversal(simulate='legacy_ecos')
        result = c.execute('status')
        self.assertTrue(result['success'])
        self.assertEqual(result['router']['model'], 'N301')

    def test_lockout_marker(self):
        self.assertTrue(looks_locked('{"leftTimes":2}'))
        self.assertFalse(looks_locked('{"errCode":0}'))

    def test_capability_maps(self):
        for family in FAMILIES:
            caps = for_family(family)
            self.assertIn('status', caps)
        for family in ('aes_goahead', 'legacy_ecos', 'module_goform',
                       'basic_http'):
            self.assertIn('reboot', for_family(family))
        self.assertIn('config_backup', for_family('aes_goahead'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
