"""
Settings Manager — Multi-tenant com cache em lote por condo_id.

Correções aplicadas:
- Cache carregado em lote (uma query por condo_id) em vez de key-a-key
- Função invalidate_cache para forçar reload após deploys
- Evita N queries por mensagem recebida
"""
import os
import logging
from src.supabase.client import supabase

logger = logging.getLogger("syndra.settings")

# Cache em memória particionado por condo_id
# Estrutura: { condo_id: { key: value } }
_settings_cache: dict[str, dict] = {}

# Controle de quais condo_ids já tiveram o cache carregado do banco
_cache_loaded: set[str] = set()


def _load_all_settings(condo_id: str):
    """Carrega TODAS as configurações de um condomínio de uma vez só (1 query)."""
    try:
        res = supabase.table("system_settings") \
            .select("key, value") \
            .eq("condo_id", condo_id) \
            .execute()

        if condo_id not in _settings_cache:
            _settings_cache[condo_id] = {}

        for row in (res.data or []):
            _settings_cache[condo_id][row["key"]] = row["value"]

        _cache_loaded.add(condo_id)
        logger.debug(f"⚙️  Settings carregados para condo '{condo_id}': {len(res.data or [])} chaves")

    except Exception as e:
        logger.warning(f"⚠️  Falha ao carregar settings do condo '{condo_id}': {e}")
        # Marca como carregado p/ não tentar em loop em caso de falha persistente
        _cache_loaded.add(condo_id)


def get_setting(condo_id: str, key: str, default: str = "") -> str:
    """
    Retorna a configuração pelo key para o condomínio.
    Na primeira chamada por condo_id, carrega tudo em lote do banco (1 query).
    Fallback para variável de ambiente se não encontrado.
    """
    # Carrega em lote na primeira vez (apenas 1 query por condo_id por sessão)
    if condo_id not in _cache_loaded:
        _load_all_settings(condo_id)

    # Buscar no cache em memória
    value = _settings_cache.get(condo_id, {}).get(key)
    if value is not None:
        return value

    # Fallback: variável de ambiente
    return os.getenv(key, default)


def set_setting(condo_id: str, key: str, value: str) -> bool:
    """Atualiza ou cria uma configuração no banco e sincroniza o cache local."""
    try:
        supabase.table("system_settings").upsert({
            "condo_id": condo_id,
            "key": key,
            "value": value
        }).execute()

        # Atualizar cache local imediatamente
        if condo_id not in _settings_cache:
            _settings_cache[condo_id] = {}
        _settings_cache[condo_id][key] = value

        return True
    except Exception as e:
        logger.error(f"❌ Erro ao salvar setting '{key}' para condo '{condo_id}': {e}")
        return False


def invalidate_cache(condo_id: str):
    """Força recarga do cache na próxima chamada (útil após deploys ou migrações)."""
    _settings_cache.pop(condo_id, None)
    _cache_loaded.discard(condo_id)
    logger.info(f"🔄 Cache de settings invalidado para condo '{condo_id}'")
