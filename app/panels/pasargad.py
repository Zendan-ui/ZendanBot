"""
ZendanBOT - Pasargad Panel Driver
Professional async support for Pasargad panel (compatible with Marzban-like API).
"""

import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PasargadPanel:
    """Async driver for Pasargad panel."""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.token = None

    async def login(self) -> bool:
        url = f"{self.base_url}/api/admin/token"
        data = {"username": self.username, "password": self.password}
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.token = result.get("access_token")
                    return True
                return False
        except Exception as e:
            logger.error(f"Pasargad login error: {e}")
            return False

    async def _headers(self) -> Dict[str, str]:
        if not self.token:
            await self.login()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def create_user(self, username: str, data_limit_gb: int = 0, expire_days: int = 30,
                          proxies: dict = None, inbounds: dict = None, note: str = "") -> Dict[str, Any]:
        headers = await self._headers()
        from datetime import datetime, timedelta
        expire_ts = int((datetime.now() + timedelta(days=expire_days)).timestamp())

        payload = {
            "username": username,
            "proxies": proxies or {"vless": {}, "vmess": {}},
            "inbounds": inbounds or {},
            "data_limit": data_limit_gb * 1024**3 if data_limit_gb else 0,
            "expire": expire_ts,
            "data_limit_reset_strategy": "no_reset",
            "note": note,
        }

        url = f"{self.base_url}/api/user"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    return {"success": True, "username": username, "subscription_url": result.get("subscription_url", ""), "data": result}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user(self, username: str) -> Dict[str, Any]:
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": await resp.text()}
        except Exception as e:
            return {"error": str(e)}

    async def update_user(self, username: str, **updates) -> Dict[str, Any]:
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}"
        try:
            async with self.session.put(url, json=updates, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def remove_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}"
        try:
            async with self.session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
        except:
            return False

    async def get_subscription_url(self, username: str) -> Optional[str]:
        user = await self.get_user(username)
        return user.get("subscription_url")

    async def close(self):
        await self.session.close()
