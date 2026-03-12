"""
Nora Agent — Definição das Tools para OpenAI/OpenRouter
"""
from datetime import datetime
import uuid

# ─── Definição das Tools (formato OpenAI/OpenRouter) ───────
TOOLS = [
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
    }
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
                    "apartment": {
                        "type": "string",
                        "description": "Número do bloco e apartamento do morador (Ex: Bloco 1, Apt 03)"
                    }
                },
                "required": ["phone", "name", "apartment"]
            }
        }
    }
]


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
    
    handler = handlers.get(tool_name)
    if not handler:
        return {"erro": f"Tool '{tool_name}' não encontrada"}
    
    try:
        return await handler(**tool_input)
    except Exception as e:
        return {"erro": f"Falha ao executar {tool_name}: {str(e)}"}


async def _atualizar_perfil_morador(phone: str, name: str, apartment: str) -> dict:
    """Invoca o backend para atualizar o morador."""
    from src.supabase.client import update_resident_profile
    return await update_resident_profile(phone, name, apartment)


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
    
    return {
        "booking_ref": booking_ref,
        "espaco": espaco,
        "data": data,
        "periodo": periodo,
        "valor": valor,
        "status": "Pré-reserva criada. Aguardando confirmação do pagamento.",
        "instrucao_pagamento": f"Realize um Pix de R$ {valor:.2f} para a chave do condomínio e envie o comprovante."
    }


async def _notificar_sindico(assunto: str, nivel: str, detalhes: str) -> dict:
    """Notifica síndico via WhatsApp."""
    import os
    from src.whatsapp.sender import send_message
    
    sindico_phone = os.getenv("SINDICO_PHONE", "")
    
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
