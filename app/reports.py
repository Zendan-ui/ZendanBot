"""Reporting to an admin group, optionally into forum topics (threads).

Settings used:
  report_chat_id            -> the group/channel id to receive reports
  topic_<kind>              -> optional message_thread_id for that report kind

Report kinds: buy, payment, test, support, agent, error, cron, night
If a topic id is not set, the report goes to the group's general thread.
"""
from __future__ import annotations

import logging

from app.models import get_setting

logger = logging.getLogger(__name__)

KINDS = ("buy", "payment", "test", "support", "agent", "error", "cron", "night")


async def send_report(bot, kind: str, text: str) -> None:
    chat = await get_setting("report_chat_id", "")
    if not chat:
        return
    kwargs = {}
    topic = await get_setting(f"topic_{kind}", "")
    if topic and topic.lstrip("-").isdigit():
        kwargs["message_thread_id"] = int(topic)
    try:
        await bot.send_message(chat, text, **kwargs)
    except Exception as exc:  # noqa: BLE001
        # fall back to general thread if the topic id is wrong
        logger.warning("report send failed (%s): %s", kind, exc)
        try:
            await bot.send_message(chat, text)
        except Exception:  # noqa: BLE001
            pass
