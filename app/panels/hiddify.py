"""
ZendanBOT - Hiddify Panel Driver
Professional integration.
"""

import aiohttp
from typing import Dict, Any

class HiddifyPanel:
    def __init__(self, url: str, admin_uuid: str):
        self.base_url = url.rstrip("/")
        self.admin_uuid = admin_uuid
        self.session = aiohttp.ClientSession()

    async def create_user(self, username: str, data_limit_gb: int = 0, expire_days: int = 30) -> Dict[str, Any]:
        payload = {
            "name": username,
            "data_limit": data_limit_gb * 1024**3 if data_limit_gb else 0,
            "expire": expire_days * 86400,
            "enable": True
        }
        url = f"{self.base_url}/api/user"
        headers = {"Authorization": self.admin_uuid}
        async with self.session.post(url, json=payload, headers=headers) as resp:
            return await resp.json()

    async def get_user_info(self, username: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/user/{username}"
        async with self.session.get(url) as resp:
            return await resp.json()

    async def close(self):
        await self.session.close()
