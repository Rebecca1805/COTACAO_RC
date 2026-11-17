-- ============================================================================
-- BD-1: Snapshot do Schema Original (Antes das Migrações V2)
-- Data: 2026-11-17
-- ============================================================================

CREATE TABLE public.representantes (
  id uuid NOT NULL,
  nome text NOT NULL,
  email text NOT NULL,
  telefone text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT representantes_pkey PRIMARY KEY (id),
  CONSTRAINT representantes_email_key UNIQUE (email),
  CONSTRAINT representantes_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE public.clientes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  representante_id uuid NOT NULL,
  nome text NOT NULL,
  cnpj text,
  telefone text,
  email text,
  cidade text,
  distancia_km integer,
  coluna_preco text DEFAULT 'Preco100a199km'::text,
  visualiza_preco boolean DEFAULT true,
  senha_hash text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT clientes_pkey PRIMARY KEY (id),
  CONSTRAINT clientes_representante_id_fkey FOREIGN KEY (representante_id) REFERENCES public.representantes(id),
  CONSTRAINT fk_clientes_rep FOREIGN KEY (representante_id) REFERENCES public.representantes(id),
  CONSTRAINT clientes_representante_id_cnpj_key UNIQUE (representante_id, cnpj),
  CONSTRAINT clientes_representante_id_telefone_key UNIQUE (representante_id, telefone)
);

CREATE TABLE public.produtos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  representante_id uuid NOT NULL,
  codigo text NOT NULL,
  produto text NOT NULL,
  unidade text,
  preco_retira numeric,
  preco_100a199km numeric,
  preco_200a299km numeric,
  preco_300a399km numeric,
  preco_acima400km numeric,
  preco_acima500km numeric,
  preco_acima600km numeric,
  created_at timestamp with time zone DEFAULT now(),
  preco_entrega double precision,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT produtos_pkey PRIMARY KEY (id),
  CONSTRAINT produtos_representante_id_fkey FOREIGN KEY (representante_id) REFERENCES public.representantes(id),
  CONSTRAINT fk_representante FOREIGN KEY (representante_id) REFERENCES public.representantes(id),
  CONSTRAINT produtos_representante_id_codigo_key UNIQUE (representante_id, codigo)
);

CREATE TABLE public.cotacoes (
  id text NOT NULL,
  representante_id uuid NOT NULL,
  cliente_id uuid NOT NULL,
  status text DEFAULT 'PENDENTE'::text,
  forma_recebimento text,
  desconto_geral_percentual numeric DEFAULT 0,
  total_original numeric,
  total_final numeric,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT cotacoes_pkey PRIMARY KEY (id),
  CONSTRAINT cotacoes_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id),
  CONSTRAINT cotacoes_representante_id_fkey FOREIGN KEY (representante_id) REFERENCES public.representantes(id),
  CONSTRAINT fk_cotacoes_rep FOREIGN KEY (representante_id) REFERENCES public.representantes(id)
);

CREATE TABLE public.cotacao_itens (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  cotacao_id text NOT NULL,
  produto_id uuid NOT NULL,
  codigo text,
  produto text,
  unidade text,
  quantidade integer NOT NULL,
  preco_unitario numeric NOT NULL,
  desconto_percentual numeric DEFAULT 0,
  subtotal numeric NOT NULL,
  CONSTRAINT cotacao_itens_pkey PRIMARY KEY (id),
  CONSTRAINT cotacao_itens_cotacao_id_fkey FOREIGN KEY (cotacao_id) REFERENCES public.cotacoes(id),
  CONSTRAINT cotacao_itens_produto_id_fkey FOREIGN KEY (produto_id) REFERENCES public.produtos(id)
);
