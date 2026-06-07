"""Marzban panel driver (real implementation).

Marzban HTTP API:
  POST /api/admin/token              -> bearer token (OAuth2 password form)
  POST /api/user                     -> create user
  GET  /api/user/{username}          -> user info (incl. subscription_url, used/limit)
  PUT  /api/user/{username}          -> modify (status / data limit / expire)
  POST /api/user/{username}/reset    -> reset traffic
  DELETE /api/user/{username}        -> delete

Mirrors XUIPanel's high-level interface (create_client / get_client_traffic /
set_client_enabled / renew_client / change_link / delete_client) so the
provisioning layer can treat both panels the same way.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class MarzbanPanel:
    def __init__(self, url: str, username: str, password: str,
                 inbound_id: int = 1, sub_domain: str = ""):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.sub_domain = (sub_domain or "").rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: str = ""

    async def __aenter__(self) -> "MarzbanPanel":
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        await self.login()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def _logged_in(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def login(self) -> bool:
        assert self._session is not None
        try:
            async with self._session.post(
                f"{self.base_url}/api/admin/token",
                data={"username": self.username, "password": self.password},
            ) as r:
                data = await r.json(content_type=None)
                self._token = data.get("access_token", "")
                return bool(self._token)
        except Exception as exc:  # noqa: BLE001
            logger.error("Marzban login error: %s", exc)
            return False

    def _full_sub(self, sub_url: str) -> str:
        if not sub_url:
            return ""
        if sub_url.startswith("http"):
            return sub_url
        host = self.sub_domain or self.base_url
        if not host.startswith("http"):
            host = "https://" + host
        return host + sub_url

    async def create_client(self, email: str, volume_gb: int = 0,
                            days: int = 30) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        payload = {
            "username": email,
            "status": "active",
            "data_limit": int(volume_gb) * 1024 ** 3 if volume_gb else 0,
            "expire": int(time.time() + int(days) * 86400) if days else 0,
            "data_limit_reset_strategy": "no_reset",
            "proxies": {"vless": {}, "vmess": {}},
            "inbounds": {},
        }
        try:
            async with self._session.post(f"{self.base_url}/api/user",
                                          json=payload, headers=self._headers()) as r:
                data = await r.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        if r.status not in (200, 201) or "username" not in data:
            return {"success": False, "error": data.get("detail", "create failed")}
        return {
            "success": True,
            "uuid": email,  # marzban keys by username
            "email": email,
            "sub_url": self._full_sub(data.get("subscription_url", "")),
        }

    async def get_client_traffic(self, email: str) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        try:
            async with self._session.get(f"{self.base_url}/api/user/{email}",
                                         headers=self._headers()) as r:
                data = await r.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        if r.status != 200:
            return {"success": False, "error": data.get("detail")}
        # normalize to xui-like shape
        return {"success": True, "data": {
            "up": 0,
            "down": data.get("used_traffic", 0),
            "total": data.get("data_limit", 0) or 0,
            "expiryTime": (data.get("expire", 0) or 0) * 1000,
        }}

    async def set_client_enabled(self, email: str, client_uuid: str, enable: bool) -> bool:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return False
        payload = {"status": "active" if enable else "disabled"}
        try:
            async with self._session.put(f"{self.base_url}/api/user/{email}",
                                         json=payload, headers=self._headers()) as r:
                return r.status == 200
        except Exception as exc:  # noqa: BLE001
            logger.error("Marzban modify error: %s", exc)
            return False

    async def renew_client(self, email: str, client_uuid: str,
                           add_volume_gb: int, add_days: int) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        cur = await self.get_client_traffic(email)
        cur_total = 0
        cur_expiry = 0
        if cur.get("success"):
            cur_total = int(cur["data"].get("total", 0) or 0)
            cur_expiry = int((cur["data"].get("expiryTime", 0) or 0) / 1000)
        new_total = cur_total + add_volume_gb * 1024 ** 3 if add_volume_gb else cur_total
        now = int(time.time())
        base = cur_expiry if cur_expiry > now else now
        new_expire = base + add_days * 86400 if add_days else cur_expiry
        payload = {"data_limit": new_total, "expire": new_expire, "status": "active"}
        try:
            async with self._session.put(f"{self.base_url}/api/user/{email}",
                                         json=payload, headers=self._headers()) as r:
                ok = r.status == 200
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        # reset traffic so the new volume is fully usable
        try:
            await self._session.post(f"{self.base_url}/api/user/{email}/reset",
                                     headers=self._headers())
        except Exception:  # noqa: BLE001
            pass
        return {"success": ok}

    async def change_link(self, email: str, client_uuid: str) -> Dict[str, Any]:
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return {"success": False, "error": "login_failed"}
        # Marzban revokes & regenerates subscription token in one call
        try:
            async with self._session.post(f"{self.base_url}/api/user/{email}/revoke_sub",
                                          headers=self._headers()) as r:
                data = await r.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}
        if r.status != 200:
            return {"success": False, "error": data.get("detail")}
        return {"success": True, "sub_url": self._full_sub(data.get("subscription_url", ""))}

    async def delete_client(self, client_uuid: str) -> bool:
        # for marzban, client_uuid == username
        assert self._session is not None
        if not self._logged_in and not await self.login():
            return False
        try:
            async with self._session.delete(f"{self.base_url}/api/user/{client_uuid}",
                                            headers=self._headers()) as r:
                return r.status in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.error("Marzban delete error: %s", exc)
            return False


async def test_connection(url: str, username: str, password: str) -> bool:
    try:
        async with MarzbanPanel(url, username, password) as panel:
            return panel._logged_in
    except Exception as exc:  # noqa: BLE001
        logger.error("Marzban test_connection error: %s", exc)
        return False
