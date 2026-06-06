"""
ZendanBOT - NowPayments Gateway
Professional async implementation.
"""

import aiohttp
import hashlib
import hmac
import json
from typing import Dict, Any, Optional

class NowPayment:
    def __init__(self, api_key: str, ipn_secret: str = None):
        self.api_key = api_key
        self.ipn_secret = ipn_secret
        self.session = aiohttp.ClientSession()
        self.base_url = "https://api.nowpayments.io/v1"

    async def create_invoice(self, amount: float, currency: str = "USD", order_id: str = None) -> Dict[str, Any]:
        headers = {"x-api-key": self.api_key}
        payload = {
            "price_amount": amount,
            "price_currency": currency,
            "order_id": order_id or "zendanbot-order",
            "ipn_callback_url": "https://yourdomain.com/webhook/nowpayment"
        }
        async with self.session.post(f"{self.base_url}/invoice", json=payload, headers=headers) as resp:
            return await resp.json()

    async def verify_ipn(self, data: dict, signature: str) -> bool:
        if not self.ipn_secret:
            return True
        sorted_data = json.dumps(data, sort_keys=True)
        expected = hmac.new(self.ipn_secret.encode(), sorted_data.encode(), hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def close(self):
        await self.session.close()
