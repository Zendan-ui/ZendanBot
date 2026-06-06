"""
ZendanBOT - Custom Payment Gateway Template
Allows connecting any arbitrary payment gateway with custom API.
"""

import aiohttp
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class CustomGateway:
    """Flexible custom gateway for any payment provider."""

    def __init__(self, name: str, base_url: str, api_key: str,
                 create_endpoint: str = "/create", verify_endpoint: str = "/verify",
                 extra_headers: dict = None, extra_params: dict = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.create_endpoint = create_endpoint
        self.verify_endpoint = verify_endpoint
        self.extra_headers = extra_headers or {}
        self.extra_params = extra_params or {}
        self.session = aiohttp.ClientSession()

    async def create_payment(self, amount: int, description: str = "",
                              callback_url: str = "", order_id: str = "") -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers
        }
        payload = {
            "amount": amount,
            "description": description,
            "callback_url": callback_url,
            "order_id": order_id or f"ZB{int(__import__('time').time())}",
            **self.extra_params
        }

        url = f"{self.base_url}{self.create_endpoint}"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    return {
                        "success": True,
                        "payment_url": result.get("payment_url") or result.get("link") or result.get("url", ""),
                        "authority": result.get("authority") or result.get("token") or result.get("id", ""),
                        "data": result
                    }
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_payment(self, authority: str, amount: int) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers
        }
        payload = {
            "authority": authority,
            "amount": amount,
            **self.extra_params
        }
        url = f"{self.base_url}{self.verify_endpoint}"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return {"success": True, "data": result}
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        await self.session.close()
