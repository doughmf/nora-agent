# src/whatsapp/webhook.py
from fastapi import APIRouter, Request, BackgroundTasks
import hmac
import hashlib

router = APIRouter()

@router.post("/webhook/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recebe webhook da Evolution API."""
    
    payload = await request.json()
    
    # Filtrar apenas mensagens de texto/áudio/imagem recebidas
    if payload.get("event") != "messages.upsert":
        return {"status": "ignored"}
    
    message_data = payload.get("data", {})
    
    # Ignorar mensagens enviadas pela própria Nora
    if message_data.get("key", {}).get("fromMe"):
        return {"status": "own_message"}
    
    # Processar em background (resposta rápida ao webhook)
    background_tasks.add_task(process_incoming_message, message_data)
    
    return {"status": "received"}

async def process_incoming_message(data: dict):
    """Processa mensagem recebida em background."""
    phone = data["key"]["remoteJid"].replace("@s.whatsapp.net", "")
    
    # Extrair conteúdo por tipo
    message_type = data.get("messageType", "")
    
    if message_type == "conversation":
        content = data["message"]["conversation"]
    elif message_type == "extendedTextMessage":
        content = data["message"]["extendedTextMessage"]["text"]
    elif message_type == "audioMessage":
        # Placeholder for transcibe
        # content = await transcribe_audio(data)  # Whisper (OpenAI)
        content = "[Áudio recebido, transcrição não implementada]"
    elif message_type == "imageMessage":
        # Placeholder for vision
        # content = await describe_image(data)    # Gemini/OpenAI Vision
        content = "[Imagem recebida, visão não implementada]"
    else:
        content = "[Mensagem não suportada]"
    
    # Encaminhar ao agente Nora
    from src.agent.nora import NoraAgent
    from src.whatsapp.sender import send_message
    
    agent = NoraAgent()
    response = await agent.process(phone=phone, message=content)
    
    # Enviar resposta
    await send_message(phone=phone, message=response)
