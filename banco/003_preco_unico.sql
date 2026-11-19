-- ============================================================================
-- BD-4: Migração 003 (Suporte a Preço Único)
-- Objetivo: Adicionar tipo_preco ('FAIXA' ou 'UNICO') em tabelas_preco
--           e coluna preco_unico em produtos (conforme decisão O4).
-- ============================================================================

BEGIN;

-- 1. Adicionar campo tipo_preco na tabela TABELAS_PRECO
ALTER TABLE public.tabelas_preco
  ADD COLUMN IF NOT EXISTS tipo_preco text NOT NULL DEFAULT 'FAIXA';

ALTER TABLE public.tabelas_preco
  DROP CONSTRAINT IF EXISTS tabelas_preco_tipo_preco_check;

ALTER TABLE public.tabelas_preco
  ADD CONSTRAINT tabelas_preco_tipo_preco_check
  CHECK (tipo_preco IN ('FAIXA', 'UNICO'));

-- 2. Adicionar coluna preco_unico na tabela PRODUTOS
ALTER TABLE public.produtos
  ADD COLUMN IF NOT EXISTS preco_unico numeric(10,2);

COMMIT;