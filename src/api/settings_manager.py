import os
from src.supabase.client import supabase

# Cache em memória simples particionado por condo_id
# Estrutura: { condo_id: { key: value } }
_settings_cache = {}

def get_setting(condo_id: str, key: str, default: str = "") -> str:
    """
    Tenta buscar a configuração no Supabase filtrando por condo_id.
    Se não achar ou houver erro, usa o cache local ou o .env.
    """
    global _settings_cache
    
    if condo_id not in _settings_cache:
        _settings_cache[condo_id] = {}

    try:
        res = supabase.table("system_settings") \
            .select("value") \
            .eq("condo_id", condo_id) \
            .eq("key", key) \
            .maybe_single() \
            .execute()
        
        if res and res.data and "value" in res.data:
            val = res.data["value"]
            _settings_cache[condo_id][key] = val
            return val
            
    except Exception as e:
        # Silencioso, falhar graciosamente para o fallback
        pass
        
    # Fallback 1: Memória Cache (útil se o banco cair de repente)
    if key in _settings_cache[condo_id]:
        return _settings_cache[condo_id][key]
        
    # Fallback 2: Variável de Ambiente Original (.env)
    return os.getenv(key, default)

def set_setting(condo_id: str, key: str, value: str):
    """Atualiza ou cria uma configuração no banco para um condomínio específico."""
    global _settings_cache
    
    if condo_id not in _settings_cache:
        _settings_cache[condo_id] = {}

    try:
        # Upsert: Insere ou Atualiza caso a chave já exista para este condo_id
        supabase.table("system_settings").upsert({
            "condo_id": condo_id,
            "key": key,
            "value": value
        }).execute()
        
        _settings_cache[condo_id][key] = value
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração {key} para condo {condo_id}: {e}")
        return False
