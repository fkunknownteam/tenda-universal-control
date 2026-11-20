"""Safe, read-only router discovery: vendor, model, firmware, API family, auth hints."""
from __future__ import annotations

import json
import re

from session.manager import ConnectionFailure

PROBES = [
    ('/', None),
    ('/login.html', None),
    ('/goform/getStatus', None),
    ('/goform/getProduct', None),
    ('/goform/getstok', None),
    ('/goform/stokCfg', None),
    ('/goform/getWifi', None),
    ('/goform/getSysTools', None),
    ('/goform/goform_get_cmd_process', {'cmd': 'system_info'}),
]

MODEL_KEYS = ('model', 'Model', 'modelName', 'deviceName', 'Product', 'product',
              'devName', 'DeviceName', 'DeviceModel')
FW_KEYS = ('firmware', 'Firmware', 'version', 'Version', 'fwVer', 'adv_firm_ver',
           'curVersion', 'SwVersion', 'sysver', 'softVer', 'firmware_version')


def shape(text):
    """Return only the shape of a response, never its values."""
    try:
        obj = json.loads(text)
    except ValueError:
        m = re.search(r'([A-Za-z0-9_]+)\s*:', text)
        return {'format': 'html_or_js', 'first_key': m.group(1) if m else None}
    if isinstance(obj, dict):
        return {'format': 'json', 'keys': sorted(str(k) for k in obj.keys())[:30]}
    if isinstance(obj, list):
        return {'format': 'json_list', 'length': len(obj)}
    return {'format': 'json', 'type': type(obj).__name__}


def find_value(obj, keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] not in (None, ''):
            return str(obj[key])[:80]
    return None


def deep_find(obj, keys):
    found = find_value(obj, keys)
    if found:
        return found
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, dict):
                hit = deep_find(value, keys)
                if hit:
                    return hit
    return None


def discover(transport, session):
    """Probe safe endpoints only. Returns a discovery report."""
    report = {
        'vendor': None, 'model': None, 'firmware': None,
        'api_family': 'unknown', 'auth_hints': [], 'auth_method': None,
        'endpoints_ok': [], 'endpoints_failed': [], 'shapes': {},
        'notes': [], 'reachable': False,
    }
    responses = {}
    for path, params in PROBES:
        try:
            response = transport.request(path, params=params,
                                         headers=session.headers())
        except ConnectionFailure as e:
            report['notes'].append(str(e))
            break
        responses[path] = response
        if response.status == 200 and response.text.strip():
            report['endpoints_ok'].append(path)
            report['shapes'][path] = shape(response.text)
        else:
            report['endpoints_failed'].append({'path': path, 'status': response.status})
    if not responses:
        return report
    report['reachable'] = True

    home = next((responses[p].text for p in ('/', '/login.html') if p in responses), '')
    blob = home + ' '.join(r.text[:2000] for r in responses.values())
    if 'Tenda' in blob or 'tenda' in blob.lower() or 'GOAHEAD' in blob:
        report['vendor'] = 'Tenda'

    # Auth hints and API family.
    stok_cfg = responses.get('/goform/stokCfg')
    sign = stok_cfg.json().get('sign') if stok_cfg and stok_cfg.json() else None
    getstok = responses.get('/goform/getstok')
    random_token = getstok.json().get('random') if getstok and getstok.json() else None
    if sign and ('aes' in blob.lower() or 'GOAHEAD_AES_CRYPT' in blob):
        report['api_family'] = 'aes_goahead'
        report['auth_hints'].append('md5_login+aes_sign')
    elif random_token:
        report['api_family'] = 'legacy_ecos'
        report['auth_hints'].append('getstok+md5(base64+token)')
    elif 'WWW-Authenticate' in ' '.join(r.headers.get('www-authenticate', '')
                                        for r in responses.values()):
        report['api_family'] = 'basic_http'
        report['auth_hints'].append('http_basic')
    elif (report['vendor'] == 'Tenda' and
          ('modules' in blob or any('/goform/getStatus' in p
                                    for p in report['endpoints_ok']))):
        report['api_family'] = 'module_goform'
        report['auth_hints'].append('base64_login_or_open')
    elif report['vendor'] == 'Tenda':
        report['api_family'] = 'basic_http'
        report['auth_hints'].append('unknown_login')
    else:
        report['notes'].append('vendor not confirmed; using unknown adapter')

    # Model and firmware from any JSON response.
    for r in responses.values():
        obj = r.json()
        if not isinstance(obj, dict):
            continue
        report['model'] = report['model'] or deep_find(obj, MODEL_KEYS)
        report['firmware'] = report['firmware'] or deep_find(obj, FW_KEYS)
        if report['model'] and report['firmware']:
            break
    if not report['model']:
        m = re.search(r'(?:model|Model)[^A-Za-z0-9]{0,8}([A-Za-z0-9_-]{3,20})', home)
        report['model'] = m.group(1) if m else None
    if not report['firmware']:
        m = re.search(r'V\d{2}\.\d{2}\.\d{2}\.\d+', blob)
        report['firmware'] = m.group(0) if m else None

    report['notes'].append('discovery used read-only requests only')
    return report
