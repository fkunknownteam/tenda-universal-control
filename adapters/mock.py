"""Offline simulated transport for demos and tests (no router contact)."""
from __future__ import annotations

from session.manager import Response

SAMPLES = {
    'aes_goahead': {
        '/goform/getStatus': {'model': 'AC10', 'version': 'V16.03.10.10_multi'},
        '/goform/GetSystemStatus': {'adv_firm_ver': 'V16.03.10.10_multi',
                                    'adv_lan_ip': '192.168.0.1', 'adv_run_time': 3600},
        '/goform/getProduct': {'product': 'AC10', 'model': 'AC10'},
        '/goform/getOnlineList': {'list': [{'mac': 'aa:bb:cc:dd:ee:ff',
                                            'ip': '192.168.0.50'}]},
        '/goform/WifiBasicGet': {'ssid': 'SimulatedNet', 'wrlEn': 1},
    },
    'legacy_ecos': {
        '/goform/getStatus': {'model': 'N301', 'version': 'V03.03.16.11',
                              'ssid': 'SimulatedLegacy', 'clientNum': 1},
        '/goform/getWifi': {'ssid': 'SimulatedLegacy', 'channel': 6},
    },
    'module_goform': {
        '/goform/getStatus': {'model': 'AC15', 'version': 'V15.03.06.50_multi',
                              'ssid': 'SimulatedModule', 'onlineList': []},
    },
    'basic_http': {
        '/goform/getStatus': {'model': 'BasicTenda', 'version': 'V1.0'},
    },
    'unknown': {
        '/goform/getStatus': {'model': 'UnknownModel', 'version': 'V0.0.0'},
    },
}


class SimulatedTransport:
    def __init__(self, family='aes_goahead'):
        self.family = family
        self.calls = []
        self.samples = SAMPLES.get(family, SAMPLES['unknown'])

    def request(self, path, method='GET', data=None, params=None, headers=None):
        self.calls.append((method, path, data, params))
        key = path.split('?')[0]
        if key in ('/', '/login.html'):
            if self.family == 'unknown':
                return Response(200, '<html>UnknownRouter</html>', {})
            if self.family == 'aes_goahead':
                return Response(200, '<html>Tenda js/aes/aes.js GOAHEAD_AES_CRYPT="y"</html>', {})
            return Response(200, '<html>Tenda Router</html>', {})
        if key == '/goform/stokCfg' and self.family == 'aes_goahead':
            return Response(200, '{"sign":"SIMULATEDSIGN"}', {})
        if key == '/goform/getstok' and self.family == 'legacy_ecos':
            return Response(200, '{"random":"abcdef1234567890"}', {})
        if 'login/Auth' in key:
            return Response(302, '', {'Location': '/main.html'})
        if key == '/goform/getStatus' and self.family in SAMPLES and self.family != 'unknown':
            sample = self.samples.get('/goform/getStatus', {})
            return Response(200, json_dumps(sample), {})
        payload = self.samples.get(key, {'endpoint': key, 'simulated': True})
        return Response(200, json_dumps(payload), {'Content-Type': 'application/json'})


def json_dumps(obj):
    import json
    return json.dumps(obj)
