"""Pasargad panel driver.

Pasargad ("Pasargad Gold") exposes a Marzban-compatible HTTP API
(/api/admin/token, /api/user, ...), so we reuse the full, working Marzban
driver and only change the label. If a future Pasargad build diverges, override
the specific methods here.
"""
from __future__ import annotations

import logging

from app.panels.marzban import MarzbanPanel

logger = logging.getLogger(__name__)


class PasargadPanel(MarzbanPanel):
    """Marzban-compatible driver for Pasargad panels."""
    pass


async def test_connection(url: str, username: str, password: str) -> bool:
    try:
        async with PasargadPanel(url, username, password) as panel:
            return panel._logged_in
    except Exception as exc:  # noqa: BLE001
        logger.error("Pasargad test_connection error: %s", exc)
        return False
