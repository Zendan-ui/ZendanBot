"""
ZendanBOT - Eylan Panel Driver
Professional async support for Eylan panel (L2TP, Cisco, WireGuard protocols).
"""

import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class EylanPanel:
    """Async driver for Eylan panel."""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.token = None

    async def login(self) -> bool:
        url = f"{self.base_url}/api/login"
        data = {"username": self.username, "password": self.password}
        try:
            async with self.session.post(url, json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.token = result.get("token") or result.get("access_token")
                    return True
                return False
        except Exception as e:
            logger.error(f"Eylan login error: {e}")
            return False

    async def _headers(self) -> Dict[str, str]:
        if not self.token:
            await self.login()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def create_user(self, username: str, password: str = "", protocol: str = "l2tp",
                          data_limit_gb: int = 0, expire_days: int = 30) -> Dict[str, Any]:
        headers = await self._headers()
        payload = {
            "username": username,
            "password": password or username,
            "protocol": protocol,  # l2tp, cisco, wireguard
            "data_limit": data_limit_gb * 1024**3 if data_limit_gb else 0,
            "expire_days": expire_days,
            "enable": True,
        }

        url = f"{self.base_url}/api/users"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    return {"success": True, "username": username, "data": await resp.json()}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user(self, username: str) -> Dict[str, Any]:
        headers = await self._headers()
        url = f"{self.base_url}/api/users/{username}"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": await resp.text()}
        except Exception as e:
            return {"error": str(e)}

    async def remove_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/users/{username}"
        try:
            async with self.session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
        except:
            return False

    async def disable_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/users/{username}/disable"
        try:
            async with self.session.post(url, headers=headers) as resp:
                return resp.status == 200
        except:
            return False

    async def enable_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/users/{username}/enable"
        try:
            async with self.session.post(url, headers=headers) as resp:
                return resp.status == 200
        except:
            return False

    async def close(self):
        await self.session.close()
