"""
ZendanBOT - S-UI Panel Driver
Professional async support for S-UI panel (Alireza's new single-port panel).
"""

import aiohttp
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SUIPanel:
    """Secure async driver for S-UI panels."""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.cookie = None

    async def login(self) -> bool:
        url = f"{self.base_url}/login"
        data = {"username": self.username, "password": self.password}
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.cookie = resp.cookies
                    return True
                return False
        except Exception as e:
            logger.error(f"S-UI login error: {e}")
            return False

    async def create_user(self, username: str, data_limit: int = 0, expire_days: int = 30,
                          protocol: str = "vmess", inbound_id: int = 1,
                          limit_ip: int = 0) -> Dict[str, Any]:
        if not self.cookie:
            await self.login()

        url = f"{self.base_url}/panel/api/inbounds/addClient"
        import uuid
        client_uuid = str(uuid.uuid4())

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": client_uuid,
                    "email": username,
                    "total": data_limit * 1024 * 1024 * 1024 if data_limit else 0,
                    "expiryTime": int(((__import__('datetime').datetime.now().timestamp() + expire_days * 86400) * 1000)),
                    "enable": True,
                    "flow": "",
                    "limitIp": limit_ip,
                    "tgId": "",
                    "subId": ""
                }]
            })
        }
        try:
            async with self.session.post(url, json=payload, cookies=self.cookie) as resp:
                result = await resp.json()
                if result.get("success"):
                    return {"success": True, "username": username, "uuid": client_uuid, "data": result}
                return {"success": False, "error": result.get("msg", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user(self, email: str) -> Dict[str, Any]:
        if not self.cookie:
            await self.login()
        url = f"{self.base_url}/panel/api/inbounds/getClientData/{email}"
        try:
            async with self.session.get(url, cookies=self.cookie) as resp:
                return await resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_user(self, email: str, **updates) -> Dict[str, Any]:
        if not self.cookie:
            await self.login()
        url = f"{self.base_url}/panel/api/inbounds/updateClient/{email}"
        try:
            async with self.session.post(url, json=updates, cookies=self.cookie) as resp:
                return await resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def remove_user(self, email: str) -> bool:
        if not self.cookie:
            await self.login()
        url = f"{self.base_url}/panel/api/inbounds/delClient/{email}"
        try:
            async with self.session.post(url, cookies=self.cookie) as resp:
                result = await resp.json()
                return result.get("success", False)
        except Exception as e:
            logger.error(f"S-UI remove error: {e}")
            return False

    async def get_subscription_link(self, username: str, domain: str) -> Optional[str]:
        return f"https://{domain}/sub/{username}"

    async def get_online_users(self) -> list:
        if not self.cookie:
            await self.login()
        url = f"{self.base_url}/panel/api/inbounds/onlines"
        try:
            async with self.session.get(url, cookies=self.cookie) as resp:
                result = await resp.json()
                return result if isinstance(result, list) else []
        except:
            return []

    async def close(self):
        await self.session.close()
