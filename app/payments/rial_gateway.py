"""
ZendanBOT - Rial Exchange Payment Gateway (ارزی ریالی)
Supports Iranian Rial payment gateways with exchange rate calculation.
"""

import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RialGateway:
    """Rial-based payment gateway with USD/IRT exchange rate."""

    def __init__(self, gateway_url: str, api_key: str, merchant_id: str = ""):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key
        self.merchant_id = merchant_id
        self.session = aiohttp.ClientSession()

    async def get_exchange_rate(self) -> float:
        """Get current USD to IRT exchange rate."""
        try:
            # Try multiple sources
            async with self.session.get("https://api.exchangerate-api.com/v4/latest/USD") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("rates", {}).get("IRR", 500000) / 10  # Convert to Toman
        except:
            pass
        return 50000  # Default fallback rate (50,000 Toman per USD)

    async def create_payment(self, amount_toman: int, description: str = "",
                              callback_url: str = "", order_id: str = "") -> Dict[str, Any]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {
            "amount": amount_toman,
            "description": description or "ZendanBot payment",
            "callback_url": callback_url,
            "order_id": order_id or f"ZB{int(__import__('time').time())}",
        }
        if self.merchant_id:
            payload["merchant_id"] = self.merchant_id

        url = f"{self.gateway_url}/create"
        try:
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return {
                        "success": True,
                        "payment_url": result.get("payment_url", result.get("link", "")),
                        "authority": result.get("authority", result.get("token", "")),
                        "data": result
                    }
                return {"success": False, "error": await resp.text()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_payment(self, authority: str, amount: int) -> Dict[str, Any]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {
            "authority": authority,
            "amount": amount,
        }
        url = f"{self.gateway_url}/verify"
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
