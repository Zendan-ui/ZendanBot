"""
ZendanBOT - AqayePardakht Gateway
"""

import aiohttp
from typing import Dict, Any

class AqayePardakht:
    def __init__(self, pin: str):
        self.pin = pin
        self.session = aiohttp.ClientSession()

    async def create_link(self, amount: int, invoice_id: str, callback: str) -> Dict[str, Any]:
        payload = {
            "pin": self.pin,
            "amount": amount,
            "invoice_id": invoice_id,
            "callback": callback
        }
        async with self.session.post("https://aqayepardakht.ir/api/v2/create", json=payload) as resp:
            return await resp.json()

    async def close(self):
        await self.session.close()
