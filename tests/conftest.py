"""Pytest configuration shared across all test layers.

Inserts `src/` into sys.path so tests can import the package without an
editable install — same pattern as the sibling kg-mcp's conftest.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
