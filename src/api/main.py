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
import logging, os, secrets, jwt, bcrypt
from datetime import datetime, timedelta
from src.api.settings_manager import get_setting, set_setting

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
from fastapi import Form
from fastapi.responses import RedirectResponse
from src.supabase.client import supabase

JWT_SECRET = os.getenv("SECRET_KEY", secrets.token_hex(32))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

def authenticate_admin(request: Request):
    """Verifica se o usuário possui sessão JWT ativa nos cookies."""
    session_token = request.cookies.get("nora_admin_session")
    
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado")
    
    try:
        payload = jwt.decode(session_token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = payload
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada")

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Página Web de Login."""
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"condo_name": get_setting("CONDO_NAME", "Residencial Nogueira Martins")}
    )

@app.post("/admin/login")
async def admin_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Busca o usuário no banco, valida e cria sessão JWT."""
    
    # Validação contra o banco de dados
    try:
        res = supabase.table("system_users").select("*").eq("username", username).execute()
        user_data = res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar usuário: {e}")
        user_data = None
        
    if not user_data or not bcrypt.checkpw(password.encode('utf-8'), user_data["password_hash"].encode('utf-8')):
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={
                "condo_name": get_setting("CONDO_NAME", "Residencial Nogueira Martins"),
                "error": "Usuário ou senha incorretos."
            }
        )
    
    # Assina JWT contendo username, nome e role (admin, sindico, colaborador)
    token_payload = {
        "sub": user_data["username"],
        "name": user_data["name"],
        "role": user_data["role"]
    }
    jwt_token = create_access_token(token_payload)
    
    # Redireciona e seta o cookie
    response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="nora_admin_session",
        value=jwt_token,
        httponly=True,
        max_age=3600 * 24 # 1 dia
    )
    return response

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user_session: dict = Depends(authenticate_admin)):
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
            "condo_name": get_setting("CONDO_NAME", "Residencial Nogueira Martins"),
            "stats": stats,
            "recent_residents": recent_res.data if hasattr(recent_res, 'data') else [],
            "recent_maintenance": recent_mnt.data if hasattr(recent_mnt, 'data') else [],
            "user": user_session
        }
    )

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    """Página Web de Configurações (exclusiva para admins)."""
    
    if user_session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para administradores.")
        
    # Carrega as configurações principais para alimentar os campos baseados na lista original    
    keys_to_load = [
        "CONDO_NAME", "CONDO_CNPJ", "CONDO_ADDRESS", "SINDICO_NAME", "SINDICO_PHONE",
        "ZELADOR_NAME", "ZELADOR_PHONE", "PORTARIA_PHONE", "ADMINISTRADORA_PHONE",
        "SALAO_PRECO_NOITE", "SALAO_PRECO_DIA", "CHURRASQUEIRA_PRECO", "PIX_CHAVE", "PIX_NOME"
    ]
    
    current_settings = {k: get_setting(k) for k in keys_to_load}
    
    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={
            "condo_name": get_setting("CONDO_NAME", "Residencial Nogueira Martins"),
            "user": user_session,
            "settings": current_settings
        }
    )

@app.post("/admin/settings", response_class=HTMLResponse)
async def admin_settings_save(request: Request, user_session: dict = Depends(authenticate_admin)):
    """Processa o salvamento do formulário de configs."""
    
    if user_session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para administradores.")
        
    form_data = await request.form()
    
    for key, value in form_data.items():
        set_setting(key, str(value))
        
    # Recarrega para mostrar form atualizado
    current_settings = {k: get_setting(k) for k in form_data.keys()}
    
    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={
            "condo_name": get_setting("CONDO_NAME", "Residencial Nogueira Martins"),
            "user": user_session,
            "settings": current_settings,
            "message": "Configurações Globais atualizadas com sucesso!"
        }
    )

@app.get("/admin/logout")
async def admin_logout():
    """Encerra a sessão limpando o cookie."""
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("nora_admin_session")
    return response
