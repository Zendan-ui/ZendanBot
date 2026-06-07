"""
3X-UI / X-UI panel driver (real, working implementation).

Tested against the 3x-ui HTTP API:
  POST /login
  POST /panel/api/inbounds/addClient
  POST /panel/api/inbounds/{id}/delClient/{uuid}
  POST /panel/api/inbounds/updateClient/{uuid}
  GET  /panel/api/inbounds/getClientTraffics/{email}
  GET  /panel/api/inbounds/get/{id}

A fresh aiohttp session is created and closed per high-level operation via
the async-context-manager protocol, so there are no leaked sessions.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class XUIPanel:
    def __init__(self, url: str, username: str, password: str,
                 inbound_id: int = 1, sub_domain: str = ""):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.inbound_id = int(inbound_id or 1)
        self.sub_domain = (sub_domain or "").rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in = False

    # --------------------------------------------------------------- #
    #  context manager helpers
    # --------------------------------------------------------------- #
    async def __aenter__(self) -> "XUIPanel":
        timeout = aiohttp.ClientTimeout(total=20)
        self._session = aiohttp.ClientSession(timeout=timeout)
        await self.login()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # --------------------------------------------------------------- #
    #  auth
    # --------------------------------------------------------------- #
    async def login(self) -> bool:
        assert self._session is not None
        try:
            async with self._session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
            ) as resp:
                data = await resp.json(content_type=None)
                self._logged_in = bool(data.get("success"))
                if not self._logged_in:
                    logger.warning("XUI login failed: %s", data.get("msg"))
                return self._logged_in
        except Exception as exc:  # noqa: BLE001
            logger.error("XUI login error: %s", exc)
            return False

    # --------------------------------------------------------------- #
    #  create client
    # --------------------------------------------------------------- #
    async def create_client(self, email: str, volume_gb: int = 0,
                            days: int = 30) -> Dict[str, Any]:
        """Add a new client to the configured inbound.

        Returns: {success, uuid, email, sub_url, error}
        """
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}

        client_uuid = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]
        total_bytes = int(volume_gb) * 1024 * 1024 * 1024 if volume_gb else 0
        expiry_ms = int((time.time() + int(days) * 86400) * 1000) if days else 0

        settings_payload = {
            "clients": [{
                "id": client_uuid,
                "email": email,
                "enable": True,
                "totalGB": total_bytes,
                "expiryTime": expiry_ms,
                "limitIp": 0,
                "tgId": "",
                "subId": sub_id,
                "flow": "",
            }]
        }
        payload = {"id": self.inbound_id, "settings": json.dumps(settings_payload)}

        try:
            async with self._session.post(
                f"{self.base_url}/panel/api/inbounds/addClient", json=payload
            ) as resp:
                data = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}

        if not data.get("success"):
            return {"success": False, "error": data.get("msg", "addClient failed")}

        return {
            "success": True,
            "uuid": client_uuid,
            "email": email,
            "sub_url": self.subscription_url(sub_id),
        }

    # --------------------------------------------------------------- #
    #  traffic / info
    # --------------------------------------------------------------- #
    async def get_client_traffic(self, email: str) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        try:
            async with self._session.get(
                f"{self.base_url}/panel/api/inbounds/getClientTraffics/{email}"
            ) as resp:
                data = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        return {"success": bool(data.get("success")), "data": data.get("obj")}

    # --------------------------------------------------------------- #
    #  enable / disable
    # --------------------------------------------------------------- #
    async def set_client_enabled(self, email: str, client_uuid: str,
                                 enable: bool) -> bool:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return False
        settings_payload = {
            "clients": [{"id": client_uuid, "email": email, "enable": enable}]
        }
        payload = {"id": self.inbound_id, "settings": json.dumps(settings_payload)}
        try:
            async with self._session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
                return bool(data.get("success"))
        except Exception as exc:  # noqa: BLE001
            logger.error("XUI updateClient error: %s", exc)
            return False

    # --------------------------------------------------------------- #
    #  renew / extend (reset traffic + push expiry forward)
    # --------------------------------------------------------------- #
    async def renew_client(self, email: str, client_uuid: str,
                           add_volume_gb: int, add_days: int) -> Dict[str, Any]:
        """Add volume/time to an existing client. We read current totals where
        possible and write new ones. Returns {success, error}."""
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}

        cur = await self.get_client_traffic(email)
        cur_total = 0
        cur_expiry = 0
        if cur.get("success") and cur.get("data"):
            d = cur["data"]
            cur_total = int(d.get("total", 0) or 0)
            cur_expiry = int(d.get("expiryTime", 0) or 0)

        new_total = cur_total + add_volume_gb * 1024 * 1024 * 1024 if add_volume_gb else cur_total
        now_ms = int(time.time() * 1000)
        base = cur_expiry if cur_expiry > now_ms else now_ms
        new_expiry = base + add_days * 86400 * 1000 if add_days else cur_expiry

        settings_payload = {
            "clients": [{
                "id": client_uuid,
                "email": email,
                "enable": True,
                "totalGB": new_total,
                "expiryTime": new_expiry,
            }]
        }
        payload = {"id": self.inbound_id, "settings": json.dumps(settings_payload)}
        try:
            async with self._session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        # reset traffic counters so the new volume is fully usable
        try:
            await self._session.post(
                f"{self.base_url}/panel/api/inbounds/{self.inbound_id}/resetClientTraffic/{email}"
            )
        except Exception:  # noqa: BLE001
            pass
        return {"success": bool(data.get("success")), "error": data.get("msg")}

    # --------------------------------------------------------------- #
    #  change link (rotate subId)
    # --------------------------------------------------------------- #
    async def change_link(self, email: str, client_uuid: str) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        new_sub = uuid.uuid4().hex[:16]
        settings_payload = {
            "clients": [{"id": client_uuid, "email": email, "enable": True, "subId": new_sub}]
        }
        payload = {"id": self.inbound_id, "settings": json.dumps(settings_payload)}
        try:
            async with self._session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                json=payload,
            ) as resp:
                data = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        if not data.get("success"):
            return {"success": False, "error": data.get("msg")}
        return {"success": True, "sub_url": self.subscription_url(new_sub)}

    # --------------------------------------------------------------- #
    #  delete
    # --------------------------------------------------------------- #
    async def delete_client(self, client_uuid: str) -> bool:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return False
        try:
            async with self._session.post(
                f"{self.base_url}/panel/api/inbounds/{self.inbound_id}/delClient/{client_uuid}"
            ) as resp:
                data = await resp.json(content_type=None)
                return bool(data.get("success"))
        except Exception as exc:  # noqa: BLE001
            logger.error("XUI delClient error: %s", exc)
            return False

    # --------------------------------------------------------------- #
    #  helpers
    # --------------------------------------------------------------- #
    def subscription_url(self, sub_id: str) -> str:
        host = self.sub_domain or self.base_url
        if not host.startswith("http"):
            host = "http://" + host
        return f"{host}/sub/{sub_id}"


async def test_connection(url: str, username: str, password: str) -> bool:
    """Quick connectivity/credentials check used by the admin panel."""
    try:
        async with XUIPanel(url, username, password) as panel:
            return panel._logged_in
    except Exception as exc:  # noqa: BLE001
        logger.error("XUI test_connection error: %s", exc)
        return False
