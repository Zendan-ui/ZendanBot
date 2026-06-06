"""
ZendanBOT - Plisio Payment Gateway
Professional async implementation for cryptocurrency payments via Plisio.
"""

import aiohttp
import hmac
import hashlib
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class PlisioPayment:
    def __init__(self, api_key: str, secret: str = ""):
        self.api_key = api_key
        self.secret = secret
        self.session = aiohttp.ClientSession()
        self.base_url = "https://plisio.net/api/v1"

    async def create_invoice(self, amount: float, currency: str = "USD",
                              source_currency: str = "TRX", order_id: str = "",
                              callback_url: str = "") -> Dict[str, Any]:
        params = {
            "api_key": self.api_key,
            "amount": amount,
            "currency": source_currency,
            "source_currency": currency,
            "order_number": order_id or f"zendanbot_{int(__import__('time').time())}",
        }
        if callback_url:
            params["callback_url"] = callback_url

        url = f"{self.base_url}/invoice/new"
        try:
            async with self.session.get(url, params=params) as resp:
                result = await resp.json()
                if result.get("status") == "success":
                    data = result.get("data", {})
                    return {
                        "success": True,
                        "invoice_id": data.get("txn_id"),
                        "pay_url": data.get("invoice_url"),
                        "amount": data.get("amount"),
                        "data": data
                    }
                return {"success": False, "error": result.get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def check_invoice(self, txn_id: str) -> Dict[str, Any]:
        params = {"api_key": self.api_key}
        url = f"{self.base_url}/invoice/{txn_id}"
        try:
            async with self.session.get(url, params=params) as resp:
                result = await resp.json()
                if result.get("status") == "success":
                    data = result.get("data", {})
                    return {
                        "success": True,
                        "status": data.get("status"),
                        "amount": data.get("amount"),
                        "data": data
                    }
                return {"success": False, "error": result.get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_callback(self, data: dict, signature: str) -> bool:
        if not self.secret:
            return True
        sorted_data = str(sorted(data.items()))
        expected = hmac.new(self.secret.encode(), sorted_data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def get_balance(self) -> Dict[str, Any]:
        params = {"api_key": self.api_key}
        url = f"{self.base_url}/balance"
        try:
            async with self.session.get(url, params=params) as resp:
                return await resp.json()
        except:
            return {"success": False}

    async def close(self):
        await self.session.close()
