# src/whatsapp/sender.py
import httpx
from config.settings import EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE

async def send_message(phone: str, message: str):
    """Envia mensagem de texto via Evolution API."""
    
    # Formatar número
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone_clean,
                "text": message,
                "delay": 1000,          # 1s de delay (mais natural)
                "linkPreview": False
            }
        )
    
    return response.json()

async def send_typing_indicator(phone: str, duration: int = 3):
    """Simula digitação antes de responder (mais natural)."""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{EVOLUTION_API_URL}/chat/sendPresence/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone,
                "options": {"presence": "composing", "delay": duration * 1000}
            }
        )

async def send_document(phone: str, url: str, filename: str, caption: str = ""):
    """Envia documento PDF/imagem."""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone,
                "mediatype": "document",
                "media": url,
                "fileName": filename,
                "caption": caption
            }
        )
