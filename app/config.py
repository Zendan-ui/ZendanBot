from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    ADMIN_ID: int = Field(..., env="ADMIN_ID")
    BOT_USERNAME: str = Field(..., env="BOT_USERNAME")
    DOMAIN: str = Field("localhost", env="DOMAIN")
    WEBHOOK_URL: str = Field(None, env="WEBHOOK_URL")
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./zendanbot.db", env="DATABASE_URL")
    DEBUG: bool = Field(True, env="DEBUG")
    SECRET_KEY: str = Field("change-this-in-production", env="SECRET_KEY")
    
    # Request timeout for panels
    REQUEST_EXEC_TIMEOUT: int | None = None

    # ZendanBOT Branding - Pure Professional
    BOT_NAME: str = "ZendanBOT"
    BOT_FULL_NAME: str = "ZendanBOT"
    VERSION: str = "2.0.0 - Professional Secure Edition"
    PROJECT_DESCRIPTION: str = "Advanced Professional VPN Sales & Management Platform"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# For compatibility with original PHP config
APIKEY = settings.BOT_TOKEN
adminnumber = str(settings.ADMIN_ID)
domainhosts = settings.DOMAIN
usernamebot = settings.BOT_USERNAME
