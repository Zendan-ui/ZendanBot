"""
ZendanBOT - WGDashboard (WireGuard) Panel Driver
Professional async support for WGDashboard panel.
"""

import aiohttp
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class WGDashboardPanel:
    """Async driver for WGDashboard (WireGuard panel)."""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.token = None

    async def login(self) -> bool:
        url = f"{self.base_url}/api/auth/login"
        data = {"username": self.username, "password": self.password}
        try:
            async with self.session.post(url, json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.token = result.get("token") or result.get("access_token")
                    return True
                return False
        except Exception as e:
            logger.error(f"WGDashboard login error: {e}")
            return False

    async def _headers(self) -> Dict[str, str]:
        if not self.token:
            await self.login()
        return {"Authorization": f"Bearer {self.token}"}

    async def create_user(self, username: str, data_limit_mb: int = 0, 
                          expire_days: int = 30, allowed_ips: str = "0.0.0.0/0,::/0") -> Dict[str, Any]:
        headers = await self._headers()
        from datetime import datetime, timedelta
        
        # WGDashboard uses specific configuration
        payload = {
            "name": username,
            "allowed_ips": allowed_ips,
        }
        
        # Add expiry if supported
        if expire_days > 0:
            expiry = datetime.now() + timedelta(days=expire_days)
            payload["expires_at"] = expiry.isoformat()
        
        # Add data limit if supported (in MB)
        if data_limit_mb > 0:
            payload["data_limit"] = data_limit_mb * 1024 * 1024

        url = f"{self.base_url}/api/peer/add"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    return {"success": True, "username": username, "data": result}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_user(self, username: str) -> Dict[str, Any]:
        headers = await self._headers()
        url = f"{self.base_url}/api/peer/{username}"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": await resp.text()}
        except Exception as e:
            return {"error": str(e)}

    async def remove_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/api/peer/{username}"
        try:
            async with self.session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"WGDashboard remove error: {e}")
            return False

    async def get_config(self, username: str) -> Optional[str]:
        """Get WireGuard config file content for user."""
        headers = await self._headers()
        url = f"{self.base_url}/api/peer/{username}/config"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except:
            return None

    async def get_qr_code(self, username: str) -> Optional[bytes]:
        """Get QR code for WireGuard config."""
        headers = await self._headers()
        url = f"{self.base_url}/api/peer/{username}/qrcode"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None
        except:
            return None

    async def list_users(self) -> List[Dict]:
        headers = await self._headers()
        url = f"{self.base_url}/api/peers"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except:
            return []

    async def close(self):
        await self.session.close()
