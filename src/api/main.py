"""
Nora Agent — API Principal
Residencial Nogueira Martins
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging, os
from datetime import datetime

# ─── Logging ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nora")

# ─── Lifespan ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏠 Nora Agent iniciando...")
    yield
    logger.info("🔴 Nora Agent encerrando...")

# ─── App ───────────────────────────────────────────
app = FastAPI(
    title="Nora Agent API",
    description="IA do Residencial Nogueira Martins",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─── Health Check ──────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Nora Agent",
        "timestamp": datetime.now().isoformat()
    }

# ─── Webhook WhatsApp ──────────────────────────────
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe mensagens da Evolution API."""
    
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Payload inválido")
    
    event = payload.get("event", "")
    logger.info(f"📨 Evento recebido: {event}")
    
    # Processar apenas mensagens recebidas
    if event != "messages.upsert":
        return {"status": "ignored", "event": event}
    
    data = payload.get("data", {})
    
    # Ignorar mensagens próprias
    if data.get("key", {}).get("fromMe"):
        return {"status": "own_message"}
    
    # Processar em background (resposta imediata ao webhook)
    background_tasks.add_task(handle_message, data)
    
    return {"status": "received"}


async def handle_message(data: dict):
    """Processa mensagem em background."""
    try:
        from src.whatsapp.webhook import process_incoming_message
        await process_incoming_message(data)
    except Exception as e:
        logger.error(f"❌ Erro ao processar mensagem: {e}", exc_info=True)


# ─── Admin Endpoints ───────────────────────────────
@app.post("/admin/broadcast")
async def send_broadcast(
    request: Request,
    x_admin_key: str = Header(None)
):
    """Envia comunicado para todos os moradores."""
    
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")
    
    body = await request.json()
    title = body.get("title")
    content = body.get("content")
    audience = body.get("audience", "todos")
    
    if not title or not content:
        raise HTTPException(400, "title e content são obrigatórios")
    
    # TODO: Implementar lógica de broadcast
    logger.info(f"📢 Broadcast solicitado: {title} → {audience}")
    
    return {"status": "queued", "title": title, "audience": audience}


@app.get("/admin/stats")
async def get_stats(x_admin_key: str = Header(None)):
    """Estatísticas do sistema."""
    
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")
    
    # TODO: Buscar do Supabase
    return {
        "status": "ok",
        "message": "Estatísticas em desenvolvimento"
    }
