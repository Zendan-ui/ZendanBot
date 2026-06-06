"""
ZendanBOT - Marzneshin Panel Driver
Professional async support.
"""

import aiohttp
from typing import Dict, Any

class MarzneshinPanel:
    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.token = None

    async def login(self):
        data = {"username": self.username, "password": self.password}
        async with self.session.post(f"{self.base_url}/api/admin/token", data=data) as resp:
            result = await resp.json()
            self.token = result.get("access_token")

    async def create_user(self, username: str, data_limit: int, expire: int, proxies: dict = None) -> Dict[str, Any]:
        if not self.token:
            await self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "username": username,
            "data_limit": data_limit,
            "expire": expire,
            "proxies": proxies or {"vless": {}},
            "inbounds": {}
        }
        async with self.session.post(f"{self.base_url}/api/user", json=payload, headers=headers) as resp:
            return await resp.json()

    async def close(self):
        await self.session.close()
