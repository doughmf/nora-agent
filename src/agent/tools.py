"""
Syndra Agent — Definição das Tools para OpenAI/OpenRouter (Multi-tenant)

Correções aplicadas:
- Descriptions adicionadas em consultar_status_chamado e atualizar_perfil_morador
- _buscar_regimento implementado com semantic_search real
- _atualizar_perfil_morador usa update_resident_profile do client.py (sem duplicar lógica)
- Tool calls são async de forma consistente
"""
from datetime import datetime
import uuid
import os
import importlib.util
import logging
from src.api.settings_manager import get_setting

logger = logging.getLogger("syndra.skills")

# ─── Definição das Tools Nativas ──────────────────────────
NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_regimento",
            "description": "Consulta o regimento interno e base de conhecimento do condomínio. Use sempre que o morador perguntar sobre regras, normas, horários ou políticas do condomínio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Pergunta ou trecho sobre o qual buscar no regimento"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_chamado_manutencao",
            "description": "Abre um chamado de manutenção no sistema para problemas físicos no condomínio (elétrica, hidráulica, limpeza, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["Elétrica", "Hidráulica", "Estrutural", "Equipamento", "Limpeza", "Outro"]},
                    "descricao": {"type": "string", "description": "Descrição detalhada do problema"},
                    "localizacao": {"type": "string", "description": "Local do problema (ex: Bloco A, Corredor 2º andar)"},
                    "urgencia": {"type": "string", "enum": ["P1", "P2", "P3"], "description": "P1=Urgente, P2=Normal, P3=Baixa prioridade"}
                },
                "required": ["tipo", "descricao", "localizacao", "urgencia"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_disponibilidade_espaco",
            "description": "Verifica se um espaço comum do condomínio (salão, churrasqueira, quadra, academia) está disponível em uma data e período específicos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "espaco": {"type": "string", "enum": ["salao_festas", "churrasqueira", "quadra", "academia"]},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                    "periodo": {"type": "string", "enum": ["manha", "tarde", "noite", "dia_todo"]}
                },
                "required": ["espaco", "data", "periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "criar_reserva",
            "description": "Cria uma pré-reserva de espaço comum para o morador após confirmar disponibilidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "espaco": {"type": "string", "description": "Nome do espaço a reservar"},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                    "periodo": {"type": "string", "enum": ["manha", "tarde", "noite", "dia_todo"]},
                    "num_convidados": {"type": "integer", "description": "Número estimado de convidados"}
                },
                "required": ["espaco", "data", "periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "notificar_sindico",
            "description": "Envia notificação ao síndico via WhatsApp. Use para situações urgentes, reclamações graves ou solicitações que requerem decisão administrativa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assunto": {"type": "string", "description": "Título resumido da notificação"},
                    "nivel": {"type": "string", "enum": ["URGENTE", "IMPORTANTE", "INFORMATIVO"]},
                    "detalhes": {"type": "string", "description": "Descrição completa da situação"}
                },
                "required": ["assunto", "nivel", "detalhes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_status_chamado",
            "description": "Consulta o status atual de um chamado de manutenção pelo número de protocolo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "protocolo": {"type": "string", "description": "Número do protocolo do chamado (ex: MNT-2024-AB12)"}
                },
                "required": ["protocolo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_perfil_morador",
            "description": "Atualiza os dados cadastrais do morador (nome, bloco, apartamento, tipo de ocupação). Use durante o onboarding ou quando o morador solicitar correção de dados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Número de telefone do morador"},
                    "name": {"type": "string", "description": "Nome completo"},
                    "block": {"type": "string", "description": "Bloco do apartamento"},
                    "apartment": {"type": "string", "description": "Número do apartamento"},
                    "is_owner": {"type": "boolean", "description": "True se proprietário, False se inquilino"}
                },
                "required": ["phone", "name", "block", "apartment", "is_owner"]
            }
        }
    }
]

TOOLS = list(NATIVE_TOOLS)
EXTERNAL_HANDLERS = {}


def load_skills():
    """Carrega skills externas da pasta /src/skills dinamicamente."""
    global TOOLS, EXTERNAL_HANDLERS
    TOOLS = list(NATIVE_TOOLS)
    EXTERNAL_HANDLERS = {}
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    if not os.path.exists(skills_dir):
        return
    for filename in os.listdir(skills_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(f"skills.{module_name}", os.path.join(skills_dir, filename))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "TOOL_DEFINITION") and hasattr(module, "execute"):
                    TOOLS.append(module.TOOL_DEFINITION)
                    EXTERNAL_HANDLERS[module.TOOL_DEFINITION["function"]["name"]] = module.execute
                    logger.info(f"✅ Skill carregada: {module_name}")
            except Exception as e:
                logger.error(f"❌ Skill {module_name} error: {e}")


load_skills()


async def execute_tool(tool_name: str, tool_input: dict, condo_id: str) -> dict:
    """Dispatcher de tools nativas e externas."""
    handlers = {
        "buscar_regimento": _buscar_regimento,
        "abrir_chamado_manutencao": _abrir_chamado_manutencao,
        "verificar_disponibilidade_espaco": _verificar_disponibilidade,
        "criar_reserva": _criar_reserva,
        "notificar_sindico": _notificar_sindico,
        "consultar_status_chamado": _consultar_status_chamado,
        "atualizar_perfil_morador": _atualizar_perfil_morador,
    }
    handler = handlers.get(tool_name)
    if handler:
        try:
            return await handler(condo_id=condo_id, **tool_input)
        except Exception as e:
            logger.error(f"❌ Erro na tool nativa '{tool_name}': {e}", exc_info=True)
            return {"erro": f"Erro ao executar {tool_name}: {str(e)}"}

    external_handler = EXTERNAL_HANDLERS.get(tool_name)
    if external_handler:
        try:
            return await external_handler(condo_id=condo_id, **tool_input)
        except Exception as e:
            logger.error(f"❌ Erro na skill '{tool_name}': {e}", exc_info=True)
            return {"erro": f"Erro ao executar skill {tool_name}: {str(e)}"}

    return {"erro": f"Tool '{tool_name}' não encontrada"}


# ─── Implementações das Tools Nativas ─────────────────────

async def _buscar_regimento(condo_id: str, query: str) -> dict:
    """Busca semântica real no regimento/base de conhecimento do condomínio."""
    try:
        from src.supabase.client import semantic_search
        from src.api.settings_manager import get_setting
        from openai import AsyncOpenAI

        api_key = get_setting(condo_id, "LLM_API_KEY", os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or "")
        provider = get_setting(condo_id, "LLM_PROVIDER", "OpenRouter")
        base_url = "https://openrouter.ai/api/v1" if provider == "OpenRouter" else None

        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        embedding_response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        query_embedding = embedding_response.data[0].embedding
        results = await semantic_search(condo_id, query_embedding)

        if not results:
            return {"resultado": "Nenhuma informação encontrada no regimento para essa consulta.", "chunks": []}

        return {
            "resultado": "Informações encontradas no regimento:",
            "chunks": [{"fonte": r.get("source", ""), "conteudo": r.get("content", "")} for r in results]
        }
    except Exception as e:
        logger.error(f"❌ Erro em buscar_regimento: {e}")
        return {"erro": "Não foi possível consultar o regimento no momento."}


async def _abrir_chamado_manutencao(condo_id: str, tipo: str, descricao: str, localizacao: str, urgencia: str) -> dict:
    from src.supabase.client import supabase
    protocol = f"MNT-{datetime.now().strftime('%Y')}-{str(uuid.uuid4())[:4].upper()}"
    supabase.table("maintenance_requests").insert({
        "condo_id": condo_id, "protocol": protocol, "type": tipo,
        "description": descricao, "location": localizacao, "urgency": urgencia
    }).execute()
    return {"protocolo": protocol, "status": "Chamado aberto com sucesso"}


async def _verificar_disponibilidade(condo_id: str, espaco: str, data: str, periodo: str) -> dict:
    from src.supabase.client import supabase
    res = supabase.table("space_bookings").select("id") \
        .eq("condo_id", condo_id).eq("space", espaco) \
        .eq("booking_date", data).eq("period", periodo) \
        .in_("status", ["confirmado", "pendente"]).execute()
    disponivel = len(res.data) == 0
    return {"disponivel": disponivel, "mensagem": "Disponível!" if disponivel else "Ocupado para esse período."}


async def _criar_reserva(condo_id: str, espaco: str, data: str, periodo: str, num_convidados: int = None) -> dict:
    from src.supabase.client import supabase
    booking_ref = f"RES-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    supabase.table("space_bookings").insert({
        "condo_id": condo_id, "booking_ref": booking_ref, "space": espaco,
        "booking_date": data, "period": periodo, "guest_count": num_convidados
    }).execute()

    pix_chave = get_setting(condo_id, "PIX_CHAVE", "Não configurada")
    pix_nome = get_setting(condo_id, "PIX_NOME", "Não configurado")
    pix_tipo = get_setting(condo_id, "PIX_TIPO", "CNPJ")

    return {
        "booking_ref": booking_ref, "status": "Pré-reserva criada",
        "instrucao_pagamento": f"PIX ({pix_tipo}): {pix_chave} — {pix_nome}. Envie o comprovante para confirmar."
    }


async def _notificar_sindico(condo_id: str, assunto: str, nivel: str, detalhes: str) -> dict:
    from src.whatsapp.sender import send_message
    sindico_phone = get_setting(condo_id, "SINDICO_PHONE", "")
    if sindico_phone:
        await send_message(sindico_phone, f"[{nivel}] {assunto}\n\n{detalhes}", condo_id=condo_id)
    else:
        logger.warning(f"⚠️  SINDICO_PHONE não configurado para condo '{condo_id}'")
    return {"enviado": bool(sindico_phone), "destino": sindico_phone or "não configurado"}


async def _consultar_status_chamado(condo_id: str, protocolo: str) -> dict:
    from src.supabase.client import supabase
    res = supabase.table("maintenance_requests").select("*") \
        .eq("condo_id", condo_id).eq("protocol", protocolo).maybe_single().execute()
    if not res.data:
        return {"erro": f"Protocolo '{protocolo}' não encontrado neste condomínio."}
    d = res.data
    return {
        "protocolo": protocolo,
        "status": d.get("status", "desconhecido"),
        "tipo": d.get("type"),
        "descricao": d.get("description"),
        "urgencia": d.get("urgency"),
        "criado_em": d.get("created_at")
    }


async def _atualizar_perfil_morador(condo_id: str, phone: str, name: str, block: str, apartment: str, is_owner: bool) -> dict:
    """Usa a função centralizada do client.py (sem duplicar lógica)."""
    from src.supabase.client import update_resident_profile
    result = await update_resident_profile(condo_id, phone, name, block, apartment, is_owner)
    if "erro" in result:
        return result
    return {"status": "Perfil atualizado com sucesso", "dados": {"name": name, "block": block, "apartment": apartment}}
