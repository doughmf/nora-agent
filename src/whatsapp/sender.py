# src/whatsapp/sender.py
"""
WhatsApp Sender — Integração com Evolution API.

Correções aplicadas:
- send_message e send_typing_indicator agora aceitam condo_id
- Instância Evolution resolvida dinamicamente por condomínio (multi-tenant)
- Fallback para EVOLUTION_INSTANCE global se não encontrar no banco
"""
import logging
import httpx
from config.settings import EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE

logger = logging.getLogger("syndra.sender")


async def _get_instance(condo_id: str | None) -> str:
    """Resolve a instância Evolution correta para o condomínio."""
    if condo_id:
        try:
            from src.supabase.client import get_evolution_instance
            instance = await get_evolution_instance(condo_id)
            if instance:
                return instance
        except Exception as e:
            logger.warning(f"⚠️  Falha ao buscar instância para condo '{condo_id}': {e}")
    # Fallback para instância global do .env
    return EVOLUTION_INSTANCE


async def send_message(phone: str, message: str, condo_id: str | None = None):
    """Envia mensagem de texto via Evolution API."""
    instance = await _get_instance(condo_id)
    phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EVOLUTION_API_URL}/message/sendText/{instance}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone_clean,
                "text": message,
                "delay": 1000,
                "linkPreview": False
            },
            timeout=10.0
        )
    return response.json()


async def send_typing_indicator(phone: str, condo_id: str | None = None, duration: int = 3):
    """Simula digitação antes de responder (mais natural)."""
    instance = await _get_instance(condo_id)

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{EVOLUTION_API_URL}/chat/sendPresence/{instance}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone,
                "options": {"presence": "composing", "delay": duration * 1000}
            },
            timeout=10.0
        )


async def send_document(phone: str, url: str, filename: str, caption: str = "", condo_id: str | None = None):
    """Envia documento PDF/imagem."""
    instance = await _get_instance(condo_id)

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{EVOLUTION_API_URL}/message/sendMedia/{instance}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={
                "number": phone,
                "mediatype": "document",
                "media": url,
                "fileName": filename,
                "caption": caption
            },
            timeout=10.0
        )
