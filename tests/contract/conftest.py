"""Pytest options for the contract test layer."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        dest="snapshot_update",
        help="Regenerate the contract golden snapshots instead of asserting (rc=0 if restored).",
    )
