-- =====================================================
-- NORA AGENT — Schema Supabase
-- Residencial Nogueira Martins
-- =====================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────
-- TABELA: residents
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS residents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    whatsapp_phone  VARCHAR(20) UNIQUE NOT NULL,
    name            VARCHAR(100),
    apartment       VARCHAR(10),
    block           VARCHAR(10),
    is_owner        BOOLEAN DEFAULT true,
    profile         JSONB DEFAULT '{"onboarding_complete": false}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- TABELA: system_users (Painel Web e Níveis de Acesso)
CREATE TABLE IF NOT EXISTS system_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'sindico', 'colaborador')),
    name            VARCHAR(100) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────
-- TABELA: conversations
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    resident_id     UUID REFERENCES residents(id) ON DELETE SET NULL,
    whatsapp_phone  TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    intent          TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_phone ON conversations (whatsapp_phone, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations (session_id);

-- ─────────────────────────────────────────────────────
-- TABELA: knowledge_chunks (RAG)
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source      TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('regimento', 'taxa', 'contato', 'calendario', 'faq', 'outro')),
    title       TEXT,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Função de busca semântica
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

-- ─────────────────────────────────────────────────────
-- TABELA: maintenance_requests
-- ─────────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS maintenance_seq START 1;

CREATE TABLE IF NOT EXISTS maintenance_requests (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    protocol    TEXT UNIQUE NOT NULL DEFAULT (
                    'MNT-' || to_char(NOW(), 'YYYY') || '-' || 
                    LPAD(nextval('maintenance_seq')::TEXT, 4, '0')
                ),
    resident_id UUID REFERENCES residents(id),
    type        TEXT NOT NULL CHECK (type IN ('Elétrica', 'Hidráulica', 'Estrutural', 'Equipamento', 'Limpeza', 'Outro')),
    description TEXT NOT NULL,
    location    TEXT NOT NULL,
    urgency     TEXT NOT NULL CHECK (urgency IN ('P1', 'P2', 'P3')),
    status      TEXT DEFAULT 'aberto' CHECK (status IN ('aberto', 'em_andamento', 'concluido', 'cancelado')),
    assigned_to TEXT,
    photos      TEXT[],
    notes       TEXT,
    opened_at   TIMESTAMPTZ DEFAULT NOW(),
    closed_at   TIMESTAMPTZ,
    metadata    JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_requests (status, urgency);
CREATE INDEX IF NOT EXISTS idx_maintenance_resident ON maintenance_requests (resident_id);

-- ─────────────────────────────────────────────────────
-- TABELA: space_bookings
-- ─────────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS booking_seq START 1;

CREATE TABLE IF NOT EXISTS space_bookings (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    booking_ref     TEXT UNIQUE NOT NULL DEFAULT (
                        'RES-' || to_char(NOW(), 'YYYY') || '-' || 
                        LPAD(nextval('booking_seq')::TEXT, 4, '0')
                    ),
    resident_id     UUID REFERENCES residents(id),
    space           TEXT NOT NULL CHECK (space IN ('salao_festas', 'churrasqueira', 'quadra', 'academia', 'outro')),
    booking_date    DATE NOT NULL,
    period          TEXT NOT NULL CHECK (period IN ('manha', 'tarde', 'noite', 'dia_todo')),
    guest_count     INTEGER,
    status          TEXT DEFAULT 'pendente' CHECK (status IN ('pendente', 'confirmado', 'cancelado')),
    payment_amount  NUMERIC(10,2),
    payment_status  TEXT DEFAULT 'aguardando' CHECK (payment_status IN ('aguardando', 'pago', 'reembolsado')),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (space, booking_date, period)
);

-- ─────────────────────────────────────────────────────
-- TABELA: announcements
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS announcements (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    type        TEXT NOT NULL CHECK (type IN ('aviso', 'assembleia', 'emergencia', 'servico', 'manutencao')),
    audience    TEXT DEFAULT 'todos',
    priority    TEXT DEFAULT 'normal' CHECK (priority IN ('baixa', 'normal', 'alta', 'urgente')),
    scheduled_at TIMESTAMPTZ,
    sent_at     TIMESTAMPTZ,
    created_by  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────
-- TABELA: security_events (Auditoria)
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_events (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type  TEXT NOT NULL,
    phone       TEXT,
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────
ALTER TABLE residents ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE space_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;

-- Service role tem acesso total (backend)
CREATE POLICY "service_all" ON residents FOR ALL TO service_role USING (true);
CREATE POLICY "service_all" ON conversations FOR ALL TO service_role USING (true);
CREATE POLICY "service_all" ON maintenance_requests FOR ALL TO service_role USING (true);
CREATE POLICY "service_all" ON space_bookings FOR ALL TO service_role USING (true);
CREATE POLICY "service_all" ON knowledge_chunks FOR ALL TO service_role USING (true);

-- ─────────────────────────────────────────────────────
-- DADOS INICIAIS (Espaços e contatos)
-- ─────────────────────────────────────────────────────
INSERT INTO knowledge_chunks (source, category, title, content, metadata) VALUES
(
    'Sistema Interno',
    'contato',
    'Contatos de Emergência',
    'Portaria 24h: (XX) XXXX-XXXX. Zelador: (XX) 9XXXX-XXXX. Bombeiros: 193. SAMU: 192. Polícia: 190. Manutenção de Elevadores: (XX) XXXX-XXXX.',
    '{"tipo": "contatos_emergencia"}'
),
(
    'Sistema Interno',
    'faq',
    'Horários das Áreas Comuns',
    'Piscina: 8h às 22h (todos os dias). Academia: 6h às 23h. Salão de Festas: 8h às 23h (sexta/sábado até meia-noite). Churrasqueira: 10h às 22h. Silêncio obrigatório: 22h às 8h.',
    '{"tipo": "horarios"}'
);
