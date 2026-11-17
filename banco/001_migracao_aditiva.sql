-- ============================================================================
-- BD-2: Migração 001 (Aditiva e Compatível com o App Atual)
-- Objetivo: Preparar colunas de status, permissões, histórico de itens e limpeza de FKs
-- ============================================================================

BEGIN;

-- 1. Ajustes na tabela CLIENTES
ALTER TABLE public.clientes
  ALTER COLUMN senha_hash DROP NOT NULL,
  ALTER COLUMN coluna_preco SET DEFAULT 'preco_100a199km',
  ALTER COLUMN visualiza_preco SET DEFAULT false;

ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS status_cliente text NOT NULL DEFAULT 'CLIENTE',
  ADD COLUMN IF NOT EXISTS permite_retirada boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS cep text,
  ADD COLUMN IF NOT EXISTS validado_em timestamp with time zone;

-- Normaliza registros antigos que estavam com CamelCase na coluna_preco
UPDATE public.clientes
SET coluna_preco = 'preco_100a199km'
WHERE coluna_preco = 'Preco100a199km';

-- Garante valores válidos para status_cliente (PROSPECT ou CLIENTE)
ALTER TABLE public.clientes
  DROP CONSTRAINT IF EXISTS clientes_status_cliente_check;
ALTER TABLE public.clientes
  ADD CONSTRAINT clientes_status_cliente_check
  CHECK (status_cliente IN ('PROSPECT', 'CLIENTE'));

-- 2. Ajustes na tabela PRODUTOS
ALTER TABLE public.produtos
  ADD COLUMN IF NOT EXISTS ativo boolean NOT NULL DEFAULT true;

ALTER TABLE public.produtos
  ALTER COLUMN preco_entrega TYPE numeric(10,2)
  USING ROUND(preco_entrega::numeric, 2);

-- 3. Ajustes na tabela COTACAO_ITENS (permite excluir produto no futuro preservando histórico)
ALTER TABLE public.cotacao_itens
  ALTER COLUMN produto_id DROP NOT NULL;

ALTER TABLE public.cotacao_itens
  DROP CONSTRAINT IF EXISTS cotacao_itens_produto_id_fkey;
ALTER TABLE public.cotacao_itens
  ADD CONSTRAINT cotacao_itens_produto_id_fkey
  FOREIGN KEY (produto_id) REFERENCES public.produtos(id) ON DELETE SET NULL;

-- 4. Ajustes na tabela COTACOES (restringe status válidos)
UPDATE public.cotacoes
SET status = UPPER(TRIM(status))
WHERE status IS NOT NULL;

ALTER TABLE public.cotacoes
  DROP CONSTRAINT IF EXISTS cotacoes_status_check;
ALTER TABLE public.cotacoes
  ADD CONSTRAINT cotacoes_status_check
  CHECK (status IN ('PENDENTE', 'APROVADA', 'CANCELADA'));

-- 5. Remoção das FKs duplicadas
ALTER TABLE public.clientes DROP CONSTRAINT IF EXISTS fk_clientes_rep;
ALTER TABLE public.cotacoes DROP CONSTRAINT IF EXISTS fk_cotacoes_rep;
ALTER TABLE public.produtos DROP CONSTRAINT IF EXISTS fk_representante;

-- 6. Índices para busca rápida por CNPJ e Telefone
CREATE INDEX IF NOT EXISTS idx_clientes_cnpj ON public.clientes (cnpj);
CREATE INDEX IF NOT EXISTS idx_clientes_telefone ON public.clientes (telefone);

COMMIT;
