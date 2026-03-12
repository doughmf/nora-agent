# SPEC-05: Integrations — WhatsApp + Supabase + APIs

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. VISÃO GERAL DA ARQUITETURA

```
┌─────────────────────────────────────────────────────────┐
│                        VPS Ubuntu 22.04                  │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ Evolution    │    │  FastAPI     │    │  Redis    │ │
│  │ API v2       │◄──►│  (Syndra App)  │◄──►│  (Queue)  │ │
│  │ Port: 8080   │    │  Port: 8000  │    │  Port:    │ │
│  └──────┬───────┘    └──────┬───────┘    │  6379     │ │
│         │                   │            └───────────┘ │
│         │            ┌──────▼───────┐                  │
│  ┌──────▼───────┐    │   LangChain  │                  │
│  │   Nginx      │    │   Agent      │                  │
│  │  (Reverse    │    │   (Syndra)     │                  │
│  │   Proxy)     │    └──────┬───────┘                  │
│  │  Port: 443   │           │                          │
│  └──────────────┘    ┌──────▼───────┐                  │
│                      │  OpenRouter  │                  │
└──────────────────────│ (LLM API)    │──────────────────┘
                       └──────┬───────┘
                              │
                    ┌─────────▼────────┐
                    │    Supabase      │
                    │  (PostgreSQL +   │
                    │   pgvector +     │
                    │   Storage)       │
                    └──────────────────┘
```

---

## 2. INTEGRAÇÃO WHATSAPP — EVOLUTION API v2

### Instalação da Evolution API
```bash
# docker-compose.yml — Serviço Evolution API
evolution-api:
  image: atendai/evolution-api:v2.2.3
  container_name: evolution_api
  restart: always
  ports:
    - "8080:8080"
  environment:
    - SERVER_URL=https://api.seu-dominio.com.br
    - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY}
    - DATABASE_ENABLED=true
    - DATABASE_CONNECTION_URI=postgresql://...
    - RABBITMQ_ENABLED=false
    - WEBHOOK_GLOBAL_URL=https://syndra.seu-dominio.com.br/webhook/whatsapp
    - WEBHOOK_GLOBAL_ENABLED=true
    - WEBHOOK_EVENTS_MESSAGES_UPDATE=true
  volumes:
    - evolution_instances:/evolution/instances
```

### Receber Mensagens (Webhook)
```python
# src/whatsapp/webhook.py
from fastapi import APIRouter, Request, BackgroundTasks
import hmac, hashlib

router = APIRouter()

@router.post("/webhook/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recebe webhook da Evolution API."""
    
    payload = await request.json()
    
    # Filtrar apenas mensagens de texto/áudio/imagem recebidas
    if payload.get("event") != "messages.upsert":
        return {"status": "ignored"}
    
    message_data = payload.get("data", {})
    
    # Ignorar mensagens enviadas pela própria Syndra
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
        content = await transcribe_audio(data)  # Whisper (OpenAI)
    elif message_type == "imageMessage":
        content = await describe_image(data)    # Gemini/OpenAI Vision
    else:
        content = "[Mensagem não suportada]"
    
    # Encaminhar ao agente Syndra
    from agent.syndra import SyndraAgent
    agent = SyndraAgent()
    response = await agent.process(phone=phone, message=content)
    
    # Enviar resposta
    await send_message(phone=phone, message=response)
```

### Enviar Mensagens
```python
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
```

---

## 3. INTEGRAÇÃO SUPABASE

### Cliente Supabase
```python
# src/supabase/client.py
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
import numpy as np

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def semantic_search(query_embedding: list[float], threshold: float = 0.75) -> list[dict]:
    """Busca semântica na base de conhecimento."""
    result = supabase.rpc("search_knowledge", {
        "query_embedding": query_embedding,
        "match_threshold": threshold,
        "match_count": 5
    }).execute()
    return result.data

async def get_or_create_resident(phone: str) -> dict:
    """Retorna residente existente ou cria novo."""
    result = supabase.table("residents") \
        .select("*") \
        .eq("whatsapp_phone", phone) \
        .single() \
        .execute()
    
    if result.data:
        return result.data
    
    # Criar novo residente (onboarding pendente)
    new_resident = supabase.table("residents").insert({
        "whatsapp_phone": phone,
        "profile": {"onboarding_complete": False}
    }).execute()
    
    return new_resident.data[0]

async def save_message(resident_id: str, role: str, content: str, session_id: str, intent: str = None):
    """Salva mensagem no histórico."""
    supabase.table("conversations").insert({
        "resident_id": resident_id,
        "whatsapp_phone": resident_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "intent": intent
    }).execute()

async def get_conversation_history(phone: str, limit: int = 10) -> list[dict]:
    """Recupera histórico recente."""
    result = supabase.table("conversations") \
        .select("role, content, created_at") \
        .eq("whatsapp_phone", phone) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    
    # Reverter para ordem cronológica
    return list(reversed(result.data or []))
```

---

## 4. NÚCLEO DO AGENTE SYNDRA

```python
# src/agent/syndra.py
import os
from openai import AsyncOpenAI # Usado para OpenRouter ou OpenAI
from datetime import datetime
from supabase.client import (
    get_or_create_resident, get_conversation_history,
    save_message, semantic_search
)
from whatsapp.sender import send_typing_indicator
from agent.tools import TOOLS, execute_tool
from agent.prompts import build_system_prompt

# Configuração do cliente (Exemplo com OpenRouter)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

class SyndraAgent:
    def __init__(self):
        self.model = "anthropic/claude-3.5-sonnet" # Nome do modelo no OpenRouter
        self.max_tokens = 1024
    
    async def process(self, phone: str, message: str) -> str:
        """Processa mensagem e retorna resposta."""
        
        # 1. Obter/criar residente
        resident = await get_or_create_resident(phone)
        
        # 2. Recuperar histórico
        history = await get_conversation_history(phone)
        
        # 3. Busca semântica na base de conhecimento
        context_chunks = await self._retrieve_context(message)
        
        # 4. Construir prompt
        system_prompt = build_system_prompt(
            resident=resident,
            knowledge_context=context_chunks,
            current_datetime=datetime.now().isoformat()
        )
        
        # 5. Construir mensagens
        messages = [
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "user", "content": message}
        ]
        
        # 6. Simular digitação
        await send_typing_indicator(phone, duration=2)
        
        # 7. Chamar LLM com ferramentas
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=TOOLS, # Formato precisa ser adaptado dependendo do provedor (ex: OpenAI tools format)
            tool_choice="auto"
        )
        
        # 8. Processar tool calls se necessário
        final_response = await self._handle_tool_calls(response, messages, system_prompt)
        
        # 9. Salvar no histórico
        session_id = f"{phone}_{datetime.now().strftime('%Y%m%d_%H')}"
        await save_message(resident["id"], "user", message, session_id)
        await save_message(resident["id"], "assistant", final_response, session_id)
        
        return final_response
    
    async def _retrieve_context(self, query: str) -> list[dict]:
        """Gera embedding e busca contexto relevante."""
        # Usar Voyage AI ou OpenAI para embeddings
        # embedding = embed(query)
        # return await semantic_search(embedding)
        return []  # Implementar com biblioteca de embeddings
    
    async def _handle_tool_calls(self, response, messages: list, system_prompt: str) -> str:
        """Executa tool calls na resposta (pseudo-código simplificado)."""
        # A implementação exata dependerá do formato retornado pelo OpenRouter/OpenAI
        
        message = response.choices[0].message
        
        while message.tool_calls:
            messages.append(message) # Adiciona assistant
            
            for tool_call in message.tool_calls:
                # Parse function name and args ...
                # result = await execute_tool(name, args)
                # messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
                pass 
            
            # response = await client.chat.completions.create(...)
            # message = response.choices[0].message
            break # Simulação
        
        return message.content or "Desculpe, não consegui processar."
```

---

## 5. VARIÁVEIS DE AMBIENTE

```bash
# config/.env.example

# APIs LLM
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIza...

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=your-secret-key
EVOLUTION_INSTANCE=syndra-condominio

# Redis
REDIS_URL=redis://localhost:6379

# Aplicação
APP_HOST=0.0.0.0
APP_PORT=8000
SECRET_KEY=your-secret-key-here
DEBUG=false

# Condomínio
CONDO_NAME="Residencial Nogueira Martins"
SINDICO_PHONE=+55119XXXXXXXX
ZELADOR_PHONE=+55119XXXXXXXX
PORTARIA_PHONE=+55119XXXXXXXX
```
