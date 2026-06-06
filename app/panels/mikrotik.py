"""
ZendanBOT - Mikrotik RouterOS Panel Driver
Professional async support for Mikrotik User Manager (OpenVPN, L2TP, PPPoE, WireGuard).
"""

import aiohttp
import base64
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class MikrotikPanel:
    """Async driver for Mikrotik RouterOS API."""

    def __init__(self, host: str, username: str, password: str, port: int = 8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.session = aiohttp.ClientSession()
        self.base_url = f"http://{host}:{port}/rest"
        self.auth_header = base64.b64encode(f"{username}:{password}".encode()).decode()

    async def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Basic {self.auth_header}", "Content-Type": "application/json"}

    async def test_connection(self) -> bool:
        try:
            headers = await self._headers()
            async with self.session.get(f"{self.base_url}/system/resource", headers=headers) as resp:
                return resp.status == 200
        except:
            return False

    async def create_ppp_user(self, username: str, password: str, profile: str = "default",
                               service: str = "pppoe", limit_bytes_total: int = 0,
                               limit_uptime: str = "") -> Dict[str, Any]:
        """Create PPP/PPPoE/L2TP/OpenVPN user on Mikrotik."""
        headers = await self._headers()
        payload = {
            "name": username,
            "password": password,
            "profile": profile,
            "service": service,
        }
        if limit_bytes_total > 0:
            payload["limit-bytes-total"] = str(limit_bytes_total)
        if limit_uptime:
            payload["limit-uptime"] = limit_uptime  # e.g., "30d" for 30 days

        url = f"{self.base_url}/ppp/secret"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    return {"success": True, "username": username, "data": result}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_wireguard_user(self, username: str, allowed_address: str = "0.0.0.0/0",
                                     interface: str = "wg0") -> Dict[str, Any]:
        """Add WireGuard peer on Mikrotik."""
        headers = await self._headers()
        payload = {
            "interface": interface,
            "allowed-address": allowed_address,
            "comment": username,
        }
        url = f"{self.base_url}/interface/wireguard/peers/add"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    return {"success": True, "username": username, "data": result}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def remove_ppp_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/ppp/secret"
        try:
            # Find user first
            async with self.session.get(f"{url}?name={username}", headers=headers) as resp:
                if resp.status == 200:
                    users = await resp.json()
                    if users:
                        user_id = users[0].get(".id")
                        async with self.session.delete(f"{url}/{user_id}", headers=headers) as del_resp:
                            return del_resp.status in (200, 204)
            return False
        except Exception as e:
            logger.error(f"Mikrotik remove error: {e}")
            return False

    async def disable_ppp_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/ppp/secret"
        try:
            async with self.session.get(f"{url}?name={username}", headers=headers) as resp:
                if resp.status == 200:
                    users = await resp.json()
                    if users:
                        user_id = users[0].get(".id")
                        async with self.session.post(f"{url}/disable", json={".id": user_id}, headers=headers) as dis_resp:
                            return dis_resp.status == 200
            return False
        except:
            return False

    async def enable_ppp_user(self, username: str) -> bool:
        headers = await self._headers()
        url = f"{self.base_url}/ppp/secret"
        try:
            async with self.session.get(f"{url}?name={username}", headers=headers) as resp:
                if resp.status == 200:
                    users = await resp.json()
                    if users:
                        user_id = users[0].get(".id")
                        async with self.session.post(f"{url}/enable", json={".id": user_id}, headers=headers) as en_resp:
                            return en_resp.status == 200
            return False
        except:
            return False

    async def get_active_users(self) -> List[Dict]:
        headers = await self._headers()
        url = f"{self.base_url}/ppp/active"
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except:
            return []

    async def close(self):
        await self.session.close()
