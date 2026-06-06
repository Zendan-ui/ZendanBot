"""
ZendanBOT - IBSng Panel Driver
"""

import aiohttp
from typing import Dict, Any

class IBSngPanel:
    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()

    async def create_user(self, username: str, group: str, data_limit: int = 0, expire_days: int = 30) -> Dict[str, Any]:
        # IBSng specific API calls (simplified professional version)
        payload = {
            "username": username,
            "group": group,
            "credit": data_limit,
            "expire_days": expire_days
        }
        try:
            async with self.session.post(f"{self.base_url}/api/user/create", json=payload) as resp:
                return await resp.json()
        except:
            return {"success": False}

    async def close(self):
        await self.session.close()
