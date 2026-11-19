-- ============================================================================
-- BD-3: Migração 002 (Empresas, Vínculos e Tabelas de Preço)
-- Objetivo: Criar estrutura multiempresa e vincular os dados de teste existentes
--           sem apagar colunas antigas (migração aditiva).
-- ============================================================================

BEGIN;

-- 1. Criar tabela EMPRESAS (fornecedores atendidos)
CREATE TABLE IF NOT EXISTS public.empresas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nome text NOT NULL,
  cnpj text,
  cep_origem text,
  cidade_origem text,
  ativo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT empresas_pkey PRIMARY KEY (id)
);

-- 2. Criar tabela REPRESENTANTE_EMPRESAS (vínculo N:N entre representante e empresa)
CREATE TABLE IF NOT EXISTS public.representante_empresas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  representante_id uuid NOT NULL,
  empresa_id uuid NOT NULL,
  ativo boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT representante_empresas_pkey PRIMARY KEY (id),
  CONSTRAINT representante_empresas_rep_fkey FOREIGN KEY (representante_id) REFERENCES public.representantes(id) ON DELETE CASCADE,
  CONSTRAINT representante_empresas_emp_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE,
  CONSTRAINT representante_empresas_unq UNIQUE (representante_id, empresa_id)
);

-- 3. Criar tabela TABELAS_PRECO (1 ou mais tabelas por empresa)
CREATE TABLE IF NOT EXISTS public.tabelas_preco (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL,
  nome text NOT NULL,
  ativa boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT tabelas_preco_pkey PRIMARY KEY (id),
  CONSTRAINT tabelas_preco_empresa_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id) ON DELETE CASCADE
);

-- 4. Adicionar colunas novas em PRODUTOS e COTACOES (sem apagar as antigas)
ALTER TABLE public.produtos
  ADD COLUMN IF NOT EXISTS empresa_id uuid,
  ADD COLUMN IF NOT EXISTS tabela_preco_id uuid;

ALTER TABLE public.produtos
  DROP CONSTRAINT IF EXISTS produtos_empresa_id_fkey,
  DROP CONSTRAINT IF EXISTS produtos_tabela_preco_id_fkey;

ALTER TABLE public.produtos
  ADD CONSTRAINT produtos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id),
  ADD CONSTRAINT produtos_tabela_preco_id_fkey FOREIGN KEY (tabela_preco_id) REFERENCES public.tabelas_preco(id);

ALTER TABLE public.cotacoes
  ADD COLUMN IF NOT EXISTS empresa_id uuid,
  ADD COLUMN IF NOT EXISTS tabela_preco_id uuid;

ALTER TABLE public.cotacoes
  DROP CONSTRAINT IF EXISTS cotacoes_empresa_id_fkey,
  DROP CONSTRAINT IF EXISTS cotacoes_tabela_preco_id_fkey;

ALTER TABLE public.cotacoes
  ADD CONSTRAINT cotacoes_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES public.empresas(id),
  ADD CONSTRAINT cotacoes_tabela_preco_id_fkey FOREIGN KEY (tabela_preco_id) REFERENCES public.tabelas_preco(id);

-- 5. Criar Empresa Inicial + Tabela Padrão e vincular todos os dados existentes
DO $$
DECLARE
  v_empresa_id uuid;
  v_tabela_id uuid;
BEGIN
  -- Cria a empresa padrão para os dados atuais se ainda não existir
  SELECT id INTO v_empresa_id
  FROM public.empresas
  WHERE nome = 'Empresa Padrão (Teste)'
  LIMIT 1;

  IF v_empresa_id IS NULL THEN
    INSERT INTO public.empresas (nome, ativo)
    VALUES ('Empresa Padrão (Teste)', true)
    RETURNING id INTO v_empresa_id;
  END IF;

  -- Vincula todos os representantes atuais à empresa padrão
  INSERT INTO public.representante_empresas (representante_id, empresa_id, ativo)
  SELECT id, v_empresa_id, true
  FROM public.representantes
  ON CONFLICT (representante_id, empresa_id) DO NOTHING;

  -- Cria a tabela de preços padrão para essa empresa se ainda não existir
  SELECT id INTO v_tabela_id
  FROM public.tabelas_preco
  WHERE empresa_id = v_empresa_id AND nome = 'Tabela Padrão'
  LIMIT 1;

  IF v_tabela_id IS NULL THEN
    INSERT INTO public.tabelas_preco (empresa_id, nome, ativa)
    VALUES (v_empresa_id, 'Tabela Padrão', true)
    RETURNING id INTO v_tabela_id;
  END IF;

  -- Liga todos os produtos existentes à empresa e tabela padrão
  UPDATE public.produtos
  SET empresa_id = v_empresa_id,
      tabela_preco_id = v_tabela_id
  WHERE tabela_preco_id IS NULL;

  -- Liga todas as cotações existentes à empresa e tabela padrão
  UPDATE public.cotacoes
  SET empresa_id = v_empresa_id,
      tabela_preco_id = v_tabela_id
  WHERE tabela_preco_id IS NULL;
END $$;

-- 6. Índices para melhorar performance das consultas multiempresa
CREATE INDEX IF NOT EXISTS idx_produtos_tabela_preco_id ON public.produtos (tabela_preco_id);
CREATE INDEX IF NOT EXISTS idx_produtos_empresa_id ON public.produtos (empresa_id);
CREATE INDEX IF NOT EXISTS idx_cotacoes_empresa_id ON public.cotacoes (empresa_id);
CREATE INDEX IF NOT EXISTS idx_rep_empresas_rep_id ON public.representante_empresas (representante_id);

COMMIT;