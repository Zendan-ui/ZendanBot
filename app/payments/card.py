# Card to Card Payment Handler - Professional & Complete + Secure
from app.database import async_session
from app.models import PaymentReport, User
from app.security import sanitize_text, validate_amount, payment_rate_limiter
import logging

logger = logging.getLogger(__name__)

async def process_card_receipt(user_id: str, amount: int, photo_id: str, note: str = ""):
    """Full secure card-to-card receipt processing"""
    if not payment_rate_limiter.is_allowed(user_id):
        return False, "Rate limit exceeded"

    safe_amount = validate_amount(amount)
    if not safe_amount:
        return False, "Invalid amount"

    safe_note = sanitize_text(note, 500)

    async with async_session() as session:
        report = PaymentReport(
            id_user=user_id,
            price=str(safe_amount),
            Payment_Method="کارت به کارت",
            payment_Status="در انتظار تایید",
            time=str(int(__import__('time').time())),
            dec_not_confirmed=safe_note
        )
        session.add(report)
        await session.commit()

        logger.info(f"Secure card receipt received from {user_id} - Amount: {safe_amount}")
        return True, "Receipt registered successfully. Admin will review."
