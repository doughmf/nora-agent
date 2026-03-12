"""
Nora Agent — API Principal
Residencial Nogueira Martins
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging, os, secrets
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

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Nora Agent",
        "timestamp": datetime.now().isoformat()
    }

# ─── Configuração Frontend Web ─────────────────────
# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

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

# ─── Segurança do Painel ───────────────────────────
security = HTTPBasic()

def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verifica usuário e senha do painel."""
    correct_username = secrets.compare_digest(credentials.username, os.getenv("ADMIN_USER", "admin"))
    correct_password = secrets.compare_digest(credentials.password, os.getenv("ADMIN_PASS", "nora2026"))
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _admin: str = Depends(authenticate_admin)):
    """Página Web do Painel Admin (Protegida)."""
    
    # Busca real do Supabase
    from src.supabase.client import supabase
    try:
        # Estatísticas
        residents = supabase.table("residents").select("id", count="exact").execute()
        messages = supabase.table("conversations").select("id", count="exact").execute()
        mnt_open = supabase.table("maintenance_requests").select("id", count="exact").eq("status", "aberto").execute()
        res_pend = supabase.table("space_bookings").select("id", count="exact").eq("status", "pendente").execute()
        
        # Últimas listagens
        recent_res = supabase.table("residents").select("*").order("created_at", desc=True).limit(5).execute()
        recent_mnt = supabase.table("maintenance_requests").select("*").order("created_at", desc=True).limit(5).execute()
        
        stats = {
            "residents_count": residents.count or 0,
            "messages_count": messages.count or 0,
            "open_maintenance": mnt_open.count or 0,
            "pending_bookings": res_pend.count or 0
        }
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard: {e}")
        stats = {"residents_count": 0, "messages_count": 0, "open_maintenance": 0, "pending_bookings": 0}
        recent_res = type('obj', (object,), {'data': []})
        recent_mnt = type('obj', (object,), {'data': []})

    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "condo_name": os.getenv("CONDO_NAME", "Residencial Nogueira Martins"),
            "stats": stats,
            "recent_residents": recent_res.data if hasattr(recent_res, 'data') else [],
            "recent_maintenance": recent_mnt.data if hasattr(recent_mnt, 'data') else []
        }
    )

@app.get("/admin/logout")
async def admin_logout():
    """Força o encerramento da sessão simulando um erro 401."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão encerrada com sucesso.",
        headers={"WWW-Authenticate": "Basic"},
    )

