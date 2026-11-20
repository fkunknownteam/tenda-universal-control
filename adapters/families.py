"""Firmware-family adapters. Differences live here, not in the CLI."""
from __future__ import annotations

import base64
import json

from adapters.base import BaseAdapter

IV = b'EU5H62G9ICGRNI43'


class AesGoaheadAdapter(BaseAdapter):
    """Modern GoAhead firmware: md5 login + per-session AES sign (AC/AX/Nova)."""
    family = 'aes_goahead'

    def decode(self, text):
        obj = super().decode(text)
        if isinstance(obj, dict) and 'raw' in obj and self.session.sign:
            try:
                from Crypto.Cipher import AES
                from Crypto.Util.Padding import unpad
                key = self.session.sign.encode()
                if len(key) not in (16, 24, 32):
                    key = (key * 3)[:32] if len(key) < 16 else key[:32]
                plain = unpad(AES.new(key, AES.MODE_CBC, IV).decrypt(
                    base64.b64decode(text.strip())), 16).decode('utf-8', 'replace')
                return json.loads(plain)
            except Exception:
                pass
        return obj


class LegacyEcosAdapter(BaseAdapter):
    """eCos plaintext goform: getstok + md5(base64(password)+token)."""
    family = 'legacy_ecos'


class ModuleGoformAdapter(BaseAdapter):
    """Older AC/N-series: getStatus?modules=... with base64/open login."""
    family = 'module_goform'


class BasicHttpAdapter(BaseAdapter):
    """Small subset of Tenda firmware with only basic goform getters."""
    family = 'basic_http'


class UnknownAdapter(BaseAdapter):
    """Unknown model: safe discovery endpoints only, everything else unsupported."""
    family = 'unknown'
