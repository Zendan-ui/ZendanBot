"""
ZendanBOT Topic Group Support
Full support for Telegram Forum Topics (Groups with Topics).
Routes different reports to dedicated topics for clean organization.
"""

from typing import Dict
from app.database import async_session
from app.models import TopicID
from sqlalchemy.future import select
import logging

logger = logging.getLogger(__name__)

# Topic types from professional requirements
TOPIC_TYPES = {
    "buyreport": "گزارش خرید",
    "paymentreport": "گزارش پرداخت",
    "errorreport": "گزارش خطا",
    "supportreport": "پشتیبانی",
    "otherreport": "سایر گزارش‌ها",
    "testreport": "گزارش اکانت تست",
    "nightreport": "گزارش شبانه",
    "cronreport": "گزارش اتوماسیون",
    "backupreport": "بکاپ",
    "porsantreport": "گزارش پورسانت",
}

async def get_topic_id(report_type: str) -> str:
    """Get the topic ID for a specific report type."""
    async with async_session() as session:
        result = await session.execute(
            select(TopicID).where(TopicID.report == report_type)
        )
        topic = result.scalar_one_or_none()
        if topic:
            return topic.idreport
        return "0"  # Default general topic

async def send_to_topic(bot, chat_id: str, topic_id: str, text: str, **kwargs):
    """Send message to a specific topic in a group."""
    try:
        if topic_id and topic_id != "0":
            kwargs["message_thread_id"] = int(topic_id)
        
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send to topic {topic_id}: {e}")
        # Fallback to general message
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)

async def init_default_topics():
    """Initialize default topic mappings if not exist."""
    async with async_session() as session:
        for key, name in TOPIC_TYPES.items():
            result = await session.execute(
                select(TopicID).where(TopicID.report == key)
            )
            if not result.scalar_one_or_none():
                session.add(TopicID(report=key, idreport="0"))
        await session.commit()
        logger.info("✅ Topic group mappings initialized.")

# Usage example in handlers/cron:
# topic_id = await get_topic_id("buyreport")
# await send_to_topic(bot, GROUP_ID, topic_id, "گزارش خرید جدید...")
