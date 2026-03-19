import httpx
import urllib.parse
from app.config.settings import settings


async def send_callmebot_whatsapp(message: str, phone: str | None = None) -> dict:
    """Send a WhatsApp message via CallMeBot (free)."""
    phone_number = phone or settings.CALLMEBOT_PHONE
    api_key = settings.CALLMEBOT_API_KEY

    if not phone_number or not api_key:
        return {
            "status": "error",
            "detail": "CallMeBot not configured. Set CALLMEBOT_PHONE and CALLMEBOT_API_KEY.",
        }

    encoded_msg = urllib.parse.quote_plus(message)
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone_number}&text={encoded_msg}&apikey={api_key}"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)

    if resp.status_code == 200:
        return {"status": "sent", "detail": "Message sent via CallMeBot"}
    else:
        return {"status": "error", "detail": f"CallMeBot returned {resp.status_code}: {resp.text}"}
