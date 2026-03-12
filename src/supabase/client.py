# src/supabase/client.py
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Usa a SERVICE_ROLE KEY para bypassar a restrição RLS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def resolve_condo_by_instance(instance_name: str) -> str | None:
    """Busca o condo_id associado ao nome da instância do Evolution API."""
    res = supabase.table("condos").select("id").eq("evolution_instance", instance_name).maybe_single().execute()
    if res.data:
        return res.data["id"]
    return None

async def semantic_search(condo_id: str, query_embedding: list[float], threshold: float = 0.75) -> list[dict]:
    """Busca semântica isolada por condomínio."""
    result = supabase.rpc("search_knowledge", {
        "p_condo_id": condo_id,
        "query_embedding": query_embedding,
        "match_threshold": threshold,
        "match_count": 5
    }).execute()
    return result.data

async def get_resident(condo_id: str, phone: str) -> dict | None:
    """Busca residente dentro de um condomínio específico."""
    result = supabase.table("residents") \
        .select("*") \
        .eq("condo_id", condo_id) \
        .eq("whatsapp_phone", phone) \
        .maybe_single() \
        .execute()
    return result.data if result.data else None

async def save_message(condo_id: str, resident_id: str, role: str, content: str, session_id: str, phone: str):
    """Salva mensagem no histórico com isolamento."""
    supabase.table("conversations").insert({
        "condo_id": condo_id,
        "resident_id": resident_id,
        "whatsapp_phone": phone,
        "session_id": session_id,
        "role": role,
        "content": content
    }).execute()

async def get_conversation_history(condo_id: str, phone: str, limit: int = 10) -> list[dict]:
    """Recupera histórico isolado por condomínio."""
    result = supabase.table("conversations") \
        .select("role, content, created_at") \
        .eq("condo_id", condo_id) \
        .eq("whatsapp_phone", phone) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    return list(reversed(result.data or []))

async def update_resident_profile(condo_id: str, phone: str, name: str, block: str, apartment: str, is_owner: bool) -> dict:
    """Atualiza o perfil do morador no escopo do condomínio."""
    result = supabase.table("residents") \
        .update({
            "name": name,
            "block": block,
            "apartment": apartment,
            "is_owner": is_owner,
            "profile": {"onboarding_complete": True}
        }) \
        .eq("condo_id", condo_id) \
        .eq("whatsapp_phone", phone) \
        .execute()
    return result.data[0] if result.data else {"erro": "Não encontrado."}
