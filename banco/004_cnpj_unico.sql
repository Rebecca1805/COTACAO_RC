-- ============================================================================
-- BD-5: Migração 004 (CNPJ Único Global entre Representantes)
-- Objetivo: Impedir que o mesmo CNPJ seja cadastrado em mais de um representante,
--           permitindo múltiplos registros apenas quando o CNPJ estiver vazio/nulo.
-- ============================================================================

BEGIN;

-- 1. Limpa espaços em branco e transforma strings vazias de CNPJ em NULL
UPDATE public.clientes
SET cnpj = NULLIF(TRIM(cnpj), '');

-- 2. Remove a restrição antiga (que só impedia CNPJ repetido dentro do MESMO representante)
ALTER TABLE public.clientes
  DROP CONSTRAINT IF EXISTS clientes_representante_id_cnpj_key;

-- 3. Cria índice único global apenas para CNPJs preenchidos (ignora NULL)
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_cnpj_unico_global
  ON public.clientes (cnpj)
  WHERE cnpj IS NOT NULL;

COMMIT;
