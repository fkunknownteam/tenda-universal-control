#!/usr/bin/env python3
"""Universal Tenda control CLI: one interface for many Tenda firmware families."""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.client import TendaUniversal  # noqa: E402

VERSION = '1.0.0'


def build_parser():
    ap = argparse.ArgumentParser(description='Universal Tenda router control')
    ap.add_argument('--host', default=None)
    ap.add_argument('--username', default=None)
    ap.add_argument('--simulate', choices=['aes_goahead', 'legacy_ecos',
                                          'module_goform', 'basic_http', 'unknown'])
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--no-backup', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--json', action='store_true', help='JSON is the default output')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--version', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('diagnose')
    sub.add_parser('capabilities')
    for name in ('status', 'info', 'wan', 'lan', 'firmware', 'logs', 'system',
                 'guest_wifi', 'parental_control', 'port_forward', 'mac_filter',
                 'dhcp_reservation', 'qos', 'diagnostics', 'reboot', 'reset'):
        sub.add_parser(name)

    p = sub.add_parser('clients')
    ps = p.add_subparsers(dest='action', required=True)
    ps.add_parser('list')
    for name in ('block', 'unblock'):
        q = ps.add_parser(name)
        q.add_argument('--mac', required=True)

    p = sub.add_parser('wifi')
    ps = p.add_subparsers(dest='action', required=True)
    ps.add_parser('get')
    q = ps.add_parser('set')
    q.add_argument('--ssid')
    q.add_argument('--password', dest='wifi_password')
    q = ps.add_parser('channel')
    q.add_argument('--value')
    q = ps.add_parser('enable')
    q = ps.add_parser('disable')

    p = sub.add_parser('dhcp')
    ps = p.add_subparsers(dest='action', required=True)
    ps.add_parser('list')
    q = ps.add_parser('reserve')
    q.add_argument('--mac', required=True)
    q.add_argument('--ip', required=True)

    p = sub.add_parser('channel')
    p.add_argument('--value')

    p = sub.add_parser('bandwidth')
    ps = p.add_subparsers(dest='action', required=True)
    ps.add_parser('show')
    q = ps.add_parser('limit')
    q.add_argument('--down', required=True)
    q.add_argument('--up', required=True)

    for name in ('block', 'unblock'):
        q = sub.add_parser(name)
        q.add_argument('--mac', required=True)

    p = sub.add_parser('raw')
    p.add_argument('endpoint')
    p.add_argument('payload', nargs='?')
    p.add_argument('--method', choices=['GET', 'POST'], default='GET')

    for parser in sub.choices.values():
        parser.add_argument('--yes', action='store_true', default=argparse.SUPPRESS)
        parser.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
    return ap


def make_client(opts):
    return TendaUniversal(
        host=opts.host or os.environ.get('TENDA_HOST', '192.168.0.1'),
        username=opts.username or os.environ.get('TENDA_USERNAME', 'admin'),
        password=os.environ.get('TENDA_PASSWORD', ''),
        simulate=opts.simulate)


def main():
    ap = build_parser()
    opts = ap.parse_args()
    if opts.version:
        print(json.dumps({'version': VERSION}))
        return 0
    client = make_client(opts)
    confirm = opts.yes
    backup = not opts.no_backup

    if opts.cmd == 'diagnose':
        result = client.diagnose()
    elif opts.cmd == 'capabilities':
        try:
            client.connect()
            result = {'success': True, 'router': client.router_info(),
                      'action': 'capabilities', 'data': client.capabilities(), 'error': None}
        except Exception as e:
            result = {'success': False, 'error': {'kind': 'error', 'message': str(e)}}
    else:
        action = 'get'
        params = {}
        feature = opts.cmd
        if opts.cmd == 'clients':
            if opts.action == 'list':
                feature = 'clients'
            else:
                feature = opts.action
                action = 'set'
                params = {'mac': opts.mac}
        elif opts.cmd == 'wifi':
            if opts.action == 'get':
                feature = 'wifi'
            elif opts.action == 'set':
                feature = 'wifi'
                action = 'set'
                params = {k: v for k, v in (('ssid', opts.ssid),
                                            ('wrlPwd', opts.wifi_password)) if v is not None}
            elif opts.action == 'channel':
                feature = 'channel'
                if getattr(opts, 'value', None):
                    action, params = 'set', {'adv_channel': opts.value}
            else:
                feature = 'wifi'
                action = 'set'
                params = {'wrlEn': 1 if opts.action == 'enable' else 0}
        elif opts.cmd == 'dhcp':
            if opts.action == 'list':
                feature = 'dhcp'
            else:
                feature = 'dhcp_reservation'
                action = 'set'
                params = {'mac': opts.mac, 'ip': opts.ip}
        elif opts.cmd == 'channel':
            feature = 'channel'
            if getattr(opts, 'value', None):
                action, params = 'set', {'adv_channel': opts.value}
        elif opts.cmd == 'bandwidth':
            feature = 'bandwidth'
            if opts.action == 'limit':
                action, params = 'set', {'downSpeed': opts.down, 'upSpeed': opts.up}
        elif opts.cmd in ('block', 'unblock'):
            action = 'set'
            params = {'mac': opts.mac}
        elif opts.cmd in ('reboot', 'reset'):
            action = 'set'
        elif opts.cmd == 'raw':
            payload = json.loads(opts.payload) if opts.payload else None
            client.connect()
            if opts.method == 'POST' and not confirm:
                result = {'success': False, 'error': {
                    'kind': 'confirmation_required', 'feature': 'raw',
                    'message': 'raw POST requires --yes'}}
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 6
            try:
                response = client.transport.request(
                    opts.endpoint, method=opts.method,
                    data=payload if opts.method == 'POST' else None,
                    params=payload if opts.method == 'GET' else None,
                    headers=client.session.headers())
                raw_result = {'endpoint': opts.endpoint,
                              'http_status': response.status,
                              'response': client.adapter.decode(response.text)}
                result = {'success': True, 'router': client.router_info(),
                          'action': 'raw', 'data': raw_result, 'error': None}
            except Exception as e:
                result = {'success': False, 'error': {'kind': 'error', 'message': str(e)}}
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result['success'] else 1
        result = client.execute(feature, action, params,
                                confirm=confirm, backup_before_write=backup)

    if opts.quiet and result.get('success'):
        print(json.dumps(result.get('data'), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get('success') else (6 if result.get('error', {}).get(
        'kind') == 'confirmation_required' else 4 if result.get('error', {}).get(
        'kind') == 'unsupported' else 1)


if __name__ == '__main__':
    sys.exit(main())
