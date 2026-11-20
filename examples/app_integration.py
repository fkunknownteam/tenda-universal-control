#!/usr/bin/env python3
"""Example: app calls one interface; the skill owns model-specific details."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.client import TendaUniversal

router = TendaUniversal(
    host=os.environ.get('TENDA_HOST', '192.168.0.1'),
    password=os.environ.get('TENDA_PASSWORD', ''),
    username=os.environ.get('TENDA_USERNAME', 'admin'),
)

report = router.diagnose()
print(json.dumps(report, indent=2, ensure_ascii=False))

for feature, action in [('status', 'get'), ('clients', 'get'), ('wifi', 'get')]:
    result = router.execute(feature, action)
    print(json.dumps(result, indent=2, ensure_ascii=False))

# Destructive actions need explicit confirmation:
# result = router.execute('reboot', 'set', confirm=True)
