import aiohttp
import json
from typing import Optional, Dict, Any
from app.config import settings

class MarzbanAPI:
    """Professional async Python client for Marzban panel API.
    Equivalent to original Marzban.php but cleaner, typed, async.
    """
    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self.session = aiohttp.ClientSession()

    async def login(self) -> bool:
        """Login and get access token."""
        url = f"{self.base_url}/api/admin/token"
        data = {"username": self.username, "password": self.password}
        async with self.session.post(url, data=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                self.token = result.get("access_token")
                return True
            return False

    async def get_headers(self) -> Dict[str, str]:
        if not self.token:
            await self.login()
        return {"Authorization": f"Bearer {self.token}"}

    async def create_user(self, username: str, proxies: Dict, inbounds: Dict, data_limit: int = 0, expire: int = 0, note: str = "") -> Dict[str, Any]:
        """Create user on Marzban. Returns user info or error."""
        headers = await self.get_headers()
        url = f"{self.base_url}/api/user"
        payload = {
            "username": username,
            "proxies": proxies or {"vless": {}, "vmess": {}},
            "inbounds": inbounds or {},
            "data_limit": data_limit * 1024 * 1024 * 1024 if data_limit > 0 else 0,  # GB to bytes
            "expire": expire,  # unix timestamp or 0
            "data_limit_reset_strategy": "no_reset",
            "note": note
        }
        async with self.session.post(url, json=payload, headers=headers) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            error = await resp.text()
            return {"error": error, "status": resp.status}

    async def get_user(self, username: str) -> Dict[str, Any]:
        headers = await self.get_headers()
        url = f"{self.base_url}/api/user/{username}"
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"error": await resp.text()}

    async def update_user(self, username: str, **updates) -> Dict[str, Any]:
        headers = await self.get_headers()
        url = f"{self.base_url}/api/user/{username}"
        async with self.session.put(url, json=updates, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else {"error": await resp.text()}

    async def remove_user(self, username: str) -> bool:
        headers = await self.get_headers()
        url = f"{self.base_url}/api/user/{username}"
        async with self.session.delete(url, headers=headers) as resp:
            return resp.status == 200

    async def get_subscription_url(self, username: str) -> Optional[str]:
        user = await self.get_user(username)
        if "subscription_url" in user:
            return user["subscription_url"]
        return None

    async def close(self):
        await self.session.close()

# Usage example in bot:
# panel = MarzbanAPI(url=panel_url, username=..., password=...)
# await panel.login()
# user_data = await panel.create_user(...)
