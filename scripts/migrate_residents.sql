-- =====================================================
-- SYNDRA — Migração: campos extras em residents
-- Execute no SQL Editor do Supabase
-- =====================================================

ALTER TABLE residents
  ADD COLUMN IF NOT EXISTS cpf          VARCHAR(14),
  ADD COLUMN IF NOT EXISTS email        VARCHAR(120),
  ADD COLUMN IF NOT EXISTS active       BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS vehicles     TEXT[],        -- ['ABC-1234', 'XYZ-5678']
  ADD COLUMN IF NOT EXISTS dependents   JSONB DEFAULT '[]'; -- [{"name":"Ana","relation":"filha"}]

-- Índices úteis para filtros
CREATE INDEX IF NOT EXISTS idx_residents_condo_block   ON residents (condo_id, block);
CREATE INDEX IF NOT EXISTS idx_residents_condo_active  ON residents (condo_id, active);
CREATE INDEX IF NOT EXISTS idx_residents_phone         ON residents (condo_id, whatsapp_phone);
