"""
ZendanBOT - Tron / Tornado Payment
"""

import aiohttp
from typing import Dict, Any

class TronPayment:
    def __init__(self, api_url: str, wallet: str):
        self.api_url = api_url
        self.wallet = wallet
        self.session = aiohttp.ClientSession()

    async def create_transaction(self, amount_trx: float, order_id: str) -> Dict[str, Any]:
        payload = {
            "wallet": self.wallet,
            "amount": amount_trx,
            "order_id": order_id
        }
        async with self.session.post(self.api_url, json=payload) as resp:
            return await resp.json()

    async def verify(self, txid: str) -> bool:
        # Verify on Tronscan or provider
        return True

    async def close(self):
        await self.session.close()
