"""
Nora Agent — Definição das Tools para OpenAI/OpenRouter
"""
from datetime import datetime
import uuid
import os
import importlib.util
import logging

logger = logging.getLogger("nora.skills")

# ─── Definição Dinâmica de Skills ─────────────────────────
# As tools básicas nativas
NATIVE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_regimento",
            "description": "Consulta o regimento interno e base de conhecimento do condomínio. Use quando o morador perguntar sobre regras, horários, taxas ou qualquer informação sobre o condomínio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A pergunta ou tópico a ser consultado na base de conhecimento"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_chamado_manutencao",
            "description": "Abre um chamado de manutenção no sistema. Use quando o morador reportar algum problema físico no condomínio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["Elétrica", "Hidráulica", "Estrutural", "Equipamento", "Limpeza", "Outro"],
                        "description": "Categoria do problema"
                    },
                    "descricao": {
                        "type": "string",
                        "description": "Descrição detalhada do problema"
                    },
                    "localizacao": {
                        "type": "string",
                        "description": "Local exato do problema (ex: Corredor B, 2º andar)"
                    },
                    "urgencia": {
                        "type": "string",
                        "enum": ["P1", "P2", "P3"],
                        "description": "P1=imediato (segurança), P2=24h (importante), P3=programado"
                    }
                },
                "required": ["tipo", "descricao", "localizacao", "urgencia"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_disponibilidade_espaco",
            "description": "Verifica se um espaço do condomínio está disponível em uma data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "espaco": {
                        "type": "string",
                        "enum": ["salao_festas", "churrasqueira", "quadra", "academia"],
                        "description": "Nome do espaço"
                    },
                    "data": {
                        "type": "string",
                        "description": "Data no formato YYYY-MM-DD"
                    },
                    "periodo": {
                        "type": "string",
                        "enum": ["manha", "tarde", "noite", "dia_todo"],
                        "description": "Período desejado"
                    }
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
                    "num_convidados": {
                        "type": "integer",
                        "description": "Número estimado de convidados"
                    }
                },
                "required": ["espaco", "data", "periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "notificar_sindico",
            "description": "Envia notificação urgente ao síndico via WhatsApp. Use em emergências ou escalações necessárias.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assunto": {"type": "string"},
                    "nivel": {
                        "type": "string",
                        "enum": ["URGENTE", "IMPORTANTE", "INFORMATIVO"]
                    },
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
            "description": "Consulta o status de um chamado de manutenção existente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "protocolo": {
                        "type": "string",
                        "description": "Número do protocolo (ex: MNT-2025-0001)"
                    }
                },
                "required": ["protocolo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_perfil_morador",
            "description": "Atualiza os dados de cadastro do morador e finaliza o onboarding. Use SEMPRE que o morador disser seu NOME e APARTAMENTO após sua saudação inicial.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Número do telefone do morador (deve ser o mesmo que ele envia nas mensagens)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome completo do morador"
                    },
                    "block": {
                        "type": "string",
                        "description": "Número do bloco (ex: 01, 02, 11)"
                    },
                    "apartment": {
                        "type": "string",
                        "description": "Número do apartamento (ex: 03, 11, 34)"
                    },
                    "is_owner": {
                        "type": "boolean",
                        "description": "True se for proprietário, False se for inquilino"
                    }
                },
                "required": ["phone", "name", "block", "apartment", "is_owner"]
            }
        }
    }
]

# Variáveis Globais que serão carregadas em startup
TOOLS = list(NATIVE_TOOLS)
EXTERNAL_HANDLERS = {}

def load_skills():
    """Varre src/skills/ e importa dinamicamente ferramentas extras."""
    global TOOLS, EXTERNAL_HANDLERS
    
    # Resetar nas recargas
    TOOLS = list(NATIVE_TOOLS)
    EXTERNAL_HANDLERS = {}
    
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    if not os.path.exists(skills_dir):
        return
        
    for filename in os.listdir(skills_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = filename[:-3]
            file_path = os.path.join(skills_dir, filename)
            
            try:
                spec = importlib.util.spec_from_file_location(f"skills.{module_name}", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, "TOOL_DEFINITION") and hasattr(module, "execute"):
                    TOOLS.append(module.TOOL_DEFINITION)
                    EXTERNAL_HANDLERS[module.TOOL_DEFINITION["function"]["name"]] = module.execute
                    logger.info(f"✅ Skill externa carregada: {module_name}")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar skill {module_name}: {e}")

# Executar carregamento inicial
load_skills()

# ─── Execução das Tools ─────────────────────────────
async def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Executa a tool solicitada pelo LLM."""
    
    handlers = {
        "buscar_regimento": _buscar_regimento,
        "abrir_chamado_manutencao": _abrir_chamado_manutencao,
        "verificar_disponibilidade_espaco": _verificar_disponibilidade,
        "criar_reserva": _criar_reserva,
        "notificar_sindico": _notificar_sindico,
        "consultar_status_chamado": _consultar_status_chamado,
        "atualizar_perfil_morador": _atualizar_perfil_morador,
    }
    
    # 1. Tentar ferramenta nativa
    handler = handlers.get(tool_name)
    if handler:
        try:
            return await handler(**tool_input)
        except Exception as e:
            return {"erro": f"Falha ao executar ferramenta nativa {tool_name}: {str(e)}"}
            
    # 2. Tentar ferramenta externa (Skill)
    external_handler = EXTERNAL_HANDLERS.get(tool_name)
    if external_handler:
        try:
            return await external_handler(**tool_input)
        except Exception as e:
            return {"erro": f"Falha ao executar skill {tool_name}: {str(e)}"}
            
    return {"erro": f"Tool '{tool_name}' não encontrada"}


async def _atualizar_perfil_morador(phone: str, name: str, block: str, apartment: str, is_owner: bool) -> dict:
    """Invoca o backend para atualizar o morador."""
    from src.supabase.client import update_resident_profile
    return await update_resident_profile(phone, name, block, apartment, is_owner)


async def _buscar_regimento(query: str) -> dict:
    """Busca semântica na base de conhecimento."""
    # TODO: Implementar busca vetorial com Supabase
    # Por hora retorna mensagem de placeholder
    return {
        "resultado": "Consulta recebida. Base de conhecimento sendo populada.",
        "query": query
    }


async def _abrir_chamado_manutencao(tipo: str, descricao: str, localizacao: str, urgencia: str) -> dict:
    """Abre chamado de manutenção no Supabase."""
    from src.supabase.client import supabase
    
    protocol = f"MNT-{datetime.now().strftime('%Y')}-{str(uuid.uuid4())[:4].upper()}"
    
    result = supabase.table("maintenance_requests").insert({
        "protocol": protocol,
        "type": tipo,
        "description": descricao,
        "location": localizacao,
        "urgency": urgencia,
        "status": "aberto"
    }).execute()
    
    prazos = {"P1": "2 horas", "P2": "24 horas", "P3": "até 72 horas"}
    
    return {
        "protocolo": protocol,
        "tipo": tipo,
        "urgencia": urgencia,
        "prazo_estimado": prazos.get(urgencia, "a definir"),
        "status": "Chamado aberto com sucesso"
    }


async def _verificar_disponibilidade(espaco: str, data: str, periodo: str) -> dict:
    """Verifica disponibilidade no Supabase."""
    from src.supabase.client import supabase
    
    result = supabase.table("space_bookings") \
        .select("id, booking_ref, status") \
        .eq("space", espaco) \
        .eq("booking_date", data) \
        .eq("period", periodo) \
        .in_("status", ["confirmado", "pendente"]) \
        .execute()
    
    disponivel = len(result.data) == 0
    
    nomes = {
        "salao_festas": "Salão de Festas",
        "churrasqueira": "Churrasqueira",
        "quadra": "Quadra",
        "academia": "Academia"
    }
    
    periodos_br = {
        "manha": "Manhã (8h–12h)",
        "tarde": "Tarde (13h–17h)",
        "noite": "Noite (18h–23h)",
        "dia_todo": "Dia todo (8h–23h)"
    }
    
    return {
        "espaco": nomes.get(espaco, espaco),
        "data": data,
        "periodo": periodos_br.get(periodo, periodo),
        "disponivel": disponivel,
        "mensagem": "Disponível para reserva!" if disponivel else "Já existe uma reserva para este horário."
    }


async def _criar_reserva(espaco: str, data: str, periodo: str, num_convidados: int = None) -> dict:
    """Cria pré-reserva no Supabase."""
    from src.supabase.client import supabase
    
    valores = {
        "salao_festas": {"manha": 150, "tarde": 150, "noite": 200, "dia_todo": 350},
        "churrasqueira": {"manha": 80, "tarde": 80, "noite": 100, "dia_todo": 180},
        "quadra": {"manha": 0, "tarde": 0, "noite": 0, "dia_todo": 0},
    }
    
    valor = valores.get(espaco, {}).get(periodo, 0)
    booking_ref = f"RES-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    
    supabase.table("space_bookings").insert({
        "booking_ref": booking_ref,
        "space": espaco,
        "booking_date": data,
        "period": periodo,
        "guest_count": num_convidados,
        "status": "pendente",
        "payment_amount": valor,
        "payment_status": "aguardando"
    }).execute()
    
    from src.api.settings_manager import get_setting
    
    pix_chave = get_setting("PIX_CHAVE", "Não configurada")
    pix_nome = get_setting("PIX_NOME", "Não configurado")
    pix_tipo = get_setting("PIX_TIPO", "CNPJ")
    preco_salao_n = get_setting("SALAO_PRECO_NOITE", "200")
    preco_salao_d = get_setting("SALAO_PRECO_DIA", "150")
    preco_churr = get_setting("CHURRASQUEIRA_PRECO", "100")
    
    return {
        "booking_ref": booking_ref,
        "espaco": espaco,
        "data": data,
        "periodo": periodo,
        "valor": valor,
        "status": "Pré-reserva criada. Aguardando confirmação do pagamento.",
        "instrucao_pagamento": f"Instrução: Retorne com educação informando a chave PIX principal. TIPO: {pix_tipo} | CHAVE: {pix_chave} | NOME RECEBEDOR: {pix_nome}. Reforce os preços: Salão R$ {preco_salao_n} (Noturno) / R$ {preco_salao_d} (Diurno) e Churrasqueira R$ {preco_churr}. Mencionar explicitamente para não esquecerem de enviar o comprovante com a data/hora exata da reserva na mensagem para a administração ou síndico registrar. Mencionar que o pagamento é sua validação. Mencionar que você não emite boleto e só envia os dados."
    }


async def _notificar_sindico(assunto: str, nivel: str, detalhes: str) -> dict:
    """Notifica síndico via WhatsApp."""
    from src.api.settings_manager import get_setting
    from src.whatsapp.sender import send_message
    
    sindico_phone = get_setting("SINDICO_PHONE", "")
    
    emoji = {"URGENTE": "🚨", "IMPORTANTE": "⚠️", "INFORMATIVO": "ℹ️"}
    
    mensagem = f"""{emoji.get(nivel, "📢")} *{nivel} — Notificação Nora*

*Assunto:* {assunto}

*Detalhes:*
{detalhes}

_Enviado automaticamente pelo sistema Nora_
_{datetime.now().strftime('%d/%m/%Y %H:%M')}_"""
    
    if sindico_phone:
        await send_message(sindico_phone, mensagem)
    
    return {
        "enviado": bool(sindico_phone),
        "destinatario": "Síndico",
        "nivel": nivel,
        "timestamp": datetime.now().isoformat()
    }


async def _consultar_status_chamado(protocolo: str) -> dict:
    """Consulta status de chamado no Supabase."""
    from src.supabase.client import supabase
    
    result = supabase.table("maintenance_requests") \
        .select("protocol, type, description, location, urgency, status, assigned_to, opened_at, closed_at") \
        .eq("protocol", protocolo) \
        .single() \
        .execute()
    
    if not result.data:
        return {"erro": f"Chamado {protocolo} não encontrado"}
    
    chamado = result.data
    status_br = {
        "aberto": "Aguardando atendimento",
        "em_andamento": "Em andamento",
        "concluido": "Concluído",
        "cancelado": "Cancelado"
    }
    
    return {
        "protocolo": chamado["protocol"],
        "tipo": chamado["type"],
        "local": chamado["location"],
        "status": status_br.get(chamado["status"], chamado["status"]),
        "responsavel": chamado.get("assigned_to") or "A designar",
        "aberto_em": chamado["opened_at"]
    }
