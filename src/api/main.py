"""
Syndra Agent — API Principal

Correções aplicadas:
- Webhook unificado: usa process_incoming_message de webhook.py (com instance_name)
- Rota /admin/debug-info protegida por autenticação
- CORS restrito ao domínio real (via env DOMAIN)
- JWT_SECRET obrigatório — falha explicitamente se não configurado
- Cookie de sessão com secure=True em produção
- Rota de admin/broadcast implementada com fila básica
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, Depends, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
import logging, os, secrets, jwt, bcrypt
from datetime import datetime, timedelta
from src.api.settings_manager import get_setting, set_setting
from config.settings import settings

# ─── Logging ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("syndra")

# ─── JWT Secret — obrigatório em produção ──────────
JWT_SECRET = settings.SECRET_KEY
if not JWT_SECRET:
    if settings.DEBUG:
        JWT_SECRET = secrets.token_hex(32)
        logger.warning("⚠️  SECRET_KEY não definida — usando valor aleatório (apenas para DEBUG)")
    else:
        raise RuntimeError("❌ SECRET_KEY deve ser definida no .env em produção!")

# ─── CORS — restrito ao domínio configurado ────────
ALLOWED_ORIGINS = [f"https://{settings.DOMAIN}"] if settings.DOMAIN else ["http://localhost:3000"]

# ─── Lifespan ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏠 Syndra Agent iniciando...")
    yield
    logger.info("🔴 Syndra Agent encerrando...")

# ─── App ───────────────────────────────────────────
app = FastAPI(
    title="Syndra Agent API",
    description="IA do Residencial Nogueira Martins",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─── Templates ─────────────────────────────────────
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# ─── Supabase ──────────────────────────────────────
from src.supabase.client import supabase


# ─── Health ────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Syndra Agent",
        "version": "1.1.0",
        "timestamp": datetime.now().isoformat()
    }


# ─── Exception Handler ─────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erro não tratado: {exc}", exc_info=True)
    # Em produção: não expor traceback
    if settings.DEBUG:
        import traceback
        return HTMLResponse(
            content=f"<h1>Error 500 - Debug</h1><pre>{traceback.format_exc()}</pre>",
            status_code=500
        )
    return HTMLResponse(content="<h1>Erro interno do servidor</h1>", status_code=500)


# ─── Webhook WhatsApp (unificado) ──────────────────
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe mensagens da Evolution API."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Payload inválido")

    event = payload.get("event", "")
    logger.info(f"📨 Evento recebido: {event}")

    if event != "messages.upsert":
        return {"status": "ignored", "event": event}

    data = payload.get("data", {})
    instance_name = payload.get("instance", "")

    if data.get("key", {}).get("fromMe"):
        return {"status": "own_message"}

    if not instance_name:
        logger.warning("⚠️  Webhook sem instance_name — ignorando")
        return {"status": "ignored", "reason": "missing_instance"}

    # Processar em background (resposta imediata ao webhook)
    from src.whatsapp.webhook import process_incoming_message
    background_tasks.add_task(process_incoming_message, data, instance_name)

    return {"status": "received"}


# ─── Admin: Segurança JWT ──────────────────────────
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=1)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")


def authenticate_admin(request: Request) -> dict:
    """Verifica se o usuário possui sessão JWT ativa nos cookies."""
    session_token = request.cookies.get("syndra_admin_session")
    if not session_token:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/admin/login"})
    try:
        payload = jwt.decode(session_token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = payload
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/admin/login"})


# ─── Admin: Login ──────────────────────────────────
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"condo_name": "Syndra SaaS"}
    )


@app.post("/admin/login")
async def admin_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        res = supabase.table("system_users").select("*").eq("username", username).execute()
        user_data = res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar usuário: {e}")
        user_data = None

    if not user_data or not bcrypt.checkpw(password.encode("utf-8"), user_data["password_hash"].encode("utf-8")):
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={"condo_name": "Syndra SaaS", "error": "Usuário ou senha incorretos."}
        )

    token_payload = {
        "sub": user_data["username"],
        "name": user_data["name"],
        "role": user_data["role"],
        "condo_id": user_data["condo_id"]
    }
    jwt_token = create_access_token(token_payload)

    response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="syndra_admin_session",
        value=jwt_token,
        httponly=True,
        secure=not settings.DEBUG,   # HTTPS em produção
        samesite="lax",
        max_age=3600 * 24
    )
    return response


# ─── Admin: Dashboard ──────────────────────────────
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")

    try:
        residents = supabase.table("residents").select("id", count="exact").eq("condo_id", condo_id).execute()
        messages = supabase.table("conversations").select("id", count="exact").eq("condo_id", condo_id).execute()
        mnt_open = supabase.table("maintenance_requests").select("id", count="exact").eq("condo_id", condo_id).eq("status", "aberto").execute()
        res_pend = supabase.table("space_bookings").select("id", count="exact").eq("condo_id", condo_id).eq("status", "pendente").execute()
        recent_res = supabase.table("residents").select("*").eq("condo_id", condo_id).order("created_at", desc=True).limit(5).execute()
        recent_mnt = supabase.table("maintenance_requests").select("*").eq("condo_id", condo_id).order("created_at", desc=True).limit(5).execute()
        stats = {
            "residents_count": residents.count or 0,
            "messages_count": messages.count or 0,
            "open_maintenance": mnt_open.count or 0,
            "pending_bookings": res_pend.count or 0
        }
    except Exception as e:
        logger.error(f"Erro dashboard: {e}")
        stats = {"residents_count": 0, "messages_count": 0, "open_maintenance": 0, "pending_bookings": 0}
        recent_res = type("obj", (object,), {"data": []})()
        recent_mnt = type("obj", (object,), {"data": []})()

    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "condo_name": get_setting(condo_id, "CONDO_NAME", "Residencial Nogueira Martins"),
            "stats": stats,
            "recent_residents": recent_res.data if hasattr(recent_res, "data") else [],
            "recent_maintenance": recent_mnt.data if hasattr(recent_mnt, "data") else [],
            "user": user_session
        }
    )


# ─── Admin: Settings ───────────────────────────────
@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")
    if user_session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para administradores.")

    keys_to_load = [
        "AGENT_NAME", "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY",
        "CONDO_NAME", "CONDO_CNPJ", "CONDO_ADDRESS",
        "SINDICO_NAME", "SINDICO_PHONE", "ZELADOR_NAME", "ZELADOR_PHONE",
        "PORTARIA_PHONE", "ADMINISTRADORA_PHONE",
        "SALAO_PRECO_NOITE", "SALAO_PRECO_DIA", "CHURRASQUEIRA_PRECO",
        "PIX_TIPO", "PIX_CHAVE", "PIX_NOME"
    ]
    current_settings = {k: get_setting(condo_id, k) for k in keys_to_load}

    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={
            "condo_name": get_setting(condo_id, "CONDO_NAME", "Residencial Nogueira Martins"),
            "user": user_session,
            "settings": current_settings
        }
    )


@app.post("/admin/settings", response_class=HTMLResponse)
async def admin_settings_save(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")
    if user_session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso exclusivo para administradores.")

    form_data = await request.form()
    for key, value in form_data.items():
        set_setting(condo_id, key, str(value))

    # Invalida cache após salvar para forçar reload
    from src.api.settings_manager import invalidate_cache
    invalidate_cache(condo_id)

    current_settings = {k: get_setting(condo_id, k) for k in form_data.keys()}
    return templates.TemplateResponse(
        request=request, name="settings.html",
        context={
            "condo_name": get_setting(condo_id, "CONDO_NAME", "Residencial Nogueira Martins"),
            "user": user_session,
            "settings": current_settings,
            "message": "Configurações atualizadas com sucesso!"
        }
    )


# ─── Admin: Broadcast ──────────────────────────────
@app.post("/admin/broadcast")
async def send_broadcast(
    request: Request,
    background_tasks: BackgroundTasks,
    x_admin_key: str = Header(None)
):
    """Envia comunicado para todos os moradores do condomínio."""
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")

    body = await request.json()
    title = body.get("title")
    content = body.get("content")
    condo_id = body.get("condo_id")
    audience = body.get("audience", "todos")

    if not title or not content or not condo_id:
        raise HTTPException(400, "title, content e condo_id são obrigatórios")

    background_tasks.add_task(_do_broadcast, condo_id, title, content, audience)
    logger.info(f"📢 Broadcast enfileirado: '{title}' → {audience} (condo: {condo_id})")
    return {"status": "queued", "title": title, "audience": audience}


async def _do_broadcast(condo_id: str, title: str, content: str, audience: str):
    """Envia mensagem para todos os moradores ativos do condomínio."""
    from src.whatsapp.sender import send_message
    try:
        query = supabase.table("residents").select("whatsapp_phone").eq("condo_id", condo_id).eq("active", True)
        if audience == "proprietarios":
            query = query.eq("is_owner", True)
        elif audience == "inquilinos":
            query = query.eq("is_owner", False)
        residents = query.execute()

        message = f"📢 *{title}*\n\n{content}"
        for r in (residents.data or []):
            phone = r.get("whatsapp_phone")
            if phone:
                try:
                    await send_message(phone, message, condo_id=condo_id)
                except Exception as e:
                    logger.error(f"❌ Falha ao enviar broadcast para {phone}: {e}")
        logger.info(f"✅ Broadcast concluído para {len(residents.data or [])} moradores")
    except Exception as e:
        logger.error(f"❌ Erro no broadcast: {e}", exc_info=True)


# ─── Admin: Stats ──────────────────────────────────
@app.get("/admin/stats")
async def get_stats(x_admin_key: str = Header(None)):
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")
    return {"status": "ok", "message": "Estatísticas em desenvolvimento"}


# ─── Admin: Debug (apenas em DEBUG=True) ───────────
@app.get("/admin/debug-info")
async def debug_info(user_session: dict = Depends(authenticate_admin)):
    """Informações de debug — requer autenticação e DEBUG=True."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Rota disponível apenas em modo DEBUG.")
    return {
        "cwd": os.getcwd(),
        "files_in_api": os.listdir("src/api") if os.path.exists("src/api") else [],
        "templates_exist": os.path.exists("src/api/templates/login.html"),
        "env_vars": [k for k in os.environ.keys() if "KEY" not in k and "TOKEN" not in k and "PASS" not in k and "SECRET" not in k]
    }


# ─── Admin: Logout ─────────────────────────────────
@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("syndra_admin_session")
    return response
