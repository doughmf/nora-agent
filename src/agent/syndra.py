# src/agent/syndra.py
"""
SyndraAgent — Agente principal de IA do condomínio.

Correções aplicadas:
- Assinaturas de get_resident, get_conversation_history e save_message corrigidas (com condo_id)
- _retrieve_context implementado com embeddings OpenAI + semantic_search
- Cache de instâncias por condo_id (evita recriar cliente a cada mensagem)
- Limite de MAX_TOOL_ROUNDS para evitar loop infinito de tool calls
- tool_choice="none" na última chamada LLM após tool calls
"""
import os
import logging
from openai import AsyncOpenAI
from datetime import datetime
from src.supabase.client import (
    get_resident, get_conversation_history,
    save_message, semantic_search
)
from src.whatsapp.sender import send_typing_indicator
from src.agent.tools import TOOLS, execute_tool
from src.agent.prompts import build_system_prompt
import json

from src.api.settings_manager import get_setting

logger = logging.getLogger("syndra.agent")

# Cache de instâncias por condo_id — evita recriar o cliente OpenAI a cada mensagem
_agent_cache: dict[str, "SyndraAgent"] = {}

MAX_TOOL_ROUNDS = 5  # Proteção contra loop infinito de tool calls


def get_agent(condo_id: str) -> "SyndraAgent":
    """Retorna agente em cache ou cria um novo para o condo_id."""
    if condo_id not in _agent_cache:
        _agent_cache[condo_id] = SyndraAgent(condo_id)
    return _agent_cache[condo_id]


class SyndraAgent:
    def __init__(self, condo_id: str):
        self.condo_id = condo_id
        self.provider = get_setting(condo_id, "LLM_PROVIDER", "OpenRouter")
        self.model = get_setting(condo_id, "LLM_MODEL", "stepfun/step-3.5-flash:free")
        self.api_key = get_setting(condo_id, "LLM_API_KEY", os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or "")

        base_url = "https://openrouter.ai/api/v1" if self.provider == "OpenRouter" else None

        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=self.api_key,
        )
        self.max_tokens = 1024

    async def process(self, phone: str, message: str) -> str:
        """Processa mensagem e retorna resposta."""

        # 1. Obter residente (com condo_id correto)
        resident = await get_resident(self.condo_id, phone)

        if not resident:
            return (
                "Olá! Seu número de WhatsApp não consta no cadastro do condomínio.\n\n"
                "Para sua segurança e a do condomínio, apenas moradores cadastrados podem interagir por aqui.\n"
                "Por favor, entre em contato com a administração e solicite o seu cadastro."
            )

        # 2. Recuperar histórico (com condo_id correto)
        history = await get_conversation_history(self.condo_id, phone)

        # 3. Busca semântica na base de conhecimento (RAG implementado)
        context_chunks = await self._retrieve_context(message)

        # 4. Construir prompt
        system_prompt = build_system_prompt(
            condo_id=self.condo_id,
            resident=resident,
            knowledge_context=context_chunks,
            current_datetime=datetime.now().isoformat()
        )

        # 5. Construir mensagens
        messages = [
            *[{"role": m["role"], "content": m["content"]} for m in history],
            {"role": "user", "content": message}
        ]

        # 6. Simular digitação
        await send_typing_indicator(phone, condo_id=self.condo_id, duration=2)

        # 7. Chamar LLM com ferramentas
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=TOOLS,
            tool_choice="auto"
        )

        # 8. Processar tool calls com limite de iterações
        final_response = await self._handle_tool_calls(response, messages, system_prompt)

        # 9. Salvar no histórico (com condo_id e phone corretos)
        session_id = f"{phone}_{datetime.now().strftime('%Y%m%d_%H')}"
        await save_message(self.condo_id, resident["id"], "user", message, session_id, phone)
        await save_message(self.condo_id, resident["id"], "assistant", final_response, session_id, phone)

        return final_response

    async def _retrieve_context(self, query: str) -> list[dict]:
        """Gera embedding e busca contexto relevante via semantic_search."""
        try:
            # Gera embedding usando o mesmo cliente OpenAI/OpenRouter
            embedding_response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            return await semantic_search(self.condo_id, query_embedding)
        except Exception as e:
            logger.warning(f"⚠️  Falha no RAG (busca semântica): {e}")
            return []

    async def _handle_tool_calls(self, response, messages: list, system_prompt: str) -> str:
        """Executa tool calls com proteção contra loop infinito (MAX_TOOL_ROUNDS)."""
        message = response.choices[0].message
        messages.append(message)

        rounds = 0
        while getattr(message, "tool_calls", None) and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            logger.info(f"🔧 Tool calls — round {rounds}/{MAX_TOOL_ROUNDS}")

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = await execute_tool(name, args, condo_id=self.condo_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

            # Na última chamada pós-tools, não permite novas tool calls
            is_last_round = rounds >= MAX_TOOL_ROUNDS
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                tools=TOOLS if not is_last_round else [],
                tool_choice="none" if is_last_round else "auto"
            )
            message = response.choices[0].message
            messages.append(message)

        if rounds >= MAX_TOOL_ROUNDS:
            logger.warning(f"⚠️  MAX_TOOL_ROUNDS atingido para condo '{self.condo_id}'")

        return message.content or "Desculpe, não consegui processar sua solicitação."
