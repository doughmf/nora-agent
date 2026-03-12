import os
from src.supabase.client import supabase

# Cache em memória simples para não bombardear o banco a cada mensagem
_settings_cache = {}

def get_setting(key: str, default: str = "") -> str:
    """
    Tenta buscar a configuração no Supabase.
    Se não achar ou houver erro, usa o cache local ou o .env.
    """
    global _settings_cache
    
    try:
        res = supabase.table("system_settings").select("value").eq("key", key).maybe_single().execute()
        
        if res and res.data and "value" in res.data:
            val = res.data["value"]
            _settings_cache[key] = val
            return val
            
    except Exception as e:
        # Silencioso, falhar graciosamente para o fallback
        pass
        
    # Fallback 1: Memória Cache (útil se o banco cair de repente)
    if key in _settings_cache:
        return _settings_cache[key]
        
    # Fallback 2: Variável de Ambiente Original (.env)
    return os.getenv(key, default)

def set_setting(key: str, value: str):
    """Atualiza ou cria uma configuração no banco e atualiza o cache."""
    global _settings_cache
    
    try:
        # Upsert: Insere ou Atualiza caso a chave já exista
        supabase.table("system_settings").upsert({
            "key": key,
            "value": value
        }).execute()
        
        _settings_cache[key] = value
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração {key}: {e}")
        return False
