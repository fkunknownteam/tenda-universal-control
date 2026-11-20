"""TendaUniversal: discovery → auth → adapter → normalized response."""
from __future__ import annotations

from adapters import make_adapter
from adapters.mock import SimulatedTransport
from auth.strategies import AuthManager
from core.capabilities import FEATURES
from core import response
from discovery.detect import discover
from session.manager import ConnectionFailure, Session, SessionExpired, Transport

WRITE_ACTIONS = {
    'wifi': 'wifi_set',
    'channel': 'channel_set',
    'bandwidth': 'bandwidth_set',
}


class TendaUniversal:
    def __init__(self, host='192.168.0.1', password='', username='admin',
                 timeout=8, simulate=None, transport=None):
        self.cfg = {'host': host, 'username': username, 'timeout': timeout}
        self.password = password
        self.simulate = simulate
        self.session = Session()
        self.session.username = username
        self.transport = transport or (SimulatedTransport(simulate or 'aes_goahead')
                                       if simulate else Transport(host, timeout))
        self.discovery = {}
        self.auth_result = {'method': None, 'attempts': []}
        self.adapter = None
        self.connected = False

    def router_info(self):
        return {
            'vendor': self.discovery.get('vendor') or 'Tenda',
            'model': self.discovery.get('model'),
            'firmware': self.discovery.get('firmware'),
            'api_family': self.discovery.get('api_family') or 'unknown',
        }

    def connect(self):
        if self.connected:
            return self
        self.discovery = discover(self.transport, self.session)
        if not self.discovery.get('reachable') and not self.simulate:
            raise ConnectionFailure(self.discovery['notes'][0] if self.discovery.get('notes')
                                    else 'router unreachable')
        if self.simulate:
            self.session.auth_method = 'simulated'
            self.session.authenticated = True
            self.auth_result = {'method': 'simulated', 'attempts': []}
        elif self.discovery.get('reachable'):
            manager = AuthManager(self.transport, self.session, self.password,
                                  self.cfg['username'])
            self.auth_result = manager.authenticate(self.discovery)
            if self.auth_result['method']:
                self.discovery['auth_hints'].append(self.auth_result['method'])
        family = self.simulate or self.discovery.get('api_family') or 'unknown'
        self.adapter = make_adapter(self.transport, self.session, self.discovery,
                                    simulate=self.simulate)
        self.connected = True
        return self

    def capabilities(self):
        self.connect()
        return self.adapter.features()

    def execute(self, feature, action='get', params=None, confirm=False,
                backup_before_write=True):
        """Single entry point for the app. Always returns the normalized envelope."""
        try:
            self.connect()
            write_action = action in ('set', 'add', 'remove', 'start', 'stop')
            target = WRITE_ACTIONS.get(feature, feature) if write_action else feature
            cap = self.adapter.capability(target)
            if cap is None:
                return response.error(
                    feature, 'unsupported',
                    '%s is not available on this router/firmware.' % feature,
                    self.router_info(), feature)
            if (write_action or cap.write) and not confirm:
                return response.error(
                    feature, 'confirmation_required',
                    '%s changes router state; re-run with confirmation.' % feature,
                    self.router_info(), feature,
                    {'destructive': cap.destructive})
            meta = {'endpoint': cap.endpoint, 'method': cap.method,
                    'write': bool(write_action or cap.write),
                    'destructive': cap.destructive,
                    'auth_method': self.session.auth_method}
            if cap.destructive and backup_before_write:
                backup = self.adapter.capability('config_backup')
                if backup:
                    try:
                        self.adapter.read('config_backup')
                        meta['backup_performed'] = True
                    except Exception as e:
                        meta['backup_error'] = type(e).__name__
            call = self.adapter.write if (write_action or cap.write) else self.adapter.read
            try:
                raw = call(target, params)
            except SessionExpired:
                manager = AuthManager(self.transport, self.session, self.password,
                                      self.cfg['username'])
                manager.authenticate(self.discovery)
                raw = call(target, params)
            data = self.adapter.normalize(target, action, raw)
            return response.success(feature, data, self.router_info(), meta=meta)
        except ConnectionFailure as e:
            return response.error(feature, 'unreachable', str(e), self.router_info(), feature)
        except Exception as e:
            return response.error(feature, 'error', '%s: %s' % (type(e).__name__, e),
                                  self.router_info(), feature)

    def diagnose(self):
        try:
            self.connect()
        except Exception as e:
            return {'reachable': False, 'error': str(e)}
        caps = self.capabilities()
        return {
            'reachable': True,
            'vendor': self.router_info()['vendor'],
            'model': self.router_info()['model'],
            'firmware': self.router_info()['firmware'],
            'authentication': self.session.public(),
            'auth_method': self.auth_result.get('method'),
            'auth_attempts': self.auth_result.get('attempts', []),
            'api_family': self.router_info()['api_family'],
            'capabilities': caps,
            'unsupported_features': [f for f, ok in caps.items() if not ok],
            'successful_endpoints': self.discovery.get('endpoints_ok', []),
            'failed_endpoints': self.discovery.get('endpoints_failed', []),
            'notes': self.discovery.get('notes', []),
        }
