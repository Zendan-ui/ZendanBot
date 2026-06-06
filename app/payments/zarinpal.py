"""
ZendanBOT - Zarinpal Gateway
Professional implementation.
"""

import aiohttp
from typing import Dict, Any

class ZarinpalPayment:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.session = aiohttp.ClientSession()
        self.base = "https://api.zarinpal.com/pg/v4/payment"

    async def create_payment(self, amount: int, description: str, callback_url: str) -> Dict[str, Any]:
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "description": description,
            "callback_url": callback_url
        }
        async with self.session.post(f"{self.base}/request.json", json=payload) as resp:
            return await resp.json()

    async def verify(self, authority: str, amount: int) -> Dict[str, Any]:
        payload = {
            "merchant_id": self.merchant_id,
            "authority": authority,
            "amount": amount
        }
        async with self.session.post(f"{self.base}/verify.json", json=payload) as resp:
            return await resp.json()

    async def close(self):
        await self.session.close()
