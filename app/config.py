from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = Field("test_token", alias="BOT_TOKEN")
    ADMIN_ID: int = Field(123456789, alias="ADMIN_ID")
    BOT_USERNAME: str = Field("testbot", alias="BOT_USERNAME")
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./zendanbot.db", alias="DATABASE_URL")
    DEBUG: bool = Field(True, alias="DEBUG")

    # Branding
    BOT_FULL_NAME: str = "ZendanBot"
    VERSION: str = "3.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True
        extra = "ignore"


settings = Settings()
