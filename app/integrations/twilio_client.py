import os
from app.config.settings import settings


def send_twilio_whatsapp(message: str, to: str | None = None) -> dict:
    """Send a WhatsApp message via Twilio."""
    from twilio.rest import Client

    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_WHATSAPP_FROM
    recipient = to or settings.TWILIO_WHATSAPP_TO

    if not recipient:
        return {"status": "error", "detail": "No recipient. Set TWILIO_WHATSAPP_TO or pass 'to'."}
    if not recipient.startswith("whatsapp:"):
        recipient = f"whatsapp:{recipient}"
    if not account_sid or not auth_token:
        return {"status": "error", "detail": "Twilio credentials not configured."}

    client = Client(account_sid, auth_token)
    msg = client.messages.create(body=message, from_=from_number, to=recipient)
    return {"status": "sent", "detail": f"Message SID: {msg.sid}"}
