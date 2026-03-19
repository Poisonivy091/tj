from app.config.settings import settings
from app.integrations.callmebot_client import send_callmebot_whatsapp
from app.integrations.twilio_client import send_twilio_whatsapp


async def send_whatsapp(message: str, to: str | None = None) -> dict:
    """Send WhatsApp using the configured provider."""
    provider = settings.WHATSAPP_PROVIDER.lower()

    if provider == "callmebot":
        return await send_callmebot_whatsapp(message, phone=to)
    elif provider == "twilio":
        return send_twilio_whatsapp(message, to=to)
    else:
        return {"status": "error", "detail": f"Unknown provider: {provider}"}
