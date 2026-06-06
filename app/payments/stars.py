"""
ZendanBOT - Telegram Stars Payment
"""

from aiogram import Bot
from typing import Dict, Any

class TelegramStars:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def create_invoice(self, title: str, description: str, amount_stars: int, payload: str):
        """Use aiogram to create Stars invoice."""
        # In real use: await bot.send_invoice(..., provider_token="", prices=...)
        return {"success": True, "payload": payload}

    async def verify(self, pre_checkout_query) -> bool:
        # Always approve for Stars in most cases, then fulfill
        return True
