-- ============================================================================
-- SEG-4: Tabela de controle de tentativas de login e bloqueio temporário
-- Objetivo: Registrar tentativas falhas por identificador e tipo de usuário,
--           aplicando bloqueio temporário após atingir o limite.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.tentativas_login (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identificador text NOT NULL,
    tipo_usuario text NOT NULL,
    tentativas integer NOT NULL DEFAULT 0,
    bloqueado_ate timestamptz NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tentativas_login_identificador_tipo_key UNIQUE (identificador, tipo_usuario)
);

-- Ativa RLS sem políticas públicas (segue o padrão do SEG-0)
ALTER TABLE public.tentativas_login ENABLE ROW LEVEL SECURITY;

COMMIT;