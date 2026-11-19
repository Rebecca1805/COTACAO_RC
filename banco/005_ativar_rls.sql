-- ============================================================================
-- SEG-0: Ativar RLS (Row Level Security) em todas as tabelas sem políticas
-- Objetivo: Bloquear qualquer acesso direto via chave pública (anon).
--           O backend Python usa service_role e continua operando normalmente.
-- ============================================================================

BEGIN;

ALTER TABLE public.representantes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.produtos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cotacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cotacao_itens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.representante_empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tabelas_preco ENABLE ROW LEVEL SECURITY;

COMMIT;