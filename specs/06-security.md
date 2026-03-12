# SPEC-06: Security — Segurança e Privacidade

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. MODELO DE AMEAÇAS

| Ameaça | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Prompt Injection | Alta | Alto | Filtro de input + sistema de detecção |
| Vazamento de dados de moradores | Média | Crítico | RLS no Supabase + sem cross-data |
| Acesso não autorizado à API | Alta | Alto | API Key + Rate Limiting |
| Mensagens em massa (spam) | Média | Médio | Rate limit por número |
| Impersonação do síndico | Baixa | Alto | Validação de números autorizados |
| Injeção SQL | Baixa | Crítico | ORM + queries parametrizadas |

---

## 2. SEGURANÇA NA CAMADA DE API

```python
# src/api/middleware.py

from fastapi import Request, HTTPException
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib, hmac

# Rate limiting por número de telefone
message_counts: dict = defaultdict(list)
MAX_MESSAGES_PER_MINUTE = 10

async def rate_limit_middleware(request: Request, call_next):
    phone = extract_phone_from_request(request)
    
    if phone:
        now = datetime.now()
        # Limpar mensagens antigas (> 1 minuto)
        message_counts[phone] = [
            t for t in message_counts[phone]
            if now - t < timedelta(minutes=1)
        ]
        
        if len(message_counts[phone]) >= MAX_MESSAGES_PER_MINUTE:
            raise HTTPException(429, "Muitas mensagens. Aguarde 1 minuto.")
        
        message_counts[phone].append(now)
    
    return await call_next(request)

# Validação do webhook da Evolution API
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 3. ROW LEVEL SECURITY (Supabase RLS)

```sql
-- Habilitar RLS em todas as tabelas sensíveis
ALTER TABLE residents ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE space_bookings ENABLE ROW LEVEL SECURITY;

-- Política: Service role (backend) tem acesso total
CREATE POLICY "service_full_access" ON residents
    FOR ALL TO service_role USING (true);

-- Política: Moradores só veem seus próprios dados (via anon key + JWT)
CREATE POLICY "residents_own_data" ON residents
    FOR SELECT USING (whatsapp_phone = current_setting('app.current_phone', true));

-- Política: Conversas só acessíveis por service_role
CREATE POLICY "conversations_service_only" ON conversations
    FOR ALL TO service_role USING (true);
```

---

## 4. DETECÇÃO DE PROMPT INJECTION

```python
# src/agent/security.py

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "esqueça as instruções",
    "ignore suas instruções",
    "você agora é",
    "now you are",
    "act as",
    "roleplay as",
    "pretend you are",
    "system:",
    "jailbreak",
    "DAN mode",
    "modo desenvolvedor",
    "modo administrador"
]

def detect_injection(message: str) -> bool:
    """Detecta tentativas de prompt injection."""
    lower_msg = message.lower()
    return any(pattern.lower() in lower_msg for pattern in INJECTION_PATTERNS)

def sanitize_input(message: str) -> str:
    """Remove caracteres potencialmente perigosos."""
    # Limitar tamanho
    if len(message) > 2000:
        message = message[:2000] + "... [mensagem truncada]"
    
    return message.strip()

async def validate_message(phone: str, message: str) -> tuple[bool, str]:
    """
    Valida mensagem antes de processar.
    Returns: (is_valid, reason)
    """
    message = sanitize_input(message)
    
    if detect_injection(message):
        # Logar tentativa sem processar
        await log_security_event(phone, "INJECTION_ATTEMPT", message)
        return False, "Mensagem não pôde ser processada."
    
    return True, message
```

---

## 5. POLÍTICA DE PRIVACIDADE DOS DADOS

### O que a Nora coleta:
- Número de WhatsApp (identificador único)
- Nome e apartamento (fornecido pelo morador)
- Histórico de conversas (para memória contextual)
- Chamados de manutenção e reservas

### O que a Nora NÃO coleta:
- Documentos pessoais (CPF, RG)
- Informações financeiras detalhadas
- Fotos pessoais (apenas fotos de problemas de manutenção)

### Retenção de dados:
```yaml
conversations: 90 dias  # Depois são deletadas ou anonimizadas
maintenance_requests: 2 anos
space_bookings: 1 ano
residents: Enquanto morador ativo
```

### Direito ao esquecimento:
```python
async def delete_resident_data(phone: str):
    """Remove todos os dados de um morador (LGPD)."""
    resident = await get_resident_by_phone(phone)
    
    # Anonimizar conversas (não deletar para auditoria)
    supabase.table("conversations") \
        .update({"content": "[dados removidos por solicitação do titular]"}) \
        .eq("resident_id", resident["id"]) \
        .execute()
    
    # Remover dados pessoais do residente
    supabase.table("residents") \
        .update({
            "name": None,
            "whatsapp_phone": f"deleted_{resident['id']}",
            "is_active": False
        }) \
        .eq("id", resident["id"]) \
        .execute()
```

---

## 6. LOGS E AUDITORIA

```python
# Eventos que SEMPRE devem ser logados:
AUDIT_EVENTS = [
    "INJECTION_ATTEMPT",        # Tentativa de prompt injection
    "ESCALATION_SINDICO",       # Mensagem escalada ao síndico
    "DATA_ACCESS_DENIED",       # Tentativa de acessar dados de terceiros
    "EMERGENCY_TRIGGERED",      # Situação de emergência detectada
    "RESIDENT_CREATED",         # Novo morador cadastrado
    "MAINTENANCE_OPENED",       # Chamado aberto
    "MAINTENANCE_CLOSED",       # Chamado fechado
    "BOOKING_CONFIRMED",        # Reserva confirmada
    "BROADCAST_SENT",           # Comunicado enviado
]
```
