"""
Syndra Agent — API Principal (SaaS Multi-tenant)

Perfis: super_admin > admin > sindico > colaborador
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, Depends, status, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from contextlib import asynccontextmanager
import logging, os, secrets, jwt, bcrypt, hashlib, uuid, json, io, csv
from datetime import datetime, timedelta
from src.api.settings_manager import get_setting, set_setting, invalidate_cache
from src.api.permissions import (
    has_permission, require_permission,
    can_manage_user, roles_available_for,
    ROLE_LABELS, PERMISSIONS
)
from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("syndra")

# ─── JWT Secret ────────────────────────────────────────────
JWT_SECRET = settings.SECRET_KEY
if not JWT_SECRET:
    logger.warning("⚠️  AVISO CRÍTICO: SECRET_KEY não definida — Não recomendado para produção!")
    logger.warning("    Defina SECRET_KEY=<valor-seguro> no arquivo .env")
    seed = f"{settings.SUPABASE_URL}{settings.SUPABASE_SERVICE_KEY}"
    JWT_SECRET = hashlib.sha256(seed.encode()).hexdigest()
    logger.warning(f"    Usando JWT derivado (inseguro). Hash: {JWT_SECRET[:20]}...")

ALLOWED_ORIGINS = [f"https://{settings.DOMAIN}"] if settings.DOMAIN else ["*"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🏠 Syndra Agent iniciando...")
    yield
    logger.info("🔴 Syndra Agent encerrando...")

app = FastAPI(title="Syndra Agent API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Carregar Supabase client com validação de erro
try:
    from src.supabase.client import supabase
    logger.info("✅ Supabase client carregado com sucesso")
except Exception as e:
    logger.error(f"❌ Erro crítico ao carregar Supabase client: {e}")
    logger.error("   Verifique SUPABASE_URL, SUPABASE_SERVICE_KEY e SUPABASE_ANON_KEY no .env")
    raise RuntimeError("Falha ao inicializar Supabase client") from e

# ─── JWT Helpers ───────────────────────────────────────────
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

def _set_session_cookie(response, token: str):
    response.set_cookie(key="syndra_admin_session", value=token,
        httponly=True, secure=not settings.DEBUG, samesite="lax", max_age=3600 * 24)

def _get_all_condos() -> list:
    try:
        return supabase.table("condos").select("id, name").order("name").execute().data or []
    except Exception:
        return []

# ─── Health ────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "Syndra Agent", "version": "2.0.0", "timestamp": datetime.now().isoformat()}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erro em {request.url}: {exc}", exc_info=True)
    if settings.DEBUG:
        import traceback
        return HTMLResponse(f"<h1>Error 500</h1><pre>{traceback.format_exc()}</pre>", status_code=500)
    return HTMLResponse("<h1>Erro interno do servidor</h1>", status_code=500)

# ─── Webhook ───────────────────────────────────────────────
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

    role = user_data.get("role", "colaborador")
    condo_id = user_data.get("condo_id")

    token_payload = {"sub": user_data["username"], "name": user_data["name"], "role": role, "condo_id": condo_id}
    token = create_access_token(token_payload)

    # Super admin sem condo → tela de condomínios; demais → dashboard
    redirect_url = "/admin/condos" if (role == "super_admin" and not condo_id) else "/admin/dashboard"
    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, token)
    return response

@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("syndra_admin_session")
    return response

# ════════════════════════════════════════════════════════════
# CONDOMÍNIOS
# ════════════════════════════════════════════════════════════

@app.get("/admin/condos", response_class=HTMLResponse)
async def admin_condos_list(request: Request, user_session: dict = Depends(authenticate_admin), msg: str = None):
    require_permission(user_session, "manage_condos")
    try:
        condos = supabase.table("condos").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        logger.error(f"Erro ao buscar condomínios: {e}")
        condos = []
    return templates.TemplateResponse(request=request, name="select_condo.html",
        context={"user": user_session, "condos": condos, "message": msg})

@app.post("/admin/select-condo")
async def admin_select_condo(request: Request, condo_id: str = Form(...), user_session: dict = Depends(authenticate_admin)):
    try:
        res = supabase.table("condos").select("id").eq("id", condo_id).maybe_single().execute()
        if not res.data:
            raise HTTPException(404, "Condomínio não encontrado")
    except Exception:
        raise HTTPException(404, "Condomínio não encontrado")
    new_payload = {**user_session, "condo_id": condo_id}
    new_payload.pop("exp", None)
    token = create_access_token(new_payload)
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    _set_session_cookie(response, token)
    return response

@app.get("/admin/condos/new", response_class=HTMLResponse)
async def new_condo_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "manage_condos")
    return templates.TemplateResponse(request=request, name="condo_form.html",
        context={"user": user_session, "condo": {}, "editing": False})

@app.post("/admin/condos/new")
async def create_condo(request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), evolution_instance: str = Form(...),
    cnpj: str = Form(""), address: str = Form(""),
    sindico_name: str = Form(""), sindico_phone: str = Form(""), active: str = Form(None)):
    require_permission(user_session, "manage_condos")
    try:
        new_id = str(uuid.uuid4())
        supabase.table("condos").insert({"id": new_id, "name": name, "cnpj": cnpj,
            "address": address, "evolution_instance": evolution_instance,
            "sindico_name": sindico_name, "sindico_phone": sindico_phone, "active": active == "on"}).execute()
        for key, value in [("CONDO_NAME", name), ("CONDO_CNPJ", cnpj), ("CONDO_ADDRESS", address),
                           ("SINDICO_NAME", sindico_name), ("SINDICO_PHONE", sindico_phone),
                           ("AGENT_NAME", "Syndra"), ("LLM_PROVIDER", "OpenRouter"),
                           ("LLM_MODEL", "stepfun/step-3.5-flash:free")]:
            if value: set_setting(new_id, key, value)
        return RedirectResponse(url=f"/admin/condos?msg=Condomínio '{name}' criado com sucesso!", status_code=302)
    except Exception as e:
        return templates.TemplateResponse(request=request, name="condo_form.html",
            context={"user": user_session, "condo": {"name": name}, "editing": False, "error": str(e)})

@app.get("/admin/condos/{condo_id}/edit", response_class=HTMLResponse)
async def edit_condo_page(condo_id: str, request: Request, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "manage_condos")
    res = supabase.table("condos").select("*").eq("id", condo_id).maybe_single().execute()
    if not res.data: raise HTTPException(404, "Condomínio não encontrado")
    return templates.TemplateResponse(request=request, name="condo_form.html",
        context={"user": user_session, "condo": res.data, "editing": True})

@app.post("/admin/condos/{condo_id}/edit")
async def update_condo(condo_id: str, request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), evolution_instance: str = Form(...),
    cnpj: str = Form(""), address: str = Form(""),
    sindico_name: str = Form(""), sindico_phone: str = Form(""), active: str = Form(None)):
    require_permission(user_session, "manage_condos")
    supabase.table("condos").update({"name": name, "cnpj": cnpj, "address": address,
        "evolution_instance": evolution_instance, "sindico_name": sindico_name,
        "sindico_phone": sindico_phone, "active": active == "on"}).eq("id", condo_id).execute()
    for key, value in [("CONDO_NAME", name), ("CONDO_CNPJ", cnpj), ("CONDO_ADDRESS", address),
                       ("SINDICO_NAME", sindico_name), ("SINDICO_PHONE", sindico_phone)]:
        set_setting(condo_id, key, value)
    invalidate_cache(condo_id)
    return RedirectResponse(url="/admin/condos?msg=Condomínio atualizado com sucesso!", status_code=302)

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "view_dashboard")
    condo_id = user_session.get("condo_id")
    if not condo_id:
        return RedirectResponse(url="/admin/condos" if has_permission(user_session, "manage_condos") else "/admin/login", status_code=302)

    try:
        residents = supabase.table("residents").select("id", count="exact").eq("condo_id", condo_id).execute()
        messages  = supabase.table("conversations").select("id", count="exact").eq("condo_id", condo_id).execute()
        mnt_open  = supabase.table("maintenance_requests").select("id", count="exact").eq("condo_id", condo_id).eq("status", "aberto").execute()
        res_pend  = supabase.table("space_bookings").select("id", count="exact").eq("condo_id", condo_id).eq("status", "pendente").execute()
        recent_res = supabase.table("residents").select("*").eq("condo_id", condo_id).order("created_at", desc=True).limit(5).execute()
        recent_mnt = supabase.table("maintenance_requests").select("*").eq("condo_id", condo_id).order("created_at", desc=True).limit(5).execute()
        stats = {"residents_count": residents.count or 0, "messages_count": messages.count or 0,
                 "open_maintenance": mnt_open.count or 0, "pending_bookings": res_pend.count or 0}
    except Exception as e:
        logger.error(f"Erro dashboard: {e}")
        stats = {"residents_count": 0, "messages_count": 0, "open_maintenance": 0, "pending_bookings": 0}
        recent_res = type("obj", (object,), {"data": []})()
        recent_mnt = type("obj", (object,), {"data": []})()

    all_condos = []
    if has_permission(user_session, "manage_condos"):
        try:
            all_condos = supabase.table("condos").select("id, name").order("name").execute().data or []
        except Exception:
            pass

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "stats": stats,
        "recent_residents": recent_res.data if hasattr(recent_res, "data") else [],
        "recent_maintenance": recent_mnt.data if hasattr(recent_mnt, "data") else [],
        "user": user_session,
        "all_condos": all_condos,
        "perms": PERMISSIONS.get(user_session.get("role", "colaborador"), set()),
    })

# ════════════════════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════════════════════

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "manage_settings")
    condo_id = user_session.get("condo_id")
    if not condo_id:
        return RedirectResponse(url="/admin/condos", status_code=302)
    keys_to_load = ["AGENT_NAME", "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY",
        "CONDO_NAME", "CONDO_CNPJ", "CONDO_ADDRESS", "SINDICO_NAME", "SINDICO_PHONE",
        "ZELADOR_NAME", "ZELADOR_PHONE", "PORTARIA_PHONE", "ADMINISTRADORA_PHONE",
        "SALAO_PRECO_NOITE", "SALAO_PRECO_DIA", "CHURRASQUEIRA_PRECO",
        "PIX_TIPO", "PIX_CHAVE", "PIX_NOME"]
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "user": user_session,
        "settings": {k: get_setting(condo_id, k) for k in keys_to_load}
    })

@app.post("/admin/settings", response_class=HTMLResponse)
async def admin_settings_save(request: Request, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "manage_settings")
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
# USUÁRIOS
# ════════════════════════════════════════════════════════════

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_list(request: Request, user_session: dict = Depends(authenticate_admin),
                            success: str = None, error: str = None):
    require_permission(user_session, "manage_users")
    try:
        res = supabase.table("system_users").select("id, name, username, role, condo_id, created_at").order("created_at", desc=True).execute()
        users = res.data or []
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {e}")
        users = []

    condos = _get_all_condos()
    condo_map = {c["id"]: c["name"] for c in condos}
    for u in users:
        u["condo_name"] = condo_map.get(u.get("condo_id"), "")
        u["role_label"] = ROLE_LABELS.get(u.get("role"), u.get("role", ""))

    return templates.TemplateResponse(request=request, name="users.html", context={
        "user": user_session,
        "users": users,
        "condos": condos,
        "assignable_roles": roles_available_for(user_session),
        "current_user_username": user_session.get("sub"),
        "success": success,
        "error": error,
    })

@app.post("/admin/users/new")
async def admin_user_create(request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), username: str = Form(...), password: str = Form(...),
    role: str = Form(...), condo_id: str = Form("")):

    require_permission(user_session, "manage_users")

    if not can_manage_user(user_session, role):
        return RedirectResponse(url=f"/admin/users?error=Você não pode criar usuários com perfil '{ROLE_LABELS.get(role, role)}'.", status_code=302)

    try:
        existing = supabase.table("system_users").select("id").eq("username", username).execute()
        if existing.data:
            return RedirectResponse(url=f"/admin/users?error=Usuário '{username}' já existe.", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=302)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Síndico e colaborador ficam vinculados ao condo do criador se não especificado
    resolved_condo = condo_id if condo_id else user_session.get("condo_id")

    try:
        supabase.table("system_users").insert({
            "name": name, "username": username, "password_hash": password_hash,
            "role": role, "condo_id": resolved_condo if resolved_condo else None
        }).execute()
        logger.info(f"✅ Usuário criado: {username} (role: {role})")
        return RedirectResponse(url=f"/admin/users?success=Usuário '{name}' criado com sucesso!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=302)

@app.post("/admin/users/{user_id}/edit")
async def admin_user_edit(user_id: str, request: Request, user_session: dict = Depends(authenticate_admin),
    name: str = Form(...), username: str = Form(...), role: str = Form(...), condo_id: str = Form("")):

    require_permission(user_session, "manage_users")
    if not can_manage_user(user_session, role):
        return RedirectResponse(url=f"/admin/users?error=Você não pode atribuir o perfil '{ROLE_LABELS.get(role, role)}'.", status_code=302)

    try:
        supabase.table("system_users").update({
            "name": name, "username": username, "role": role,
            "condo_id": condo_id if condo_id else None
        }).eq("id", user_id).execute()
        return RedirectResponse(url=f"/admin/users?success=Usuário '{name}' atualizado com sucesso!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=302)

@app.post("/admin/users/{user_id}/reset-password")
async def admin_user_reset_password(user_id: str, user_session: dict = Depends(authenticate_admin),
    new_password: str = Form(...)):

    require_permission(user_session, "manage_users")
    if len(new_password) < 8:
        return RedirectResponse(url="/admin/users?error=Senha deve ter no mínimo 8 caracteres.", status_code=302)

    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        supabase.table("system_users").update({"password_hash": password_hash}).eq("id", user_id).execute()
        return RedirectResponse(url="/admin/users?success=Senha redefinida com sucesso!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=302)

@app.post("/admin/users/{user_id}/delete")
async def admin_user_delete(user_id: str, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "manage_users")
    try:
        res = supabase.table("system_users").select("username, role").eq("id", user_id).maybe_single().execute()
        if res.data:
            if res.data["username"] == user_session.get("sub"):
                return RedirectResponse(url="/admin/users?error=Você não pode excluir seu próprio usuário.", status_code=302)
            if not can_manage_user(user_session, res.data["role"]):
                return RedirectResponse(url=f"/admin/users?error=Você não pode excluir um usuário com perfil '{ROLE_LABELS.get(res.data['role'], '')}'.", status_code=302)
        supabase.table("system_users").delete().eq("id", user_id).execute()
        return RedirectResponse(url="/admin/users?success=Usuário excluído com sucesso!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/users?error={str(e)}", status_code=302)

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
    return {"status": "ok"}

@app.get("/admin/debug-info")
async def debug_info(user_session: dict = Depends(authenticate_admin)):
    if not settings.DEBUG:
        raise HTTPException(403, "Disponível apenas em modo DEBUG.")
    return {"cwd": os.getcwd(),
            "env_vars": [k for k in os.environ.keys() if not any(s in k for s in ["KEY", "TOKEN", "PASS", "SECRET"])]}

# ════════════════════════════════════════════════════════════
# MORADORES
# ════════════════════════════════════════════════════════════
import csv, io, json
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

PAGE_SIZE = 20

@app.get("/admin/residents", response_class=HTMLResponse)
async def admin_residents_list(
    request: Request,
    user_session: dict = Depends(authenticate_admin),
    q: str = "", block: str = "", tipo: str = "", status: str = "",
    page: int = 1, success: str = None, error: str = None
):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")
    if not condo_id:
        return RedirectResponse(url="/admin/condos", status_code=302)

    try:
        query = supabase.table("residents").select("*").eq("condo_id", condo_id)

        if q:
            query = query.or_(f"name.ilike.%{q}%,whatsapp_phone.ilike.%{q}%,apartment.ilike.%{q}%,email.ilike.%{q}%")
        if block:
            query = query.eq("block", block)
        if tipo == "owner":
            query = query.eq("is_owner", True)
        elif tipo == "tenant":
            query = query.eq("is_owner", False)
        if status == "active":
            query = query.eq("active", True)
        elif status == "inactive":
            query = query.eq("active", False)
        elif status == "onboarding":
            query = query.eq("active", True)  # filtro adicional via Python abaixo

        all_res = query.order("block").order("apartment").execute()
        all_residents = all_res.data or []

        # Filtro onboarding (campo JSONB — feito em Python)
        if status == "onboarding":
            all_residents = [r for r in all_residents if not (r.get("profile") or {}).get("onboarding_complete")]

        total = len(all_residents)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        residents = all_residents[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

        # Blocos disponíveis para o filtro
        blocks_res = supabase.table("residents").select("block").eq("condo_id", condo_id).execute()
        blocks = sorted({r["block"] for r in (blocks_res.data or []) if r.get("block")})

    except Exception as e:
        logger.error(f"Erro ao listar moradores: {e}")
        residents, total, total_pages, blocks = [], 0, 1, []

    return templates.TemplateResponse(request=request, name="residents.html", context={
        "user": user_session,
        "condo_name": get_setting(condo_id, "CONDO_NAME", "Condomínio"),
        "residents": residents,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "blocks": blocks,
        "filters": {"q": q, "block": block, "tipo": tipo, "status": status},
        "success": success,
        "error": error,
    })


@app.post("/admin/residents/new")
async def admin_resident_create(
    request: Request,
    user_session: dict = Depends(authenticate_admin),
    name: str = Form(""), whatsapp_phone: str = Form(...),
    cpf: str = Form(""), email: str = Form(""),
    is_owner: str = Form("true"), apartment: str = Form(...),
    block: str = Form(""), vehicles: str = Form(""),
    dependents: str = Form("[]")
):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")

    # Formatar telefone
    phone_clean = whatsapp_phone.replace("+", "").replace(" ", "").replace("-", "")

    # Verificar duplicata
    existing = supabase.table("residents").select("id").eq("condo_id", condo_id).eq("whatsapp_phone", phone_clean).execute()
    if existing.data:
        return RedirectResponse(url=f"/admin/residents?error=Telefone {phone_clean} já cadastrado neste condomínio.", status_code=302)

    # Processar veículos e dependentes
    vehicles_list = [v.strip().upper() for v in vehicles.split(",") if v.strip()] if vehicles else []
    try:
        dependents_list = json.loads(dependents)
    except Exception:
        dependents_list = []

    try:
        supabase.table("residents").insert({
            "condo_id": condo_id,
            "name": name or None,
            "whatsapp_phone": phone_clean,
            "cpf": cpf or None,
            "email": email or None,
            "is_owner": is_owner == "true",
            "apartment": apartment,
            "block": block or None,
            "vehicles": vehicles_list,
            "dependents": dependents_list,
            "active": True,
            "profile": {"onboarding_complete": bool(name)}
        }).execute()
        return RedirectResponse(url=f"/admin/residents?success=Morador cadastrado com sucesso!", status_code=302)
    except Exception as e:
        logger.error(f"Erro ao criar morador: {e}")
        return RedirectResponse(url=f"/admin/residents?error={str(e)}", status_code=302)


@app.post("/admin/residents/{resident_id}/edit")
async def admin_resident_edit(
    resident_id: str,
    user_session: dict = Depends(authenticate_admin),
    name: str = Form(""), whatsapp_phone: str = Form(...),
    cpf: str = Form(""), email: str = Form(""),
    is_owner: str = Form("true"), apartment: str = Form(...),
    block: str = Form(""), vehicles: str = Form(""),
    dependents: str = Form("[]")
):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")

    phone_clean = whatsapp_phone.replace("+", "").replace(" ", "").replace("-", "")
    vehicles_list = [v.strip().upper() for v in vehicles.split(",") if v.strip()] if vehicles else []
    try:
        dependents_list = json.loads(dependents)
    except Exception:
        dependents_list = []

    try:
        supabase.table("residents").update({
            "name": name or None,
            "whatsapp_phone": phone_clean,
            "cpf": cpf or None,
            "email": email or None,
            "is_owner": is_owner == "true",
            "apartment": apartment,
            "block": block or None,
            "vehicles": vehicles_list,
            "dependents": dependents_list,
            "profile": {"onboarding_complete": bool(name)}
        }).eq("id", resident_id).eq("condo_id", condo_id).execute()
        return RedirectResponse(url="/admin/residents?success=Morador atualizado com sucesso!", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/residents?error={str(e)}", status_code=302)


@app.post("/admin/residents/{resident_id}/toggle-active")
async def admin_resident_toggle(resident_id: str, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")
    try:
        res = supabase.table("residents").select("active").eq("id", resident_id).eq("condo_id", condo_id).maybe_single().execute()
        if not res.data:
            return RedirectResponse(url="/admin/residents?error=Morador não encontrado.", status_code=302)
        new_status = not res.data.get("active", True)
        supabase.table("residents").update({"active": new_status}).eq("id", resident_id).execute()
        msg = "Acesso ao WhatsApp ativado." if new_status else "Acesso ao WhatsApp desativado."
        return RedirectResponse(url=f"/admin/residents?success={msg}", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/residents?error={str(e)}", status_code=302)


@app.post("/admin/residents/{resident_id}/delete")
async def admin_resident_delete(resident_id: str, user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")
    try:
        supabase.table("residents").delete().eq("id", resident_id).eq("condo_id", condo_id).execute()
        return RedirectResponse(url="/admin/residents?success=Morador excluído com sucesso.", status_code=302)
    except Exception as e:
        return RedirectResponse(url=f"/admin/residents?error={str(e)}", status_code=302)


# ─── Exportar CSV ──────────────────────────────────────────
@app.get("/admin/residents/export")
async def admin_residents_export(user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")
    res = supabase.table("residents").select("*").eq("condo_id", condo_id).order("block").order("apartment").execute()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "whatsapp_phone", "apartment", "block", "is_owner", "cpf", "email", "vehicles", "active"])
    for r in (res.data or []):
        writer.writerow([
            r.get("name", ""), r.get("whatsapp_phone", ""), r.get("apartment", ""),
            r.get("block", ""), r.get("is_owner", True), r.get("cpf", ""),
            r.get("email", ""), ",".join(r.get("vehicles") or []), r.get("active", True)
        ])

    output.seek(0)
    condo_name = get_setting(condo_id, "CONDO_NAME", "condo").replace(" ", "_")
    filename = f"moradores_{condo_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


# ─── Template CSV ──────────────────────────────────────────
@app.get("/admin/residents/csv-template")
async def residents_csv_template(user_session: dict = Depends(authenticate_admin)):
    require_permission(user_session, "view_residents")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "whatsapp_phone", "apartment", "block", "is_owner", "cpf", "email", "vehicles"])
    writer.writerow(["João da Silva", "5511999990001", "101", "A", "true", "000.000.000-00", "joao@email.com", "ABC-1234"])
    writer.writerow(["Maria Souza", "5511999990002", "202", "B", "false", "", "maria@email.com", ""])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=modelo_moradores.csv"})


# ─── Importar CSV ──────────────────────────────────────────
@app.post("/admin/residents/import")
async def admin_residents_import(
    request: Request,
    user_session: dict = Depends(authenticate_admin),
    file: UploadFile = File(...)
):
    require_permission(user_session, "view_residents")
    condo_id = user_session.get("condo_id")

    if not file.filename.endswith(".csv"):
        return RedirectResponse(url="/admin/residents?error=Arquivo deve ser .csv", status_code=302)

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig para suportar BOM do Excel
    except Exception:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    inserted, skipped, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):
        phone = row.get("whatsapp_phone", "").replace("+", "").replace(" ", "").replace("-", "").strip()
        apartment = row.get("apartment", "").strip()

        if not phone or not apartment:
            errors.append(f"Linha {i}: whatsapp_phone e apartment são obrigatórios")
            skipped += 1
            continue

        # Verificar duplicata
        existing = supabase.table("residents").select("id").eq("condo_id", condo_id).eq("whatsapp_phone", phone).execute()
        if existing.data:
            skipped += 1
            continue

        vehicles_raw = row.get("vehicles", "")
        vehicles_list = [v.strip().upper() for v in vehicles_raw.split(",") if v.strip()] if vehicles_raw else []
        name = row.get("name", "").strip()

        try:
            supabase.table("residents").insert({
                "condo_id": condo_id,
                "name": name or None,
                "whatsapp_phone": phone,
                "cpf": row.get("cpf", "").strip() or None,
                "email": row.get("email", "").strip() or None,
                "is_owner": str(row.get("is_owner", "true")).lower() in ("true", "1", "sim", "s"),
                "apartment": apartment,
                "block": row.get("block", "").strip() or None,
                "vehicles": vehicles_list,
                "dependents": [],
                "active": True,
                "profile": {"onboarding_complete": bool(name)}
            }).execute()
            inserted += 1
        except Exception as e:
            errors.append(f"Linha {i}: {str(e)}")
            skipped += 1

    msg = f"Importação concluída: {inserted} inseridos, {skipped} ignorados."
    if errors:
        msg += f" Erros: {'; '.join(errors[:3])}"
        return RedirectResponse(url=f"/admin/residents?error={msg}", status_code=302)
    return RedirectResponse(url=f"/admin/residents?success={msg}", status_code=302)
