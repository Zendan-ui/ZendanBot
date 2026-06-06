"""
ZendanBOT - Alireza Panel Driver
Professional async support for Alireza single port panels.
"""

import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AlirezaPanel:
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
                    data = await resp.json()
                    self.token = data.get("token")
                    return True
                return False
        except Exception as e:
            logger.error(f"Alireza login failed: {e}")
            return False

    async def create_user(self, username: str, data_limit_gb: int = 0, expire_days: int = 30, 
                          inbound_id: int = 1) -> Dict[str, Any]:
        if not self.token:
            await self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "username": username,
            "data_limit": data_limit_gb * 1024**3 if data_limit_gb else 0,
            "expire": expire_days,
            "inbound_id": inbound_id,
            "enable": True
        }
        try:
            async with self.session.post(f"{self.base_url}/api/clients", json=payload, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_subscription_url(self, username: str, domain: str) -> str:
        return f"https://{domain}/sub/{username}"

    async def close(self):
        await self.session.close()
