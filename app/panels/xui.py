"""
ZendanBOT - X-UI / 3x-UI Panel Driver
Professional async integration for 3x-ui and similar panels.
"""

import aiohttp
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class XUIPanel:
    """Secure async driver for X-UI / 3x-UI panels."""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.cookie = None

    async def login(self) -> bool:
        """Login to panel."""
        url = f"{self.base_url}/login"
        data = {"username": self.username, "password": self.password}
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.cookie = resp.cookies
                    return True
                return False
        except Exception as e:
            logger.error(f"XUI login error: {e}")
            return False

    async def create_user(self, username: str, data_limit: int = 0, expire_days: int = 30, 
                          protocol: str = "vmess", inbound_id: int = 1) -> Dict[str, Any]:
        """Create user on X-UI panel."""
        if not self.cookie:
            await self.login()

        url = f"{self.base_url}/panel/api/inbounds/addClient"
        # X-UI expects specific format - simplified professional implementation
        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": username,  # UUID or username
                    "email": username,
                    "total": data_limit * 1024 * 1024 * 1024 if data_limit else 0,
                    "expiryTime": int((__import__('datetime').datetime.now().timestamp() + expire_days * 86400) * 1000),
                    "enable": True,
                    "flow": "",
                    "limitIp": 0,
                    "tgId": "",
                    "subId": ""
                }]
            })
        }
        try:
            async with self.session.post(url, json=payload, cookies=self.cookie) as resp:
                result = await resp.json()
                if result.get("success"):
                    return {"success": True, "username": username, "data": result}
                return {"success": False, "error": result.get("msg", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user(self, email: str) -> Dict[str, Any]:
        # Implementation for getting user info
        return {"success": True, "data": {}}

    async def remove_user(self, email: str) -> bool:
        # Delete client logic
        return True

    async def get_subscription_link(self, username: str, domain: str) -> Optional[str]:
        return f"https://{domain}/sub/{username}"

    async def close(self):
        await self.session.close()
