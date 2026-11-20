"""Adapter base class: request execution, decoding and normalization."""
from __future__ import annotations

import json
import re

from core.capabilities import FEATURES, for_family
from session.manager import SessionExpired

MODULE_DEFAULTS = {
    'status': 'internetStatus,deviceStatistics,systemInfo',
    'info': 'systemInfo',
    'clients': 'onlineList,localhost',
    'wifi': 'wifiBasicCfg,wifiAdvCfg,wifiPower',
    'wan': 'lanCfg,wanBasicCfg,wanAdvCfg,internetStatus',
    'lan': 'lanCfg',
    'dhcp': 'dhcpInfo,localhost',
    'bandwidth': 'localhost,onlineList',
    'parental_control': 'parentCtrlList,parentAccessCtrl',
    'port_forward': 'staticIPList,portList,ddns,dmz,upnp',
    'qos': 'localhost,onlineList,blackList',
    'firmware': 'softWare,systemInfo',
    'logs': 'sysTime,systemInfo',
    'system': 'loginAuth,systemInfo',
}


class BaseAdapter:
    family = 'unknown'

    def __init__(self, transport, session, discovery):
        self.transport = transport
        self.session = session
        self.discovery = discovery

    def capability_map(self):
        return for_family(self.family)

    def capability(self, feature):
        return self.capability_map().get(feature)

    def supported(self, feature):
        return self.capability(feature) is not None

    def features(self):
        caps = self.capability_map()
        return {name: bool(caps.get(name)) for name in FEATURES}

    def default_params(self, feature, params=None):
        values = dict(params or {})
        if self.family == 'module_goform' and 'modules' not in values:
            values['modules'] = MODULE_DEFAULTS.get(feature, 'systemInfo')
        return values

    def decode(self, text):
        try:
            return json.loads(text)
        except ValueError:
            pass
        fixed = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', text)
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        try:
            return json.loads(fixed)
        except ValueError:
            return {'raw': text[:2000]}

    def _request(self, cap, feature, params=None, write=False):
        if cap is None:
            raise ValueError('no capability')
        data = None
        if write or cap.method == 'POST':
            data = self.default_params(feature, params)
        query = None if data is not None else self.default_params(feature, params)
        response = self.transport.request(
            cap.endpoint, method=cap.method, data=data, params=query,
            headers=self.session.headers())
        if response.status in (301, 302, 303) or \
                '<!doctype' in response.text[:200].lower():
            raise SessionExpired('session expired or redirected to login')
        self.session.absorb(response)
        return {'endpoint': cap.endpoint, 'method': cap.method,
                'http_status': response.status, 'response': self.decode(response.text)}

    def read(self, feature, params=None):
        return self._request(self.capability(feature), feature, params, write=False)

    def write(self, feature, params=None):
        return self._request(self.capability(feature), feature, params, write=True)

    def normalize(self, feature, action, raw):
        payload = raw.get('response') if isinstance(raw, dict) else raw
        result = {'endpoint': raw.get('endpoint') if isinstance(raw, dict) else None,
                  'http_status': raw.get('http_status') if isinstance(raw, dict) else None}
        if isinstance(payload, dict):
            result.update({k: v for k, v in payload.items()
                           if k not in ('password', 'token', 'sign', 'cookie')})
        else:
            result['value'] = payload
        return result
