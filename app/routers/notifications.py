from fastapi import APIRouter
from app.models.schemas import WhatsAppRequest, WhatsAppResponse
from app.services.notifications import send_whatsapp

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.post("/whatsapp", response_model=WhatsAppResponse)
async def send_whatsapp_message(req: WhatsAppRequest):
    """Send a WhatsApp message via configured provider (CallMeBot or Twilio)."""
    result = await send_whatsapp(req.message, to=req.to)
    return result
