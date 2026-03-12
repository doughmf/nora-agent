# src/whatsapp/webhook.py
"""
Webhook WhatsApp — Recebe e roteia mensagens da Evolution API.

Correções aplicadas:
- Validação dos campos obrigatórios do payload antes de processar
- instance_name extraído e passado corretamente para process_incoming_message
- Suporte a audioMessage com fallback descritivo
- Router registrado em main.py (não duplicado)
"""
import logging
from fastapi import APIRouter, Request, BackgroundTasks
from src.supabase.client import resolve_condo_by_instance
from src.agent.syndra import get_agent
from src.whatsapp.sender import send_message

logger = logging.getLogger("syndra.webhook")
router = APIRouter()


async def process_incoming_message(data: dict, instance_name: str):
    """Processa mensagem resolvendo o condomínio (Tenant)."""

    # 1. Resolver Condo ID
    condo_id = await resolve_condo_by_instance(instance_name)
    if not condo_id:
        logger.error(f"❌ Instância '{instance_name}' não mapeada para nenhum condomínio.")
        return

    # 2. Extrair e validar campos obrigatórios
    key = data.get("key", {})
    remote_jid = key.get("remoteJid", "")
    if not remote_jid:
        logger.warning("⚠️  Payload sem remoteJid, ignorando.")
        return

    phone = remote_jid.replace("@s.whatsapp.net", "")

    # 3. Extrair conteúdo por tipo de mensagem
    message_type = data.get("messageType", "")
    message_obj = data.get("message", {})

    if message_type == "conversation":
        content = message_obj.get("conversation", "")
    elif message_type == "extendedTextMessage":
        content = message_obj.get("extendedTextMessage", {}).get("text", "")
    elif message_type == "audioMessage":
        content = "[Mensagem de áudio recebida — transcrição não disponível no momento]"
    elif message_type == "imageMessage":
        content = message_obj.get("imageMessage", {}).get("caption", "[Imagem recebida]")
    else:
        content = "[Tipo de mensagem não suportado no momento]"

    if not content:
        logger.warning(f"⚠️  Mensagem vazia do tipo '{message_type}', ignorando.")
        return

    logger.info(f"📩 [{condo_id}] Mensagem de {phone}: {content[:60]}...")

    # 4. Inicializar Agente via cache (evita recriar a cada mensagem)
    agent = get_agent(condo_id)

    try:
        response = await agent.process(phone=phone, message=content)
    except Exception as e:
        logger.error(f"❌ Erro no agente para condo '{condo_id}', phone '{phone}': {e}", exc_info=True)
        response = "Desculpe, ocorreu um erro interno. Tente novamente em instantes."

    # 5. Enviar resposta com a instância correta
    await send_message(phone=phone, message=response, condo_id=condo_id)
