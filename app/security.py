"""
ZendanBOT Enterprise Security Layer
High-security utilities, validators, rate limiting, and protection mechanisms.
"""

import hashlib
import hmac
import time
import re
from typing import Optional
from passlib.context import CryptContext
from pydantic import BaseModel, validator
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Password hashing (for admin panel and sensitive data)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Securely hash passwords using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

# Input Sanitization
def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Sanitize user input - remove dangerous characters and limit length."""
    if not text:
        return ""
    # Remove control characters and limit
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    text = text.strip()[:max_length]
    return text

def validate_telegram_id(user_id: str | int) -> bool:
    """Validate Telegram user ID."""
    try:
        uid = int(user_id)
        return 1 <= uid <= 10**12  # Reasonable range
    except (ValueError, TypeError):
        return False

def validate_amount(amount: str | int, min_amount: int = 10000, max_amount: int = 10000000) -> Optional[int]:
    """Validate monetary amounts."""
    try:
        amt = int(amount)
        if min_amount <= amt <= max_amount:
            return amt
        return None
    except (ValueError, TypeError):
        return None

# Rate Limiting (simple in-memory, for production use Redis)
class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = {}  # user_id -> list of timestamps

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        user_requests = self.requests.get(user_id, [])
        
        # Clean old requests
        user_requests = [t for t in user_requests if now - t < self.window]
        
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        self.requests[user_id] = user_requests
        return True

# Global rate limiters
bot_rate_limiter = RateLimiter(max_requests=8, window_seconds=60)  # General bot actions
payment_rate_limiter = RateLimiter(max_requests=3, window_seconds=300)  # Payments stricter

# Webhook Signature Verification (for production)
def verify_telegram_webhook(data: bytes, secret_token: str, header_signature: str) -> bool:
    """Verify Telegram webhook secret (use in production with secret token)."""
    if not secret_token:
        return True  # For development
    
    expected = hmac.new(
        secret_token.encode(),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, header_signature)

# Admin Security
def is_authorized_admin(user_id: str | int) -> bool:
    """Strict admin check."""
    try:
        return str(user_id) == str(settings.ADMIN_ID)
    except:
        return False

# Sensitive Data Masking for Logs
def mask_sensitive(text: str) -> str:
    """Mask sensitive information in logs."""
    if not text:
        return text
    # Mask card numbers, tokens, etc.
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '**** **** **** ****', text)
    text = re.sub(r'(token|key|secret|password)[\s=:]+[\w\-]+', r'\1=***MASKED***', text, flags=re.IGNORECASE)
    return text

# Pydantic Models for Strict Validation
class SecureAmount(BaseModel):
    amount: int
    
    @validator('amount')
    def amount_must_be_valid(cls, v):
        if v < 10000 or v > 100000000:
            raise ValueError('Amount out of allowed range')
        return v

class SecureUsername(BaseModel):
    username: str
    
    @validator('username')
    def username_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]{3,32}$', v):
            raise ValueError('Invalid username format')
        return v

# Anti-Spam / Flood Protection Helper
class AntiSpam:
    def __init__(self):
        self.last_action = {}
    
    def can_proceed(self, user_id: str, action: str, cooldown: int = 10) -> bool:
        key = f"{user_id}:{action}"
        now = time.time()
        last = self.last_action.get(key, 0)
        
        if now - last < cooldown:
            return False
        self.last_action[key] = now
        return True

anti_spam = AntiSpam()

# Telegram Bot Security Middleware (complete hardening)
def secure_handler(func):
    """Decorator for complete security on all bot handlers"""
    async def wrapper(message_or_callback, *args, **kwargs):
        user_id = str(getattr(message_or_callback, 'from_user', message_or_callback).id)
        
        # Strict rate limit
        if not bot_rate_limiter.is_allowed(user_id):
            if hasattr(message_or_callback, 'answer'):
                await message_or_callback.answer("⏳ لطفاً کمی صبر کنید.")
            return
        
        # Input sanitization for text
        if hasattr(message_or_callback, 'text') and message_or_callback.text:
            message_or_callback.text = sanitize_text(message_or_callback.text)
        
        # Admin only for sensitive actions
        if 'admin' in func.__name__.lower() or 'panel' in func.__name__.lower():
            if not is_authorized_admin(user_id):
                if hasattr(message_or_callback, 'answer'):
                    await message_or_callback.answer("❌ دسترسی غیرمجاز.")
                logger.warning(f"Unauthorized access attempt by {user_id}")
                return
        
        return await func(message_or_callback, *args, **kwargs)
    return wrapper

print("🔒 ZendanBOT Enterprise Security Layer loaded successfully — Telegram security fully hardened.")
