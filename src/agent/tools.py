"""
Syndra Agent — Definição das Tools para OpenAI/OpenRouter (Multi-tenant)
"""
from datetime import datetime
import uuid
import os
import importlib.util
import logging
from src.api.settings_manager import get_setting

logger = logging.getLogger("syndra.skills")

# ─── Definição Dinâmica de Skills ─────────────────────────
NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_regimento",
            "description": "Consulta o regimento interno e base de conhecimento do condomínio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_chamado_manutencao",
            "description": "Abre um chamado de manutenção no sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["Elétrica", "Hidráulica", "Estrutural", "Equipamento", "Limpeza", "Outro"]},
                    "descricao": {"type": "string"},
                    "localizacao": {"type": "string"},
                    "urgencia": {"type": "string", "enum": ["P1", "P2", "P3"]}
                },
                "required": ["tipo", "descricao", "localizacao", "urgencia"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_disponibilidade_espaco",
            "description": "Verifica se um espaço do condomínio está disponível.",
            "parameters": {
                "type": "object",
                "properties": {
                    "espaco": {"type": "string", "enum": ["salao_festas", "churrasqueira", "quadra", "academia"]},
                    "data": {"type": "string"},
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
            "description": "Cria uma pré-reserva de espaço para o morador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "espaco": {"type": "string"},
                    "data": {"type": "string"},
                    "periodo": {"type": "string"},
                    "num_convidados": {"type": "integer"}
                },
                "required": ["espaco", "data", "periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "notificar_sindico",
            "description": "Envia notificação urgente ao síndico via WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assunto": {"type": "string"},
                    "nivel": {"type": "string", "enum": ["URGENTE", "IMPORTANTE", "INFORMATIVO"]},
                    "detalhes": {"type": "string"}
                },
                "required": ["assunto", "nivel", "detalhes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_status_chamado",
            "parameters": {
                "type": "object",
                "properties": {
                    "protocolo": {"type": "string"}
                },
                "required": ["protocolo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_perfil_morador",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "name": {"type": "string"},
                    "block": {"type": "string"},
                    "apartment": {"type": "string"},
                    "is_owner": {"type": "boolean"}
                },
                "required": ["phone", "name", "block", "apartment", "is_owner"]
            }
        }
    }
]

TOOLS = list(NATIVE_TOOLS)
EXTERNAL_HANDLERS = {}

def load_skills():
    global TOOLS, EXTERNAL_HANDLERS
    TOOLS = list(NATIVE_TOOLS)
    EXTERNAL_HANDLERS = {}
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    if not os.path.exists(skills_dir): return
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
            except Exception as e:
                logger.error(f"❌ Skill {module_name} error: {e}")

load_skills()

async def execute_tool(tool_name: str, tool_input: dict, condo_id: str) -> dict:
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
            return {"erro": f"Erro nativa {tool_name}: {str(e)}"}
    
    external_handler = EXTERNAL_HANDLERS.get(tool_name)
    if external_handler:
        try:
            return await external_handler(condo_id=condo_id, **tool_input)
        except Exception as e:
            return {"erro": f"Erro skill {tool_name}: {str(e)}"}
            
    return {"erro": f"Tool '{tool_name}' não encontrada"}

async def _atualizar_perfil_morador(condo_id: str, phone: str, name: str, block: str, apartment: str, is_owner: bool) -> dict:
    from src.supabase.client import supabase
    supabase.table("residents").update({
        "name": name, "block": block, "apartment": apartment, "is_owner": is_owner,
        "profile": {"onboarding_complete": True}
    }).eq("condo_id", condo_id).eq("whatsapp_phone", phone).execute()
    return {"status": "Perfil atualizado para este condomínio"}

async def _buscar_regimento(condo_id: str, query: str) -> dict:
    return {"resultado": "Consulta recebida para isolamento.", "condo_id": condo_id}

async def _abrir_chamado_manutencao(condo_id: str, tipo: str, descricao: str, localizacao: str, urgencia: str) -> dict:
    from src.supabase.client import supabase
    protocol = f"MNT-{datetime.now().strftime('%Y')}-{str(uuid.uuid4())[:4].upper()}"
    supabase.table("maintenance_requests").insert({
        "condo_id": condo_id, "protocol": protocol, "type": tipo, 
        "description": descricao, "location": localizacao, "urgency": urgencia
    }).execute()
    return {"protocolo": protocol, "status": "Chamado aberto no seu condomínio"}

async def _verificar_disponibilidade(condo_id: str, espaco: str, data: str, periodo: str) -> dict:
    from src.supabase.client import supabase
    res = supabase.table("space_bookings").select("id").eq("condo_id", condo_id).eq("space", espaco).eq("booking_date", data).eq("period", periodo).in_("status", ["confirmado", "pendente"]).execute()
    disponivel = len(res.data) == 0
    return {"disponivel": disponivel, "mensagem": "Livre!" if disponivel else "Ocupado."}

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
        "instrucao_pagamento": f"PIX ({pix_tipo}): {pix_chave} - {pix_nome}. Envie o comprovante."
    }

async def _notificar_sindico(condo_id: str, assunto: str, nivel: str, detalhes: str) -> dict:
    from src.whatsapp.sender import send_message
    sindico_phone = get_setting(condo_id, "SINDICO_PHONE", "")
    if sindico_phone:
        await send_message(sindico_phone, f"[{nivel}] {assunto}: {detalhes}")
    return {"enviado": bool(sindico_phone)}

async def _consultar_status_chamado(condo_id: str, protocolo: str) -> dict:
    from src.supabase.client import supabase
    res = supabase.table("maintenance_requests").select("*").eq("condo_id", condo_id).eq("protocol", protocolo).single().execute()
    if not res.data: return {"erro": "Não encontrado"}
    return {"protocolo": protocolo, "status": res.data["status"]}
