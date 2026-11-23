-- SEG-12: Marca de troca obrigatória de senha no primeiro acesso do representante
ALTER TABLE public.representantes
ADD COLUMN IF NOT EXISTS trocar_senha BOOLEAN NOT NULL DEFAULT FALSE;