from __future__ import annotations

import importlib
import sys
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MODULES = [
    'app.main',
    'app.device_middleware',
    'app.labor_engine',
    'app.mattermost_integration',
    'app.ats_onboarding',
    'app.assets_lifecycle',
    'app.performance',
    'app.analytics',
    'app.user_experience',
    'app.monitoring',
]

for name in MODULES:
    importlib.import_module(name)
    print(f'[OK] imported {name}')

from app.main import app  # noqa: E402
from app.performance import _percentage  # noqa: E402

assert len(app.routes) >= 20, 'Expected expanded enterprise route set'
assert _percentage(Decimal('55'), Decimal('0'), Decimal('100')) == Decimal('55.00')
assert (PROJECT_ROOT / 'sql' / '002_enterprise_extensions.sql').exists()
assert (PROJECT_ROOT / 'static' / 'ess.css').exists()
assert (PROJECT_ROOT / 'templates' / 'ess_demo.html').exists()
print(f'[OK] route count = {len(app.routes)}')
print('[OK] project smoke checks passed')
