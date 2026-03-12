# src/supabase/client.py
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
import numpy as np

# Usa a SERVICE_ROLE KEY para bypassar a restrição RLS de inserção (Row-Level Security)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def semantic_search(query_embedding: list[float], threshold: float = 0.75) -> list[dict]:
    """Busca semântica na base de conhecimento."""
    result = supabase.rpc("search_knowledge", {
        "query_embedding": query_embedding,
        "match_threshold": threshold,
        "match_count": 5
    }).execute()
    return result.data

async def get_resident(phone: str) -> dict | None:
    """Retorna o residente existente ou None se não cadastrado."""
    result = supabase.table("residents") \
        .select("*") \
        .eq("whatsapp_phone", phone) \
        .maybe_single() \
        .execute()
    
    if result is not None and result.data:
        return result.data
    
    return None

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

async def update_resident_profile(phone: str, name: str, block: str, apartment: str, is_owner: bool) -> dict:
    """Atualiza o perfil do morador (Onboarding)."""
    result = supabase.table("residents") \
        .update({
            "name": name,
            "block": block,
            "apartment": apartment,
            "is_owner": is_owner,
            "profile": {"onboarding_complete": True}
        }) \
        .eq("whatsapp_phone", phone) \
        .execute()
    
    if result.data:
        return result.data[0]
    return {"erro": "Residente não encontrado."}
