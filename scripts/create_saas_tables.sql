-- =====================================================
-- SYNDRA SaaS — Tabelas necessárias
-- Execute no SQL Editor do Supabase
-- =====================================================

-- Tabela de Condomínios (tenant raiz)
CREATE TABLE IF NOT EXISTS condos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    cnpj TEXT,
    address TEXT,
    evolution_instance TEXT NOT NULL,  -- Nome da instância no Evolution API
    sindico_name TEXT,
    sindico_phone TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de Configurações por Condomínio
CREATE TABLE IF NOT EXISTS system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condo_id UUID NOT NULL REFERENCES condos(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(condo_id, key)
);

-- Adicionar condo_id ao system_users (se não existir)
ALTER TABLE system_users ADD COLUMN IF NOT EXISTS condo_id UUID REFERENCES condos(id);

-- Índices
CREATE INDEX IF NOT EXISTS idx_system_settings_condo ON system_settings(condo_id);
CREATE INDEX IF NOT EXISTS idx_condos_evolution ON condos(evolution_instance);
CREATE INDEX IF NOT EXISTS idx_system_users_condo ON system_users(condo_id);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_condos_updated_at
    BEFORE UPDATE ON condos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_system_settings_updated_at
    BEFORE UPDATE ON system_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
