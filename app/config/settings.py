import os
from pathlib import Path

from dotenv import load_dotenv

# Auto-load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    """All configuration from environment variables."""

    # Finnhub
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")

    # NewsAPI
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

    # Alpha Vantage
    ALPHA_VANTAGE_KEY: str = os.getenv("ALPHA_VANTAGE_KEY", "")

    # Twilio (WhatsApp)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    TWILIO_WHATSAPP_TO: str = os.getenv("TWILIO_WHATSAPP_TO", "")

    # CallMeBot (free WhatsApp alternative)
    CALLMEBOT_API_KEY: str = os.getenv("CALLMEBOT_API_KEY", "")
    CALLMEBOT_PHONE: str = os.getenv("CALLMEBOT_PHONE", "")

    # Claude / Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Database
    DB_PATH: str = os.getenv("TJ_DB_PATH", "tj.db")

    # Notification preference: "callmebot" or "twilio"
    WHATSAPP_PROVIDER: str = os.getenv("WHATSAPP_PROVIDER", "callmebot")


settings = Settings()
