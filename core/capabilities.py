"""Per-family capability maps. Only endpoints observed in real Tenda firmware."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    endpoint: str
    method: str = 'GET'
    params: tuple = ()
    write: bool = False
    destructive: bool = False


def C(endpoint, method='GET', params=(), write=False, destructive=False):
    return Capability(endpoint, method, tuple(params), write, destructive)


# AES-era GoAhead (AC/AX/Nova, V16.x): see routerctl-ac10 discovery.
AES = {
    'status': C('/goform/GetSystemStatus'),
    'info': C('/goform/getProduct'),
    'clients': C('/goform/getOnlineList'),
    'wifi': C('/goform/WifiBasicGet'),
    'wifi_set': C('/goform/WifiBasicSet', 'POST',
                  ('ssid', 'wrlPwd', 'wrlEn'), True, True),
    'wan': C('/goform/getWanParameters'),
    'lan': C('/goform/AdvGetLanIp'),
    'dhcp': C('/goform/GetIpMacBind'),
    'reboot': C('/goform/SysToolReboot', 'POST', ('action',), True, True),
    'reset': C('/goform/SysToolRestoreSet', 'POST', ('action',), True, True),
    'channel': C('/goform/WifiRadioGet'),
    'channel_set': C('/goform/WifiRadioSet', 'POST', ('adv_channel',), True, True),
    'bandwidth': C('/goform/GetQos'),
    'bandwidth_set': C('/goform/SetQos', 'POST', ('upSpeed', 'downSpeed'), True, True),
    'block': C('/goform/setBlackRule', 'POST', ('mac',), True, True),
    'unblock': C('/goform/delBlackRule', 'POST', ('mac',), True, True),
    'guest_wifi': C('/goform/WifiGuestGet'),
    'parental_control': C('/goform/GetParentCtrlList'),
    'port_forward': C('/goform/GetVirtualServerCfg'),
    'mac_filter': C('/goform/getMacFilterCfg'),
    'dhcp_reservation': C('/goform/GetIpMacBind'),
    'qos': C('/goform/GetQos'),
    'firmware': C('/goform/SysToolGetUpgrade'),
    'logs': C('/goform/GetSySLogCfg'),
    'system': C('/goform/GetSysTools'),
    'config_backup': C('/cgi-bin/DownloadCfg/RouterCfm.cfg'),
    'diagnostics': None,
}

# Legacy eCos plaintext goform (V03.03.16.11 and similar).
LEGACY = {
    'status': C('/goform/getStatus'),
    'info': C('/goform/getStatus'),
    'clients': C('/goform/getStatus'),
    'wifi': C('/goform/getWifi'),
    'wifi_set': C('/goform/setWifi', 'POST', ('ssid', 'wrlPassword'), True, True),
    'wan': C('/goform/getWAN'),
    'lan': C('/goform/getStatus'),
    'dhcp': C('/goform/getStatus'),
    'reboot': C('/goform/sysReboot', 'POST', ('module1', 'action'), True, True),
    'reset': C('/goform/sysRestore', 'POST', ('module1', 'action'), True, True),
    'channel': C('/goform/getWifi'),
    'bandwidth': C('/goform/getQos'),
    'block': C('/goform/setBlackRule', 'POST', ('mac',), True, True),
    'unblock': C('/goform/delBlackRule', 'POST', ('mac',), True, True),
    'guest_wifi': C('/goform/getWifi'),
    'parental_control': C('/goform/getParentControl'),
    'port_forward': C('/goform/getNAT'),
    'mac_filter': C('/goform/getMacFilterCfg'),
    'dhcp_reservation': C('/goform/getIpMacBind'),
    'qos': C('/goform/getQos'),
    'firmware': C('/goform/getSysTools'),
    'logs': C('/goform/getSysTools'),
    'system': C('/goform/getSysTools'),
    'config_backup': None,
    'diagnostics': None,
}

# Older AC/N-series module-style UI: /goform/getStatus?modules=...
MODULE = {
    'status': C('/goform/getStatus', 'GET', ('modules',)),
    'info': C('/goform/getStatus', 'GET', ('modules',)),
    'clients': C('/goform/getStatus', 'GET', ('modules',)),
    'wifi': C('/goform/getWifi', 'GET', ('modules',)),
    'wifi_set': C('/goform/setWifi', 'POST', ('ssid', 'wrlPwd'), True, True),
    'wan': C('/goform/getWAN', 'GET', ('modules',)),
    'lan': C('/goform/getWAN', 'GET', ('modules',)),
    'dhcp': C('/goform/getNAT', 'GET', ('modules',)),
    'reboot': C('/goform/sysReboot', 'POST', (), True, True),
    'reset': C('/goform/sysRestore', 'POST', (), True, True),
    'channel': C('/goform/getWifi', 'GET', ('modules',)),
    'bandwidth': C('/goform/getQos', 'GET', ('modules',)),
    'block': C('/goform/setBlackRule', 'POST', ('mac',), True, True),
    'unblock': C('/goform/delBlackRule', 'POST', ('mac',), True, True),
    'parental_control': C('/goform/getParentControl', 'GET', ('modules',)),
    'port_forward': C('/goform/getNAT', 'GET', ('modules',)),
    'qos': C('/goform/getQos', 'GET', ('modules',)),
    'firmware': C('/goform/getSysTools', 'GET', ('modules',)),
    'logs': C('/goform/getSysTools', 'GET', ('modules',)),
    'system': C('/goform/getSysTools', 'GET', ('modules',)),
    'config_backup': None,
    'diagnostics': None,
}

# Minimal/basic HTTP management: only a handful of getters were observed.
BASIC = {
    'status': C('/goform/getStatus'),
    'info': C('/goform/getStatus'),
    'wifi': C('/goform/getWifi'),
    'clients': None,
    'wan': C('/goform/getWAN'),
    'lan': None,
    'dhcp': None,
    'reboot': C('/goform/sysReboot', 'POST', (), True, True),
    'reset': None,
    'channel': None,
    'bandwidth': None,
    'block': None,
    'unblock': None,
    'diagnostics': None,
}

# Unknown model: safe discovery only.
UNKNOWN = {
    'status': C('/goform/getStatus'),
    'info': C('/goform/getStatus'),
}

MAPS = {
    'aes_goahead': AES,
    'legacy_ecos': LEGACY,
    'module_goform': MODULE,
    'basic_http': BASIC,
    'unknown': UNKNOWN,
}

FEATURES = tuple(AES.keys())


def for_family(family):
    return MAPS.get(family, UNKNOWN)
