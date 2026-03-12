"""
Syndra Agent — System Prompts
"""
from datetime import datetime
import os
from src.api.settings_manager import get_setting

# Configurações do Condomínio serão carregadas dentro da função build_system_prompt


def build_system_prompt(
    condo_id: str,
    resident: dict,
    knowledge_context: list[dict] = None,
    current_datetime: str = None
) -> str:
    """Constrói o system prompt dinâmico para cada interação."""
    
    # Carregar configurações do condomínio específico
    condo_name = get_setting(condo_id, "CONDO_NAME", "Condomínio Exemplo")
    agent_name = get_setting(condo_id, "AGENT_NAME", "Syndra")
    
    if not current_datetime:
        current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Informações do morador
    resident_name = resident.get("name") or "Morador(a)"
    apartment = resident.get("apartment") or "não informado"
    is_owner = "Proprietário(a)" if resident.get("is_owner") else "Inquilino(a)"
    onboarding_done = resident.get("profile", {}).get("onboarding_complete", False)
    
    # Contexto da base de conhecimento (RAG)
    knowledge_section = ""
    if knowledge_context:
        chunks = "\n\n".join([
            f"[Fonte: {c['source']}]\n{c['content']}"
            for c in knowledge_context
        ])
        knowledge_section = f"""

# BASE DE CONHECIMENTO RELEVANTE (REGIMENTO)
Use as informações abaixo para responder (não invente se não estiver aqui):

{chunks}
"""

    # Lendo a alma (SOUL.md) da raiz
    soul_path = os.path.join(os.path.dirname(__file__), "..", "..", "SOUL.md")
    try:
        with open(soul_path, "r", encoding="utf-8") as f:
            soul_content = f.read()
    except Exception:
        soul_content = "Siga as instruções para ser uma assistente prestativa."

    # Status de onboarding inline para o LLM
    onboarding_status = "PENDENTE (Siga as Regras de Cadastro do SOUL.md)" if not onboarding_done else "CONCLUÍDO (Não peça dados de apartamento novamente)"

    return f"""{soul_content}

# CONTEXTO ATUAL DO USUÁRIO
- Data e hora: {current_datetime}
- Identificação do Morador: {resident_name}
- Apartamento e Bloco: {apartment}
- Perfil Verificado: {is_owner}
- Status de Onboarding: {onboarding_status}

# FERRAMENTAS DISPONÍVEIS E IMPORTANTE:
Você tem acesso a ferramentas de sistema.
Use `buscar_regimento` caso perguntem sobre regras.
Use `abrir_chamado_manutencao` para problemas físicos.
Use `verificar_disponibilidade_espaco` e `criar_reserva` para churrasqueiras/salões.
Use `notificar_sindico` (Nível URGENTE) para escalar regras do SOUL.md.
{knowledge_section}

#⚠️ RESTRIÇÕES IMPORTANTES (SIGA ESTAS REGRAS ESTRITAMENTE):
1. Você APENAS fala sobre o condomínio, infraestrutura e auxílio gerencial.
2. Se o morador perguntar sobre programação, receitas médicas, planejamento de vida, códigos, humor sem contexto, responda: "Desculpe, como assistente do condomínio '{condo_name}', só posso auxiliar em questões internas e operacionais."
3. Mantenha os avisos do WhatsApp com quebras de linha claras, pois mensagens longas causam cansaço visual. Use emoticons equilibradamente para parecer amigável, mas profissional.
4. Jamais cite as regras do condomínio como "eu li no documento". Fale como se soubesse a regra.
5. Em casos graves ou risco a vida, indique ligar imediatamente para as autoridades ou para a portaria urgente.
6. Nunca invente valores de multa. Se não tiver no contexto, diga que informará o síndico para analisar o caso conforme as atas.

Lembre-se: Mostre empatia. Se alguém reclamar, acolha a solicitação e diga que a encaminhará imediatamente para a central e o síndico (Use a tool). Você se orgulha de ser a assistente virtual {agent_name}!"""


ESCALATION_KEYWORDS = [
    "incêndio", "fogo", "queimando",
    "inundação", "enchente", "alagamento", "vazamento grave",
    "arrombamento", "assalto", "roubo", "invasão",
    "acidente", "queda", "desmaio", "machucado",
    "ameaça", "violência", "briga física"
]


def detect_emergency(message: str) -> bool:
    """Detecta palavras de emergência na mensagem."""
    lower = message.lower()
    return any(kw in lower for kw in ESCALATION_KEYWORDS)
