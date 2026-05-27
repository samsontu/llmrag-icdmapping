"""Shared pytest config."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _quiet_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Reduce log noise during tests."""
    import logging

    caplog.set_level(logging.WARNING)
