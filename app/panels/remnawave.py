"""
ZendanBOT - Remnawave Panel Driver
Professional async support for Remnawave panel (compatible with latest version).
"""

import aiohttp
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class RemnawavePanel:
    """Async driver for Remnawave panel API."""

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
            logger.error(f"Remnawave login error: {e}")
            return False

    async def _headers(self) -> Dict[str, str]:
        if not self.token:
            await self.login()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def create_user(self, username: str, data_limit: int = 0, expire_days: int = 30,
                          proxies: dict = None, inbounds: dict = None,
                          limit_ips: int = 0, note: str = "") -> Dict[str, Any]:
        headers = await self._headers()
        from datetime import datetime, timedelta
        
        expire_ts = int((datetime.now() + timedelta(days=expire_days)).timestamp())

        payload = {
            "username": username,
            "proxies": proxies or {"vless": {}, "vmess": {}},
            "inbounds": inbounds or {},
            "data_limit": data_limit * 1024 * 1024 * 1024 if data_limit > 0 else 0,
            "expire": expire_ts,
            "data_limit_reset_strategy": "no_reset",
            "limit_ips": limit_ips,
            "note": note,
        }

        url = f"{self.base_url}/api/user"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    sub_url = result.get("subscription_url", "")
                    return {"success": True, "username": username, "subscription_url": sub_url, "data": result}
                error = await resp.text()
                return {"success": False, "error": error}
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
                if resp.status == 200:
                    return await resp.json()
                return {"error": await resp.text()}
        except Exception as e:
            return {"error": str(e)}

    async def remove_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}"
        try:
            async with self.session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"Remnawave remove error: {e}")
            return False

    async def get_subscription_url(self, username: str) -> Optional[str]:
        user = await self.get_user(username)
        if "subscription_url" in user:
            return user["subscription_url"]
        return None

    async def reset_user_data(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}/reset-data"
        try:
            async with self.session.post(url, headers=headers) as resp:
                return resp.status == 200
        except:
            return False

    async def revoke_subscription(self, username: str) -> Optional[str]:
        """Revoke old subscription and get new URL."""
        headers = await self._headers()
        url = f"{self.base_url}/api/user/{username}/revoke-subscription"
        try:
            async with self.session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("subscription_url")
                return None
        except:
            return None

    async def get_user_usage(self, username: str) -> Dict[str, Any]:
        """Get user traffic usage."""
        user = await self.get_user(username)
        if "used_traffic" in user:
            return {
                "used": user.get("used_traffic", 0),
                "total": user.get("data_limit", 0),
                "remaining": max(0, user.get("data_limit", 0) - user.get("used_traffic", 0))
            }
        return {"used": 0, "total": 0, "remaining": 0}

    async def get_nodes(self) -> List[Dict]:
        headers = await self._headers()
        url = f"{self.base_url}/api/node"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except:
            return []

    async def get_system_stats(self) -> Dict[str, Any]:
        headers = await self._headers()
        url = f"{self.base_url}/api/system/stats"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except:
            return {}

    async def close(self):
        await self.session.close()
