"""Shared test fixtures."""

from __future__ import annotations

import pytest

# Environment variables that influence credential resolution. Cleared for every
# test so a developer's own shell (e.g. an exported RDT_COOKIE) can't leak in and
# make credential tests flaky.
_RDT_ENV_VARS = ("RDT_COOKIE", "RDT_SESSION", "RDT_MODHASH")


@pytest.fixture(autouse=True)
def _clear_rdt_env(monkeypatch):
    for var in _RDT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
