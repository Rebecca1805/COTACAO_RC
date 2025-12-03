# 📦 Portal de Cotações e Pedidos

Um sistema web interativo para cotação e pedidos de produtos, construído com Streamlit e Supabase.

## Funcionalidades

- ✅ Autenticação por telefone
- ✅ Preços personalizados por cliente
- ✅ Seleção dinâmica de produtos
- ✅ Cálculo automático de pedidos
- ✅ Integração com Supabase

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/SEU_USUARIO/COTA-app.git
cd COTA-app
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# ou
source venv/bin/activate  # Linux/Mac
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas credenciais do Supabase
```

5. Execute a aplicação:
```bash
streamlit run App.py
```

A aplicação estará disponível em `http://localhost:8501`

## Configuração do Supabase

Você precisa ter as seguintes tabelas no Supabase:
- `clientes` (telefone, nome, cidade, id_regra_preferencial)
- `regras_preco` (id, coluna_no_banco)
- `produtos` (codigo_produto, descricao, unidade, preço_*)

## Variáveis de Ambiente

Crie um arquivo `.env` com:
```
SUPABASE_URL=sua_url_aqui
SUPABASE_KEY=sua_chave_aqui
```

## Licença

MIT

## Autor

Rebecca
