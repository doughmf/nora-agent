# src/whatsapp/webhook.py
from fastapi import APIRouter, Request, BackgroundTasks
from src.supabase.client import resolve_condo_by_instance
from src.agent.syndra import SyndraAgent
from src.whatsapp.sender import send_message
import logging

logger = logging.getLogger("syndra.webhook")
router = APIRouter()

@router.post("/webhook/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recebe webhook da Evolution API."""
    payload = await request.json()
    
    if payload.get("event") != "messages.upsert":
        return {"status": "ignored"}
    
    message_data = payload.get("data", {})
    instance_name = payload.get("instance") # Nome da instância no Evolution
    
    if message_data.get("key", {}).get("fromMe"):
        return {"status": "own_message"}
    
    # Processar em background passando o instance_name
    background_tasks.add_task(process_incoming_message, message_data, instance_name)
    return {"status": "received"}

async def process_incoming_message(data: dict, instance_name: str):
    """Processa mensagem resolvendo o condomínio (Tenant)."""
    # 1. Resolver Condo ID
    condo_id = await resolve_condo_by_instance(instance_name)
    if not condo_id:
        logger.error(f"❌ Instância '{instance_name}' não mapeada para nenhum condomínio.")
        return

    phone = data["key"]["remoteJid"].replace("@s.whatsapp.net", "")
    
    # 2. Extrair conteúdo
    message_type = data.get("messageType", "")
    if message_type == "conversation":
        content = data["message"]["conversation"]
    elif message_type == "extendedTextMessage":
        content = data["message"]["extendedTextMessage"]["text"]
    else:
        content = "[Mensagem não suportada no momento]"
    
    # 3. Inicializar Agente com o Contexto do Condomínio
    agent = SyndraAgent(condo_id=condo_id)
    response = await agent.process(phone=phone, message=content)
    
    # 4. Enviar resposta
    await send_message(phone=phone, message=response)
