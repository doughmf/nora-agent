"""
Syndra Agent — API Principal (SaaS Multi-tenant)

Fluxo de autenticação:
- Login → super_admin vê tela de seleção de condomínio
- condo_admin vai direto ao dashboard do seu condomínio
- Dropdown no dashboard para trocar de condomínio (super_admin)
- CRUD completo de condomínios
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, Depends, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
import logging, os, secrets, jwt, bcrypt, hashlib, uuid
from datetime import datetime, timedelta
from src.api.settings_manager import get_setting, set_setting, invalidate_cache
from config.settings import settings

# ─── Logging ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("syndra")

# ─── JWT Secret ────────────────────────────────────────────
JWT_SECRET = settings.SECRET_KEY
if not JWT_SECRET:
    seed = f"{settings.SUPABASE_URL}{settings.SUPABASE_SERVICE_KEY}"
    JWT_SECRET = hashlib.sha256(seed.encode()).hexdigest()
    logger.warning("⚠️  SECRET_KEY não definida — JWT derivado do Supabase. Defina SECRET_KEY no .env.")

# ─── CORS ──────────────────────────────────────────────────
ALLOWED_ORIGINS = [f"https://{settings.DOMAIN}"] if settings.DOMAIN else ["*"]

# ─── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏠 Syndra Agent iniciando...")
    yield
    logger.info("🔴 Syndra Agent encerrando...")

# ─── App ───────────────────────────────────────────────────
app = FastAPI(title="Syndra Agent API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

from src.supabase.client import supabase

# ─── Helpers JWT ───────────────────────────────────────────
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(days=1)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

def authenticate_admin(request: Request) -> dict:
    token = request.cookies.get("syndra_admin_session")
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = payload
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})

def is_super_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "super_admin")

def _set_session_cookie(response, token: str):
    response.set_cookie(
        key="syndra_admin_session", value=token,
        httponly=True, secure=not settings.DEBUG,
        samesite="lax", max_age=3600 * 24
    )

# ─── Health ────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "Syndra Agent", "version": "2.0.0", "timestamp": datetime.now().isoformat()}

# ─── Exception Handler ─────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erro não tratado em {request.url}: {exc}", exc_info=True)
    if settings.DEBUG:
        import traceback
        return HTMLResponse(f"<h1>Error 500</h1><pre>{traceback.format_exc()}</pre>", status_code=500)
    return HTMLResponse("<h1>Erro interno do servidor</h1>", status_code=500)

# ─── Webhook WhatsApp ──────────────────────────────────────
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Payload inválido")

    event = payload.get("event", "")
    if event != "messages.upsert":
        return {"status": "ignored", "event": event}

    data = payload.get("data", {})
    instance_name = payload.get("instance", "")

    if data.get("key", {}).get("fromMe"):
        return {"status": "own_message"}

    if not instance_name:
        return {"status": "ignored", "reason": "missing_instance"}

    from src.whatsapp.webhook import process_incoming_message
    background_tasks.add_task(process_incoming_message, data, instance_name)
    return {"status": "received"}

# ════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"condo_name": "Syndra SaaS"})

@app.post("/admin/login")
async def admin_login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        res = supabase.table("system_users").select("*").eq("username", username).execute()
        user_data = res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Erro ao buscar usuário: {e}")
        user_data = None

    if not user_data or not bcrypt.checkpw(password.encode("utf-8"), user_data["password_hash"].encode("utf-8")):
        return templates.TemplateResponse(request=request, name="login.html",
            context={"condo_name": "Syndra SaaS", "error": "Usuário ou senha incorretos."})

    role = user_data.get("role", "condo_admin")
    condo_id = user_data.get("condo_id")

    token_payload = {
        "sub": user_data["username"],
        "name": user_data["name"],
        "role": role,
        "condo_id": condo_id  # None para super_admin
    }
    token = create_access_token(token_payload)

    # Super admin → tela de seleção de condomínio
    # Condo admin → direto ao dashboard
    if is_super_admin({"role": role}) or not condo_id:
        redirect_url = "/admin/condos"
    else:
        redirect_url = "/admin/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, token)
    return response

@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("syndra_admin_session")
    return response

# ════════════════════════════════════════════════════════════
# SELEÇÃO DE CONDOMÍNIO
# ════════════════════════════════════════════════════════════

@app.get("/admin/condos", response_class=HTMLResponse)
async def admin_condos_list(request: Request, user_session: dict = Depends(authenticate_admin), msg: str = None):
    """Lista todos os condomínios (super admin) ou redireciona para o dashboard (condo admin)."""
    if not is_super_admin(user_session):
        return RedirectResponse(url="/admin/dashboard", status_code=302)

    try:
        res = supabase.table("condos").select("*").order("created_at", desc=True).execute()
        condos = res.data or []
    except Exception as e:
        logger.error(f"Erro ao buscar condomínios: {e}")
        condos = []

    return templates.TemplateResponse(request=request, name="select_condo.html",
        context={"user": user_session, "condos": condos, "message": msg})

@app.post("/admin/select-condo")
async def admin_select_condo(request: Request, condo_id: str = Form(...), user_session: dict = Depends(authenticate_admin)):
    """Troca o condo_id ativo na sessão JWT."""
    # Verificar se condomínio existe
    try:
        res = supabase.table("condos").select("id, name").eq("id", condo_id).maybe_single().execute()
        if not res.data:
            raise HTTPException(404, "Condomínio não encontrado")
    except Exception:
        raise HTTPException(404, "Condomínio não encontrado")

    # Re-emitir JWT com novo condo_id
    new_payload = {**user_session, "condo_id": condo_id}
    new_payload.pop("exp", None)
    token = create_access_token(new_payload)

    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    _set_session_cookie(response, token)
    return response

# ════════════════════════════════════════════════════════════
# CRUD DE CONDOMÍNIOS
# ════════════════════════════════════════════════════════════

@app.get("/admin/condos/new", response_class=HTMLResponse)
async def new_condo_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    if not is_super_admin(user_session):
        raise HTTPException(403, "Acesso negado")
    return templates.TemplateResponse(request=request, name="condo_form.html",
        context={"user": user_session, "condo": {}, "editing": False})

@app.post("/admin/condos/new")
async def create_condo(request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), evolution_instance: str = Form(...),
    cnpj: str = Form(""), address: str = Form(""),
    sindico_name: str = Form(""), sindico_phone: str = Form(""),
    active: str = Form(None)):

    if not is_super_admin(user_session):
        raise HTTPException(403, "Acesso negado")

    try:
        new_id = str(uuid.uuid4())
        supabase.table("condos").insert({
            "id": new_id, "name": name, "cnpj": cnpj,
            "address": address, "evolution_instance": evolution_instance,
            "sindico_name": sindico_name, "sindico_phone": sindico_phone,
            "active": active == "on"
        }).execute()

        # Pré-popular settings básicos do novo condomínio
        for key, value in [
            ("CONDO_NAME", name), ("CONDO_CNPJ", cnpj),
            ("CONDO_ADDRESS", address), ("SINDICO_NAME", sindico_name),
            ("SINDICO_PHONE", sindico_phone), ("AGENT_NAME", "Syndra"),
            ("LLM_PROVIDER", "OpenRouter"), ("LLM_MODEL", "stepfun/step-3.5-flash:free")
        ]:
            if value:
                set_setting(new_id, key, value)

        logger.info(f"✅ Novo condomínio criado: {name} ({new_id})")
        return RedirectResponse(url=f"/admin/condos?msg=Condomínio '{name}' criado com sucesso!", status_code=302)
    except Exception as e:
        logger.error(f"Erro ao criar condomínio: {e}")
        return templates.TemplateResponse(request=request, name="condo_form.html",
            context={"user": user_session, "condo": {"name": name}, "editing": False, "error": str(e)})

@app.get("/admin/condos/{condo_id}/edit", response_class=HTMLResponse)
async def edit_condo_page(condo_id: str, request: Request, user_session: dict = Depends(authenticate_admin)):
    if not is_super_admin(user_session):
        raise HTTPException(403, "Acesso negado")
    res = supabase.table("condos").select("*").eq("id", condo_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(404, "Condomínio não encontrado")
    return templates.TemplateResponse(request=request, name="condo_form.html",
        context={"user": user_session, "condo": res.data, "editing": True})

@app.post("/admin/condos/{condo_id}/edit")
async def update_condo(condo_id: str, request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), evolution_instance: str = Form(...),
    cnpj: str = Form(""), address: str = Form(""),
    sindico_name: str = Form(""), sindico_phone: str = Form(""),
    active: str = Form(None)):

    if not is_super_admin(user_session):
        raise HTTPException(403, "Acesso negado")

    supabase.table("condos").update({
        "name": name, "cnpj": cnpj, "address": address,
        "evolution_instance": evolution_instance,
        "sindico_name": sindico_name, "sindico_phone": sindico_phone,
        "active": active == "on"
    }).eq("id", condo_id).execute()

    # Sincronizar settings
    for key, value in [("CONDO_NAME", name), ("CONDO_CNPJ", cnpj),
                       ("CONDO_ADDRESS", address), ("SINDICO_NAME", sindico_name),
                       ("SINDICO_PHONE", sindico_phone)]:
        set_setting(condo_id, key, value)
    invalidate_cache(condo_id)

    return RedirectResponse(url="/admin/condos?msg=Condomínio atualizado com sucesso!", status_code=302)

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")

    # Super admin sem condomínio selecionado → redireciona para seleção
    if not condo_id:
        return RedirectResponse(url="/admin/condos", status_code=302)

    try:
        residents = supabase.table("residents").select("id", count="exact").eq("condo_id", condo_id).execute()
        messages  = supabase.table("conversations").select("id", count="exact").eq("condo_id", condo_id).execute()
        mnt_open  = supabase.table("maintenance_requests").select("id", count="exact").eq("condo_id", condo_id).eq("status", "aberto").execute()
        res_pend  = supabase.table("space_bookings").select("id", count="exact").eq("condo_id", condo_id).eq("status", "pendente").execute()
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

    # Buscar lista de condomínios para o dropdown (super admin)
    all_condos = []
    if is_super_admin(user_session):
        try:
            res = supabase.table("condos").select("id, name").order("name").execute()
            all_condos = res.data or []
        except Exception:
            pass

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "stats": stats,
        "recent_residents": recent_res.data if hasattr(recent_res, "data") else [],
        "recent_maintenance": recent_mnt.data if hasattr(recent_mnt, "data") else [],
        "user": user_session,
        "all_condos": all_condos
    })

# ════════════════════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════════════════════

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")
    if not condo_id:
        return RedirectResponse(url="/admin/condos", status_code=302)
    if user_session.get("role") not in ("admin", "super_admin", "condo_admin"):
        raise HTTPException(403, "Acesso negado")

    keys_to_load = [
        "AGENT_NAME", "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY",
        "CONDO_NAME", "CONDO_CNPJ", "CONDO_ADDRESS",
        "SINDICO_NAME", "SINDICO_PHONE", "ZELADOR_NAME", "ZELADOR_PHONE",
        "PORTARIA_PHONE", "ADMINISTRADORA_PHONE",
        "SALAO_PRECO_NOITE", "SALAO_PRECO_DIA", "CHURRASQUEIRA_PRECO",
        "PIX_TIPO", "PIX_CHAVE", "PIX_NOME"
    ]
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "user": user_session,
        "settings": {k: get_setting(condo_id, k) for k in keys_to_load}
    })

@app.post("/admin/settings", response_class=HTMLResponse)
async def admin_settings_save(request: Request, user_session: dict = Depends(authenticate_admin)):
    condo_id = user_session.get("condo_id")
    if not condo_id:
        return RedirectResponse(url="/admin/condos", status_code=302)

    form_data = await request.form()
    for key, value in form_data.items():
        set_setting(condo_id, key, str(value))
    invalidate_cache(condo_id)

    return templates.TemplateResponse(request=request, name="settings.html", context={
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "user": user_session,
        "settings": {k: get_setting(condo_id, k) for k in form_data.keys()},
        "message": "Configurações atualizadas com sucesso!"
    })

# ════════════════════════════════════════════════════════════
# BROADCAST & STATS
# ════════════════════════════════════════════════════════════

@app.post("/admin/broadcast")
async def send_broadcast(request: Request, background_tasks: BackgroundTasks, x_admin_key: str = Header(None)):
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")
    body = await request.json()
    title, content, condo_id = body.get("title"), body.get("content"), body.get("condo_id")
    audience = body.get("audience", "todos")
    if not all([title, content, condo_id]):
        raise HTTPException(400, "title, content e condo_id são obrigatórios")
    background_tasks.add_task(_do_broadcast, condo_id, title, content, audience)
    return {"status": "queued", "title": title, "audience": audience}

async def _do_broadcast(condo_id: str, title: str, content: str, audience: str):
    from src.whatsapp.sender import send_message
    try:
        query = supabase.table("residents").select("whatsapp_phone").eq("condo_id", condo_id).eq("active", True)
        if audience == "proprietarios": query = query.eq("is_owner", True)
        elif audience == "inquilinos":  query = query.eq("is_owner", False)
        residents = query.execute()
        message = f"📢 *{title}*\n\n{content}"
        for r in (residents.data or []):
            phone = r.get("whatsapp_phone")
            if phone:
                try: await send_message(phone, message, condo_id=condo_id)
                except Exception as e: logger.error(f"❌ Broadcast falhou para {phone}: {e}")
    except Exception as e:
        logger.error(f"❌ Erro no broadcast: {e}", exc_info=True)

@app.get("/admin/stats")
async def get_stats(x_admin_key: str = Header(None)):
    if x_admin_key != os.getenv("ADMIN_KEY"):
        raise HTTPException(401, "Chave de admin inválida")
    return {"status": "ok", "message": "Estatísticas em desenvolvimento"}

# ─── Debug (apenas DEBUG=True + autenticado) ───────────────
@app.get("/admin/debug-info")
async def debug_info(user_session: dict = Depends(authenticate_admin)):
    if not settings.DEBUG:
        raise HTTPException(403, "Disponível apenas em modo DEBUG.")
    return {
        "cwd": os.getcwd(),
        "env_vars": [k for k in os.environ.keys() if not any(s in k for s in ["KEY", "TOKEN", "PASS", "SECRET"])]
    }
