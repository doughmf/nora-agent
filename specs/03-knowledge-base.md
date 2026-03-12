# SPEC-03: Knowledge Base — Base de Conhecimento e RAG

**Versão:** 1.0  
**Status:** Aprovado

---

## 1. ARQUITETURA RAG (Retrieval-Augmented Generation)

```
[Morador envia mensagem]
        ↓
[Embedding da query — text-embedding-3-small]
        ↓
[Busca vetorial no Supabase (pgvector)]
        ↓
[Top-K chunks recuperados (K=5)]
        ↓
[Prompt enriquecido com contexto]
        ↓
[LLM (OpenRouter/OpenAI/Gemini) gera resposta fundamentada]
        ↓
[Resposta enviada ao morador]
```

---

## 2. SCHEMA DO SUPABASE

### Tabela: `knowledge_chunks`
```sql
CREATE TABLE knowledge_chunks (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source      TEXT NOT NULL,           -- Ex: "Regimento Interno 2023"
    category    TEXT NOT NULL,           -- regimento | taxa | contato | calendario
    title       TEXT,                   -- Título do trecho
    content     TEXT NOT NULL,          -- Texto do chunk
    embedding   vector(1536),           -- Embedding (OpenAI/Gemini)
    metadata    JSONB DEFAULT '{}',     -- { "artigo": "15", "pagina": 3 }
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para busca vetorial
CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### Tabela: `residents`
```sql
CREATE TABLE residents (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    whatsapp_phone  TEXT UNIQUE NOT NULL,   -- +5511999999999
    name            TEXT,
    apartment       TEXT,                   -- "101-A", "204-B"
    block           TEXT,
    is_owner        BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    profile         JSONB DEFAULT '{}',     -- Preferências, histórico
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabela: `conversations`
```sql
CREATE TABLE conversations (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    resident_id     UUID REFERENCES residents(id),
    whatsapp_phone  TEXT NOT NULL,
    session_id      TEXT NOT NULL,          -- Agrupa mensagens de uma sessão
    role            TEXT NOT NULL,          -- 'user' | 'assistant'
    content         TEXT NOT NULL,
    intent          TEXT,                   -- Intenção classificada
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON conversations (whatsapp_phone, created_at DESC);
CREATE INDEX ON conversations (session_id);
```

### Tabela: `maintenance_requests`
```sql
CREATE TABLE maintenance_requests (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    protocol    TEXT UNIQUE NOT NULL,       -- MNT-2025-0001
    resident_id UUID REFERENCES residents(id),
    type        TEXT NOT NULL,              -- Elétrica | Hidráulica | etc
    description TEXT NOT NULL,
    location    TEXT NOT NULL,
    urgency     TEXT NOT NULL CHECK (urgency IN ('P1', 'P2', 'P3')),
    status      TEXT DEFAULT 'aberto'
                CHECK (status IN ('aberto', 'em_andamento', 'concluido', 'cancelado')),
    assigned_to TEXT,                       -- Nome do técnico/zelador
    photos      TEXT[],                     -- URLs das fotos no Supabase Storage
    notes       TEXT,
    opened_at   TIMESTAMPTZ DEFAULT NOW(),
    closed_at   TIMESTAMPTZ,
    metadata    JSONB DEFAULT '{}'
);
```

### Tabela: `space_bookings`
```sql
CREATE TABLE space_bookings (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    booking_ref     TEXT UNIQUE NOT NULL,   -- RES-2025-0001
    resident_id     UUID REFERENCES residents(id),
    space           TEXT NOT NULL,          -- salao_festas | churrasqueira | quadra
    booking_date    DATE NOT NULL,
    period          TEXT NOT NULL,          -- manha | tarde | noite | dia_todo
    guest_count     INTEGER,
    status          TEXT DEFAULT 'pendente'
                    CHECK (status IN ('pendente', 'confirmado', 'cancelado')),
    payment_amount  NUMERIC(10,2),
    payment_status  TEXT DEFAULT 'aguardando'
                    CHECK (payment_status IN ('aguardando', 'pago', 'reembolsado')),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (space, booking_date, period)    -- Impede double booking
);
```

### Tabela: `announcements`
```sql
CREATE TABLE announcements (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    type        TEXT NOT NULL,              -- aviso | assembleia | emergencia | servico
    audience    TEXT DEFAULT 'todos',       -- todos | bloco_a | proprietarios | etc
    priority    TEXT DEFAULT 'normal'
                CHECK (priority IN ('baixa', 'normal', 'alta', 'urgente')),
    scheduled_at TIMESTAMPTZ,              -- Para envios futuros agendados
    sent_at     TIMESTAMPTZ,
    created_by  TEXT,                      -- Nome do síndico/admin
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3. DOCUMENTOS DA BASE DE CONHECIMENTO

### Documentos Obrigatórios (Para alimentar o RAG)

| Documento | Formato | Prioridade |
|---|---|---|
| Regimento Interno | PDF | P1 — Crítico |
| Convenção do Condomínio | PDF | P1 — Crítico |
| Tabela de Taxas e Multas | PDF/CSV | P1 — Crítico |
| Guia de Uso das Áreas Comuns | PDF | P2 — Alta |
| Contatos de Emergência | CSV | P2 — Alta |
| FAQ de Moradores | Markdown | P2 — Alta |
| Calendário de Eventos | JSON | P3 — Média |
| Manual do Condômino | PDF | P3 — Média |

### Script de Ingestão (seed_knowledge.py)
```python
# scripts/seed_knowledge.py
import openai # Pode usar embeddings da OpenAI ou Gemini
from supabase import create_client
import pdfplumber

def chunk_document(text: str, chunk_size: int = 500) -> list[str]:
    """Divide documento em chunks com overlap."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - 50):  # 50 words overlap
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def embed_text(text: str) -> list[float]:
    """Gera embedding via OpenAI ou Gemini."""
    # Use text-embedding-3-small da OpenAI ou text-embedding-004 do Gemini
    pass

def ingest_pdf(filepath: str, category: str, source_name: str):
    """Ingere PDF completo na base de conhecimento."""
    with pdfplumber.open(filepath) as pdf:
        full_text = "\n".join(p.extract_text() for p in pdf.pages)
    
    chunks = chunk_document(full_text)
    
    for chunk in chunks:
        embedding = embed_text(chunk)
        supabase.table("knowledge_chunks").insert({
            "source": source_name,
            "category": category,
            "content": chunk,
            "embedding": embedding
        }).execute()
    
    print(f"✅ Ingested: {source_name} ({len(chunks)} chunks)")
```

---

## 4. FUNÇÃO DE BUSCA VETORIAL

```sql
-- Função Supabase para busca semântica
CREATE OR REPLACE FUNCTION search_knowledge(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.75,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id uuid,
    source text,
    category text,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE SQL STABLE AS $$
    SELECT
        id, source, category, content, metadata,
        1 - (embedding <=> query_embedding) AS similarity
    FROM knowledge_chunks
    WHERE 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```
