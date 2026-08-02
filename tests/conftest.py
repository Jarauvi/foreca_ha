"""Shared pytest fixtures for the Foreca integration tests."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import aioresponses as aioresponses_module

# Ensure the repository root is importable (for `custom_components`).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure tests/ is importable (for `mvt_builder`).
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


@pytest.fixture
def aioresponses():
    """Provide an aioresponses context manager for mocking aiohttp calls."""
    with aioresponses_module.aioresponses() as mock:
        yield mock

