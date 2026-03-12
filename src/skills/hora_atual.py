import datetime

# A DEFINIÇÃO QUE VAI PRO MOTOR DO OPENROUTER/OPENAI
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "consultar_hora_servidor",
        "description": "Retorna o horário exato e atual do servidor da Nora. Use APENAS quando o usuário perguntar explicitamente a hora ou data de hoje.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

# A LÓGICA QUE RODA EM PYTHON (Precisa se chamar 'execute')
async def execute(**kwargs) -> dict:
    hora_atual = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
    return {
        "hora_servidor": hora_atual,
        "mensagem": "Horário consultado com sucesso.",
        "fonte": "Nora Agent OS"
    }
