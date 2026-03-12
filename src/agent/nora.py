# src/agent/nora.py
import os
from openai import AsyncOpenAI # Usado para OpenRouter ou OpenAI
from datetime import datetime
from src.supabase.client import (
    get_resident, get_conversation_history,
    save_message, semantic_search
)
from src.whatsapp.sender import send_typing_indicator
from src.agent.tools import TOOLS, execute_tool
from src.agent.prompts import build_system_prompt
import json

# Configuração do cliente (Exemplo com OpenRouter)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

class NoraAgent:
    def __init__(self):
        self.model = "stepfun/step-3.5-flash:free" # Nome do modelo no OpenRouter
        self.max_tokens = 1024
    
    async def process(self, phone: str, message: str) -> str:
        """Processa mensagem e retorna resposta."""
        
        # 1. Obter residente
        resident = await get_resident(phone)
        
        if not resident:
            # Retorno imediato, sem acionar a LLM
            return (
                "Olá! Seu número de WhatsApp não consta no cadastro do Residencial Nogueira Martins.\n\n"
                "Para sua segurança e a do condomínio, apenas moradores cadastrados podem interagir por aqui.\n"
                "Por favor, entre em contato com a administração e solicite o seu cadastro."
            )
        
        # 2. Recuperar histórico
        history = await get_conversation_history(phone)
        
        # 3. Busca semântica na base de conhecimento
        context_chunks = await self._retrieve_context(message)
        
        # 4. Construir prompt
        system_prompt = build_system_prompt(
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
        await send_typing_indicator(phone, duration=2)
        
        # 7. Chamar LLM com ferramentas
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=TOOLS, # Formato precisa ser adaptado dependendo do provedor (ex: OpenAI tools format)
            tool_choice="auto"
        )
        
        # 8. Processar tool calls se necessário
        final_response = await self._handle_tool_calls(response, messages, system_prompt)
        
        # 9. Salvar no histórico
        session_id = f"{phone}_{datetime.now().strftime('%Y%m%d_%H')}"
        await save_message(resident["id"], "user", message, session_id)
        await save_message(resident["id"], "assistant", final_response, session_id)
        
        return final_response
    
    async def _retrieve_context(self, query: str) -> list[dict]:
        """Gera embedding e busca contexto relevante."""
        # Usar Voyage AI ou OpenAI para embeddings
        # embedding = embed(query)
        # return await semantic_search(embedding)
        return []  # Implementar com biblioteca de embeddings
    
    async def _handle_tool_calls(self, response, messages: list, system_prompt: str) -> str:
        """Executa tool calls na resposta."""
        message = response.choices[0].message
        messages.append(message)
        
        while getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                result = await execute_tool(name, args)
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id, 
                    "content": json.dumps(result)
                })
            
            response = await client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            message = response.choices[0].message
            messages.append(message)

        return message.content or "Desculpe, não consegui processar."
