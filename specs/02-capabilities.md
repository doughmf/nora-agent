# SPEC-02: Capabilities — Capacidades e Escopo de Atuação

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. MAPA DE CAPACIDADES

```
SYNDRA AGENT
├── PILAR 1: Atendimento ao Morador
│   ├── Responder dúvidas sobre regimento interno
│   ├── Informar horários de silêncio, piscina, academia
│   ├── Explicar regras de uso das áreas comuns
│   ├── Informar contatos de emergência
│   └── Consultar histórico de interações do morador
│
├── PILAR 2: Gestão de Manutenção
│   ├── Abrir chamado de reparo com protocolo
│   ├── Triagem de urgência (P1/P2/P3)
│   ├── Consultar status de chamado aberto
│   ├── Notificar zelador/prestador via webhook
│   └── Fechar chamado com confirmação do morador
│
├── PILAR 3: Reservas e Agendamentos
│   ├── Consultar disponibilidade de espaços
│   ├── Pré-reservar com pendência de confirmação
│   ├── Confirmar reserva após pagamento
│   ├── Cancelar reserva com antecedência mínima
│   └── Enviar lembrete automático 24h antes
│
└── PILAR 4: Comunicação e Avisos
    ├── Receber e distribuir comunicados da administração
    ├── Notificar sobre assembleias e votações
    ├── Avisar sobre interrupções de serviços
    ├── Enviar boletos e informações financeiras
    └── Broadcast para grupos específicos (por bloco/andar)
```

---

## 2. FERRAMENTAS DISPONÍVEIS (Tools/Functions)

### Tool: `buscar_regimento`
```python
"""
Consulta o regimento interno e convenção do condomínio via RAG.
Retorna o trecho relevante e o número do artigo.

Args:
    query (str): Pergunta do morador em linguagem natural

Returns:
    dict: {
        "artigo": "Art. 15",
        "texto": "...",
        "fonte": "Regimento Interno 2023"
    }
"""
```

### Tool: `abrir_chamado_manutencao`
```python
"""
Cria um chamado de manutenção no Supabase.

Args:
    tipo (str): Elétrica | Hidráulica | Estrutural | Equipamento | Limpeza
    descricao (str): Descrição detalhada do problema
    localizacao (str): Local exato (Ex: "Corredor B2, luminária 3")
    urgencia (str): P1 (imediato) | P2 (24h) | P3 (agendado)
    morador_id (str): UUID do morador

Returns:
    dict: { "protocolo": "MNT-2025-0047", "prazo_estimado": "24h" }
"""
```

### Tool: `verificar_disponibilidade_espaco`
```python
"""
Consulta calendário de reservas no Supabase.

Args:
    espaco (str): salao_festas | churrasqueira | quadra | academia
    data (str): YYYY-MM-DD
    periodo (str): manha | tarde | noite | dia_todo

Returns:
    dict: { "disponivel": True/False, "horarios_livres": [...] }
"""
```

### Tool: `criar_reserva`
```python
"""
Cria pré-reserva pendente de pagamento.

Args:
    espaco (str): Nome do espaço
    data (str): YYYY-MM-DD
    periodo (str): Período desejado
    morador_id (str): UUID do morador
    num_convidados (int): Estimativa de pessoas

Returns:
    dict: { "reserva_id": "RES-2025-0012", "valor": 150.00, "pix": "..." }
"""
```

### Tool: `buscar_contato_emergencia`
```python
"""
Retorna contatos de emergência por categoria.

Args:
    categoria (str): zelador | portaria | elevador | gas | bombeiro | policia

Returns:
    dict: { "nome": str, "telefone": str, "disponibilidade": str }
"""
```

### Tool: `registrar_ocorrencia`
```python
"""
Registra ocorrência formal (barulho, vandalismo, etc).

Args:
    tipo (str): Tipo da ocorrência
    descricao (str): Relato detalhado
    local (str): Local do ocorrido
    data_hora (str): ISO 8601
    morador_id (str): UUID do morador

Returns:
    dict: { "ocorrencia_id": str, "status": "registrada" }
"""
```

### Tool: `notificar_sindico`
```python
"""
Envia notificação urgente ao síndico via WhatsApp.

Args:
    assunto (str): Resumo do problema
    nivel (str): URGENTE | IMPORTANTE | INFORMATIVO
    morador_id (str): UUID do morador solicitante
    detalhes (str): Contexto completo

Returns:
    dict: { "enviado": True, "timestamp": str }
"""
```

---

## 3. CLASSIFICAÇÃO DE INTENÇÕES (Intent Classification)

```python
INTENTS = {
    # Informação
    "INFO_REGIMENTO":   ["regimento", "regra", "permitido", "pode", "proibido"],
    "INFO_TAXA":        ["taxa", "boleto", "condomínio", "valor", "mensalidade"],
    "INFO_HORARIO":     ["horário", "funcionamento", "abre", "fecha", "silêncio"],
    "INFO_CONTATO":     ["telefone", "contato", "número", "zelador", "porteiro"],

    # Ações
    "MANUTENCAO_ABRIR": ["conserto", "quebrado", "vazamento", "não funciona", "reparo"],
    "MANUTENCAO_STATUS":["protocolo", "chamado", "status", "meu reparo"],
    "RESERVA_CONSULTA": ["disponível", "livre", "reservar", "agendar"],
    "RESERVA_CRIAR":    ["quero reservar", "reserva para", "marcar salão"],
    "RESERVA_CANCELAR": ["cancelar reserva", "desmarcar", "não vou mais"],

    # Escalação
    "ESCALAR_URGENTE":  ["incêndio", "inundação", "arrombamento", "acidente"],
    "ESCALAR_CONFLITO": ["briga", "ameaça", "processo", "advogado"],

    # Social
    "SAUDACAO":         ["oi", "olá", "bom dia", "boa tarde", "boa noite"],
    "AGRADECIMENTO":    ["obrigado", "valeu", "obrigada", "agradeço"],
    "DESPEDIDA":        ["tchau", "até logo", "bye", "até mais"]
}
```

---

## 4. LIMITES DE ESCOPO (Fora do escopo)

A Syndra NÃO deve:
- Dar conselhos jurídicos sobre disputas entre condôminos
- Aprovar ou negar pedidos de isenção de taxa
- Interferir em decisões de assembleia
- Fazer cobranças de inadimplentes (encaminhar para administradora)
- Revelar quem abriu chamados ou reclamações
- Responder sobre assuntos externos ao condomínio
