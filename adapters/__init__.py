"""Adapter factory: choose by discovery or explicit simulation."""
from __future__ import annotations

from adapters.base import BaseAdapter
from adapters.families import (AesGoaheadAdapter, LegacyEcosAdapter,
                               ModuleGoformAdapter, BasicHttpAdapter,
                               UnknownAdapter)
from adapters.mock import SimulatedTransport

CLASSES = {
    'aes_goahead': AesGoaheadAdapter,
    'legacy_ecos': LegacyEcosAdapter,
    'module_goform': ModuleGoformAdapter,
    'basic_http': BasicHttpAdapter,
    'unknown': UnknownAdapter,
}


def make_adapter(transport, session, discovery, simulate=None):
    family = simulate or discovery.get('api_family') or 'unknown'
    cls = CLASSES.get(family, UnknownAdapter)
    return cls(transport, session, discovery)


__all__ = ['make_adapter', 'BaseAdapter', 'SimulatedTransport']
