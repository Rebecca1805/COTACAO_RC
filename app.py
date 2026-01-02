import os
from datetime import datetime
import pandas as pd
import streamlit as st
import re
from fpdf import FPDF
import bcrypt
import csv
import secrets
import string
import shutil
from unidecode import unidecode

# ========================= 
# CONFIGURAÇÕES INICIAIS
# ========================= 
BASE_DIR = "data"
AUTH_DIR = "auth"
AUTH_CLIENTES_PATH = os.path.join(AUTH_DIR, "usuarios_clientes.csv")
AUTH_REPRESENTANTES_PATH = os.path.join(AUTH_DIR, "usuarios_representantes.csv")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(AUTH_DIR, exist_ok=True)

# ========================= 
# FUNÇÕES AUXILIARES DE CAMINHO
# ========================= 
def get_representante_dir(username_rep):
    """Retorna o diretório específico do representante"""
    return os.path.join(BASE_DIR, f"rep_{username_rep}")

def get_clientes_path(username_rep):
    """Retorna caminho do arquivo de clientes do representante"""
    return os.path.join(get_representante_dir(username_rep), "clientes.xlsx")

def get_tabela_path(username_rep):
    """Retorna caminho da tabela de preços do representante"""
    return os.path.join(get_representante_dir(username_rep), "tabela_precos.csv")

def get_cotacoes_path(username_rep):
    """Retorna caminho do arquivo de cotações do representante"""
    return os.path.join(get_representante_dir(username_rep), "cotacoes.csv")

def get_itens_cotacao_path(username_rep):
    """Retorna caminho do arquivo de itens de cotação do representante"""
    return os.path.join(get_representante_dir(username_rep), "itens_cotacao.csv")

def inicializar_estrutura_representante(username_rep):
    """Cria a estrutura de pastas e arquivos para um novo representante"""
    rep_dir = get_representante_dir(username_rep)
    os.makedirs(rep_dir, exist_ok=True)

    # Cria arquivo de clientes vazio se não existir
    clientes_path = get_clientes_path(username_rep)
    if not os.path.exists(clientes_path):
        df_clientes = pd.DataFrame(columns=[
            "NOME", "CNPJ", "TELEFONE", "CIDADE", "DISTANCIA", 
            "COLUNA_PRECO", "VISUALIZA_PRECO"
        ])
        df_clientes.to_excel(clientes_path, index=False)

    # Cria arquivo de cotações vazio se não existir
    cotacoes_path = get_cotacoes_path(username_rep)
    if not os.path.exists(cotacoes_path):
        df_cotacoes = pd.DataFrame(columns=[
            "id", "cliente_nome", "cliente_telefone", "representante",
            "status", "data", "forma_recebimento", "total_original",
            "desconto_percentual", "total"
        ])
        df_cotacoes.to_csv(cotacoes_path, index=False)

    # Cria arquivo de itens de cotação vazio se não existir
    itens_path = get_itens_cotacao_path(username_rep)
    if not os.path.exists(itens_path):
        df_itens = pd.DataFrame(columns=[
            "id_cotacao", "codigo", "produto", "unidade", "quantidade",
            "preco_retira", "preco_final", "subtotal_retira", "subtotal_final"
        ])
        df_itens.to_csv(itens_path, index=False)

# ========================= 
# ESTILO LOCAL
# ========================= 
def local_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gilroy:wght@400;600;700&family=Thasadith:wght@400;700&display=swap');
    
    * {
        font-family: 'Gilroy', sans-serif;
    }
    
    .main-header {
        text-align: center;
        color: #0b245c;
        padding: 20px;
        font-size: 2.5em;
        font-weight: 700;
        font-family: 'Gilroy', sans-serif;
    }
    
    .login-box {
        background-color: #f8f9fa;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #3d2fa6;
    }
    
    .stButton>button {
        background-color: #f54f2b;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 10px 20px;
        font-weight: 600;
        font-family: 'Gilroy', sans-serif;
    }
    
    .stButton>button:hover {
        background-color: #0b245c;
        color: white;
    }
    
    .stTextInput>div>div>input, .stTextArea>div>textarea, .stSelectbox>div>div>select {
        border: 2px solid #3d2fa6;
        border-radius: 5px;
        font-family: 'Thasadith', serif;
    }
    
    .stSidebar {
        background-color: #0b245c;
        color: white;
    }
    
    .stSidebar .stRadio label, .stSidebar .stSelectbox label, .stSidebar .stButton button, .stSidebar h1, .stSidebar h2, .stSidebar p {
        color: white !important;
        font-family: 'Gilroy', sans-serif;
    }
    
    .stSidebar .stRadio div[role="radiogroup"] label, .stSidebar .stSelectbox div label {
        color: white !important;
    }
    
    .stMetric {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stMetric .metric-value {
        color: #f54f2b;
        font-weight: 700;
        font-family: 'Gilroy', sans-serif;
    }
    
    .stMetric .metric-label {
        color: #3d2fa6;
        font-family: 'Thasadith', serif;
    }
    
    .stExpander {
        border: 1px solid #3d2fa6;
        border-radius: 5px;
    }
    
    .stExpander .stExpanderHeader {
        background-color: #f8f9fa;
        color: #0b245c;
        font-weight: 600;
        font-family: 'Gilroy', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #0b245c;
        font-family: 'Gilroy', sans-serif;
    }
    
    .stSuccess, .stInfo, .stWarning, .stError {
        border-radius: 5px;
        font-family: 'Thasadith', serif;
    }
    
    .stSuccess {
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
    }
    
    .stInfo {
        background-color: #d1ecf1;
        border-color: #bee5eb;
        color: #0c5460;
    }
    
    .stWarning {
        background-color: #fff3cd;
        border-color: #ffeaa7;
        color: #856404;
    }
    
    .stError {
        background-color: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
    }
    </style>
    """, unsafe_allow_html=True)

# ========================= 
# FUNÇÕES DE AUTENTICAÇÃO
# ========================= 
def init_auth_files():
    """Cria arquivos de autenticação se não existirem"""
    if not os.path.exists(AUTH_CLIENTES_PATH):
        with open(AUTH_CLIENTES_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'nome', 'senha_hash', 'cnpj', 'telefone', 'representante_id'])

    if not os.path.exists(AUTH_REPRESENTANTES_PATH):
        with open(AUTH_REPRESENTANTES_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'nome', 'senha_hash', 'email'])

def hash_senha(senha):
    """Gera hash da senha"""
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha, senha_hash):
    """Verifica se a senha está correta"""
    try:
        return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))
    except (ValueError, AttributeError) as e:
        st.error(f"Erro ao verificar senha: {e}")
        return False

def load_usuarios_clientes():
    """Carrega usuários clientes do CSV"""
    if not os.path.exists(AUTH_CLIENTES_PATH):
        init_auth_files()
        return pd.DataFrame(columns=['username', 'nome', 'senha_hash', 'cnpj', 'telefone', 'representante_id'])

    df = pd.read_csv(AUTH_CLIENTES_PATH, dtype=str)
    rename_map = {
        "usuario": "username",
        "usuário": "username",
    }
    df = df.rename(columns={c: rename_map.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns})

    for col in ['username', 'nome', 'senha_hash', 'cnpj', 'telefone', 'representante_id']:
        if col not in df.columns:
            df[col] = ""

    return df[['username', 'nome', 'senha_hash', 'cnpj', 'telefone', 'representante_id']]

def load_usuarios_representantes():
    """Carrega usuários representantes do CSV"""
    if not os.path.exists(AUTH_REPRESENTANTES_PATH):
        init_auth_files()
        return pd.DataFrame(columns=['username', 'nome', 'senha_hash', 'email'])

    df = pd.read_csv(AUTH_REPRESENTANTES_PATH, dtype=str)
    rename_map = {
        "usuario": "username",
        "usuário": "username",
    }
    df = df.rename(columns={c: rename_map.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns})

    for col in ['username', 'nome', 'senha_hash', 'email']:
        if col not in df.columns:
            df[col] = ""

    return df[['username', 'nome', 'senha_hash', 'email']]

def salvar_usuario_cliente(username, nome, senha, cnpj, telefone, representante_id):
    """Adiciona novo usuário cliente"""
    usuarios = load_usuarios_clientes()
    if username in usuarios['username'].values:
        return False, "Username já cadastrado"

    novo_usuario = {
        'username': username,
        'nome': nome,
        'senha_hash': hash_senha(senha),
        'cnpj': cnpj,
        'telefone': telefone,
        'representante_id': representante_id
    }
    usuarios = pd.concat([usuarios, pd.DataFrame([novo_usuario])], ignore_index=True)
    usuarios.to_csv(AUTH_CLIENTES_PATH, index=False)
    return True, "Cliente cadastrado com sucesso!"

def autenticar_cliente(username, senha):
    """Autentica cliente e retorna seus dados"""
    usuarios = load_usuarios_clientes()
    usuario = usuarios[usuarios['username'] == username]

    if usuario.empty:
        return None, "Usuário não encontrado"

    usuario = usuario.iloc[0]
    if verificar_senha(senha, usuario['senha_hash']):
        return usuario, "Login realizado com sucesso"

    return None, "Senha incorreta"

def salvar_usuario_representante(username, nome, senha, email):
    """Adiciona novo usuário representante"""
    usuarios = load_usuarios_representantes()
    if username in usuarios['username'].values:
        return False, "Username já cadastrado"

    novo_usuario = {
        'username': username,
        'nome': nome,
        'senha_hash': hash_senha(senha),
        'email': email
    }
    usuarios = pd.concat([usuarios, pd.DataFrame([novo_usuario])], ignore_index=True)
    usuarios.to_csv(AUTH_REPRESENTANTES_PATH, index=False)

    # Inicializa estrutura de pastas para o novo representante
    inicializar_estrutura_representante(username)

    return True, "Representante cadastrado!"

def autenticar_representante(username, senha):
    """Autentica representante"""
    usuarios = load_usuarios_representantes()
    usuario = usuarios[usuarios['username'] == username]

    if usuario.empty:
        return None, "Usuário não encontrado"

    usuario = usuario.iloc[0]
    if verificar_senha(senha, usuario['senha_hash']):
        return usuario, "Login realizado"

    return None, "Senha incorreta"

def resetar_senha_cliente(username):
    """Reseta senha do cliente e gera senha temporária"""
    usuarios = load_usuarios_clientes()
    if username not in usuarios['username'].values:
        return False, None, "Usuário não encontrado"

    caracteres = string.ascii_letters + string.digits
    senha_temp = ''.join(secrets.choice(caracteres) for _ in range(8))

    usuarios.loc[usuarios['username'] == username, 'senha_hash'] = hash_senha(senha_temp)
    usuarios.to_csv(AUTH_CLIENTES_PATH, index=False)

    return True, senha_temp, "Senha resetada com sucesso!"

# ========================= 
# FUNÇÕES DE CARGA DE DADOS
# ========================= 
def load_clientes(username_rep):
    """Lê a planilha de clientes do representante"""
    clientes_path = get_clientes_path(username_rep)

    if not os.path.exists(clientes_path):
        inicializar_estrutura_representante(username_rep)

    df = pd.read_excel(clientes_path)
    df = df[df["NOME"].notna()].copy()
    df.columns = [str(c).strip().upper() for c in df.columns]

    if "CNPJ" in df.columns:
        df["CNPJ"] = df["CNPJ"].fillna("").astype(str)
        df["CNPJ"] = df["CNPJ"].apply(lambda x: x.split('.')[0] if '.' in x else x)

    if "TELEFONE" in df.columns:
        df["TELEFONE"] = df["TELEFONE"].fillna("").astype(str)
        df["TELEFONE"] = df["TELEFONE"].apply(lambda x: x.split('.')[0] if '.' in x else x)

    def _map_preco_from_dist(row):
        if "DISTANCIA" in row and pd.notna(row["DISTANCIA"]):
            s = str(row["DISTANCIA"]).strip()
            if s.lower().startswith("preco"):
                return s.replace(" ", "")
            digits = re.sub(r"\D", "", s)
            if digits:
                try:
                    d = int(digits)
                except ValueError:
                    return str(row.get("COLUNA_PRECO", "Preco100a199km")).replace(" ", "")
                if d <= 199:
                    return "Preco100a199km"
                if d <= 299:
                    return "Preco200a299km"
                if d <= 399:
                    return "Preco300a399km"
                if d <= 499:
                    return "PrecoAcima400km"
                if d <= 599:
                    return "PrecoAcima500km"
                return "PrecoAcima600km"
        return str(row.get("COLUNA_PRECO", "Preco100a199km")).replace(" ", "")

    if "DISTANCIA" in df.columns:
        df["COLUNA_PRECO"] = df.apply(_map_preco_from_dist, axis=1)
    else:
        df["COLUNA_PRECO"] = "Preco100a199km"

    if "VISUALIZA_PRECO" not in df.columns:
        df["VISUALIZA_PRECO"] = True
    else:
        def _parse_bool(v):
            s = str(v).strip().lower()
            if s in ("1", "true", "sim", "yes", "y"):
                return True
            return False
        df["VISUALIZA_PRECO"] = df["VISUALIZA_PRECO"].apply(_parse_bool)

    return df

def salvar_clientes_df(df, username_rep):
    """Salva o DataFrame de clientes do representante"""
    df_to_save = df.copy()
    df_to_save.columns = [str(c).upper() for c in df_to_save.columns]

    if "VISUALIZA_PRECO" in df_to_save.columns:
        df_to_save["VISUALIZA_PRECO"] = df_to_save["VISUALIZA_PRECO"].apply(
            lambda v: "sim" if bool(v) else "0"
        )

    clientes_path = get_clientes_path(username_rep)
    df_to_save.to_excel(clientes_path, index=False)
    st.success("Clientes atualizados com sucesso!")

def load_tabela_geral(username_rep):
    """Lê a tabela geral de produtos do representante"""
    tabela_path = get_tabela_path(username_rep)

    if not os.path.exists(tabela_path):
        return pd.DataFrame()

    df = pd.read_csv(tabela_path, sep=",", encoding="utf-8", dtype=str)
    df.columns = [str(c).strip().replace(" ", "") for c in df.columns]
    return df

def parse_preco(valor):
    """Converte string tipo '18,14' em float 18.14"""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    if not s:
        return None
    try:
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except (ValueError, AttributeError):
        return None

def get_preco_entrega(cliente_row, produto_row):
    """Preço com frete, usando a coluna da faixa do cliente"""
    if "COLUNA_PRECO" in cliente_row.index:
        coluna_preco = str(cliente_row["COLUNA_PRECO"]).replace(" ", "")
    elif "coluna_preco" in cliente_row.index:
        coluna_preco = str(cliente_row["coluna_preco"]).replace(" ", "")
    else:
        return None

    if coluna_preco not in produto_row.index:
        return None

    return parse_preco(produto_row[coluna_preco])

def get_preco_retira(produto_row):
    """Preço para retirada (coluna 'Retira')"""
    if "Retira" not in produto_row.index:
        return None
    return parse_preco(produto_row["Retira"])

def so_digitos(valor):
    """Remove tudo que não for número"""
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))

def cliente_pode_ver_preco(cliente_row):
    """Retorna True/False se o cliente pode visualizar os preços"""
    try:
        return bool(cliente_row.get("VISUALIZA_PRECO", True))
    except Exception:
        return True

# ========================= 
# FUNÇÕES DE ARMAZENAMENTO
# ========================= 
def load_cotacoes(username_rep):
    """Carrega cotações do representante"""
    cotacoes_path = get_cotacoes_path(username_rep)

    if not os.path.exists(cotacoes_path):
        return pd.DataFrame(columns=[
            "id", "cliente_nome", "cliente_telefone", "representante", "status",
            "data", "forma_recebimento", "total_original", "desconto_percentual", "total"
        ])

    df = pd.read_csv(cotacoes_path)
    if "total_original" not in df.columns:
        df["total_original"] = df["total"]
    if "desconto_percentual" not in df.columns:
        df["desconto_percentual"] = 0.0

    return df

def load_itens_cotacao(username_rep):
    """Carrega itens das cotações do representante"""
    itens_path = get_itens_cotacao_path(username_rep)

    if not os.path.exists(itens_path):
        return pd.DataFrame(columns=[
            "id_cotacao", "codigo", "produto", "unidade", "quantidade",
            "preco_retira", "preco_final", "subtotal_retira", "subtotal_final"
        ])

    return pd.read_csv(itens_path)

def gerar_id_cotacao(cliente_nome):
    """Gera ID da cotação"""
    cliente_prefix = re.sub(r"\W", "", cliente_nome.upper())[:4].ljust(4, "X")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{cliente_prefix}{timestamp}"

def salvar_cotacao(cliente_row, itens, forma_recebimento, username_rep):
    """Salva cotação e itens"""
    if not itens:
        st.error("Nenhum item na cotação.")
        return None

    cotacoes = load_cotacoes(username_rep)
    itens_cot = load_itens_cotacao(username_rep)

    id_cotacao = gerar_id_cotacao(cliente_row["NOME"])
    total_final = sum(item["subtotal_final"] for item in itens)

    nova_cot = {
        "id": id_cotacao,
        "cliente_nome": cliente_row["NOME"],
        "cliente_telefone": cliente_row.get("TELEFONE", ""),
        "representante": username_rep,
        "status": "PENDENTE",
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "forma_recebimento": forma_recebimento,
        "total_original": total_final,
        "desconto_percentual": 0.0,
        "total": total_final,
    }
    cotacoes = pd.concat([cotacoes, pd.DataFrame([nova_cot])], ignore_index=True)

    novos_itens = []
    for item in itens:
        novos_itens.append({
            "id_cotacao": id_cotacao,
            "codigo": item["codigo"],
            "produto": item["produto"],
            "unidade": item["unidade"],
            "quantidade": item["quantidade"],
            "preco_retira": item["preco_retira"],
            "preco_final": item["preco_final"],
            "subtotal_retira": item["subtotal_retira"],
            "subtotal_final": item["subtotal_final"],
        })
    itens_cot = pd.concat([itens_cot, pd.DataFrame(novos_itens)], ignore_index=True)

    cotacoes.to_csv(get_cotacoes_path(username_rep), index=False)
    itens_cot.to_csv(get_itens_cotacao_path(username_rep), index=False)

    return id_cotacao

def atualizar_status_cotacao(id_cotacao, novo_status, username_rep):
    """Atualiza status da cotação"""
    cotacoes = load_cotacoes(username_rep)
    if id_cotacao not in cotacoes["id"].values:
        st.error("Cotação não encontrada.")
        return

    cotacoes.loc[cotacoes["id"] == id_cotacao, "status"] = novo_status
    cotacoes.to_csv(get_cotacoes_path(username_rep), index=False)
    st.success(f"Status atualizado para {novo_status}.")

def aplicar_desconto_cotacao(id_cotacao, desconto_percentual, username_rep):
    """Aplica desconto na cotação"""
    cotacoes = load_cotacoes(username_rep)
    if id_cotacao not in cotacoes["id"].values:
        st.error("Cotação não encontrada.")
        return

    idx = cotacoes[cotacoes["id"] == id_cotacao].index[0]
    total_original = float(cotacoes.loc[idx, "total_original"])
    novo_total = total_original * (1 - desconto_percentual / 100)

    cotacoes.loc[idx, "desconto_percentual"] = desconto_percentual
    cotacoes.loc[idx, "total"] = novo_total

    cotacoes.to_csv(get_cotacoes_path(username_rep), index=False)
    st.success(f"Desconto de {desconto_percentual}% aplicado!")

def gerar_pdf_cotacao(cot_row, itens_df, show_prices=True):
    """Gera PDF da cotação"""
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Cotacao de Produtos", ln=True)

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"ID: {cot_row.get('id', '')}", ln=True)
    pdf.cell(0, 8, f"Cliente: {cot_row.get('cliente_nome', '')}", ln=True)
    pdf.cell(0, 8, f"Telefone: {cot_row.get('cliente_telefone', '')}", ln=True)
    pdf.cell(0, 8, f"Data: {cot_row.get('data', '')}", ln=True)
    pdf.cell(0, 8, f"Forma de recebimento: {cot_row.get('forma_recebimento', '')}", ln=True)

    try:
        total_original = float(cot_row.get("total_original", cot_row.get("total", 0.0)))
    except (ValueError, TypeError):
        total_original = 0.0

    try:
        desconto = float(cot_row.get("desconto_percentual", 0.0))
    except (ValueError, TypeError):
        desconto = 0.0

    if show_prices:
        pdf.cell(0, 8, f"Total original: R$ {total_original:.2f}", ln=True)

        if desconto:
            pdf.cell(0, 8, f"Desconto: {desconto:.1f}%", ln=True)

        try:
            total_final = float(cot_row.get('total', 0.0))
        except (ValueError, TypeError):
            total_final = 0.0

        pdf.cell(0, 8, f"Total final: R$ {total_final:.2f}", ln=True)
    else:
        pdf.cell(0, 8, "Valores totais a serem informados pelo representante.", ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(20, 8, "Cod.", border=1)
    pdf.cell(60, 8, "Produto", border=1)
    pdf.cell(12, 8, "Un.", border=1)
    pdf.cell(12, 8, "Qtde", border=1)
    if show_prices:
        pdf.cell(28, 8, "Preço Unitário", border=1)
        pdf.cell(32, 8, "Subtotal", border=1, ln=True)
    else:
        pdf.cell(60, 8, "Preços a serem informados", border=1, ln=True)

    pdf.set_font("Arial", "", 9)
    for _, row in itens_df.iterrows():
        codigo = str(row.get("codigo", ""))
        produto = str(row.get("produto", ""))[:30]
        unidade = str(row.get("unidade", ""))
        qtde = str(row.get("quantidade", ""))

        pdf.cell(20, 6, codigo, border=1)
        pdf.cell(60, 6, produto, border=1)
        pdf.cell(12, 6, unidade, border=1)
        pdf.cell(12, 6, qtde, border=1)
        if show_prices:
            try:
                preco_final = float(row.get("preco_final", 0.0))
            except (ValueError, TypeError):
                preco_final = 0.0

            try:
                subtotal_final = float(row.get("subtotal_final", 0.0))
            except (ValueError, TypeError):
                subtotal_final = 0.0

            pdf.cell(28, 6, f"{preco_final:.2f}", border=1)
            pdf.cell(32, 6, f"{subtotal_final:.2f}", border=1, ln=True)
        else:
            pdf.cell(60, 6, "-", border=1, ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 8, "Desenvolvido por beccai.com.br", ln=True, align="R")

    try:
        out = pdf.output(dest="S")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
        return b""

    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str):
        return out.encode("latin-1")

    raise RuntimeError("Não foi possível exportar PDF")

# ========================= 
# PÁGINAS - REPRESENTANTE
# ========================= 
def pagina_upload_tabela_precos(username_rep):
    """Página para importar a tabela de preços"""
    st.subheader("📊 Gerenciar Tabela de Preços")

    tabela_path = get_tabela_path(username_rep)

    if os.path.exists(tabela_path):
        st.success("✅ Você já possui uma tabela de preços cadastrada")

        df_atual = load_tabela_geral(username_rep)
        if not df_atual.empty:
            st.info(f"Produtos cadastrados: {len(df_atual)}")

            with st.expander("👁️ Visualizar tabela atual"):
                st.dataframe(df_atual.head(50))

        st.warning("⚠️ Carregar uma nova tabela substituirá a atual")
    else:
        st.info("Nenhuma tabela de preços cadastrada ainda")

    st.markdown("---")
    st.markdown("### 📤 Carregar Nova Tabela")

    st.markdown("""
    **Formato esperado do arquivo CSV:**
    - Separador: vírgula (,)
    - Codificação: UTF-8
    - Colunas obrigatórias: `Codigo`, `Produto`, `Unidade`, `Retira`
    - Colunas de preço por distância: `Preco100a199km`, `Preco200a299km`, etc.
    """)

    arquivo_upload = st.file_uploader(
        "Selecione o arquivo CSV com a tabela de preços",
        type=['csv'],
        help="Arquivo CSV com produtos e preços"
    )

    if arquivo_upload is not None:
        try:
            df_preview = pd.read_csv(arquivo_upload, sep=",", encoding="utf-8", dtype=str)
            df_preview.columns = [str(c).strip().replace(" ", "") for c in df_preview.columns]

            st.success("✅ Arquivo carregado com sucesso!")
            st.info(f"Total de produtos: {len(df_preview)}")

            colunas_necessarias = ["Codigo", "Produto", "Unidade", "Retira"]
            colunas_faltando = [col for col in colunas_necessarias if col not in df_preview.columns]

            if colunas_faltando:
                st.error(f"❌ Colunas obrigatórias faltando: {', '.join(colunas_faltando)}")
            else:
                st.success("✅ Todas as colunas obrigatórias presentes")

                with st.expander("👁️ Pré-visualizar dados (50 primeiras linhas)"):
                    st.dataframe(df_preview.head(50))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Confirmar e Salvar Tabela", type="primary"):
                        arquivo_upload.seek(0)
                        with open(tabela_path, 'wb') as f:
                            f.write(arquivo_upload.getvalue())
                        st.success("✅ Tabela de preços salva com sucesso!")
                        st.balloons()
                        st.rerun()

                with col2:
                    if st.button("🗑️ Cancelar"):
                        st.rerun()

        except Exception as e:
            st.error(f"❌ Erro ao processar arquivo: {e}")
            st.info("Verifique se o arquivo está no formato correto (CSV com separador vírgula)")

def pagina_upload_clientes(username_rep):
    """Página para importar a planilha de clientes"""
    st.subheader("👥 Gerenciar Clientes")

    clientes_path = get_clientes_path(username_rep)

    if os.path.exists(clientes_path):
        st.success("✅ Você já possui uma planilha de clientes")

        df_atual = load_clientes(username_rep)
        if not df_atual.empty:
            st.info(f"Clientes cadastrados: {len(df_atual)}")

            with st.expander("👁️ Visualizar clientes atuais"):
                st.dataframe(df_atual[['NOME', 'CNPJ', 'TELEFONE', 'CIDADE']])

        st.warning("⚠️ Carregar uma nova planilha substituirá a atual")
    else:
        st.info("Nenhuma planilha de clientes cadastrada ainda")

    st.markdown("---")
    st.markdown("### 📤 Carregar Nova Planilha de Clientes")

    st.markdown("""
    **Formato esperado do arquivo Excel (.xlsx):**
    - Colunas obrigatórias: `NOME`, `CNPJ`, `TELEFONE`
    - Colunas opcionais: `CIDADE`, `DISTANCIA`, `VISUALIZA_PRECO`
    """)

    arquivo_upload = st.file_uploader(
        "Selecione o arquivo Excel com os clientes",
        type=['xlsx'],
        help="Arquivo Excel (.xlsx) com dados dos clientes"
    )

    if arquivo_upload is not None:
        try:
            df_preview = pd.read_excel(arquivo_upload)
            df_preview = df_preview[df_preview["NOME"].notna()].copy()
            df_preview.columns = [str(c).strip().upper() for c in df_preview.columns]

            st.success("✅ Arquivo carregado com sucesso!")
            st.info(f"Total de clientes: {len(df_preview)}")

            colunas_necessarias = ["NOME"]
            colunas_faltando = [col for col in colunas_necessarias if col not in df_preview.columns]

            if colunas_faltando:
                st.error(f"❌ Colunas obrigatórias faltando: {', '.join(colunas_faltando)}")
            else:
                st.success("✅ Coluna NOME presente")

                with st.expander("👁️ Pré-visualizar dados"):
                    st.dataframe(df_preview)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Confirmar e Salvar Clientes", type="primary"):
                        arquivo_upload.seek(0)
                        df_save = pd.read_excel(arquivo_upload)
                        df_save.to_excel(clientes_path, index=False)
                        st.success("✅ Planilha de clientes salva com sucesso!")
                        st.balloons()
                        st.rerun()

                with col2:
                    if st.button("🗑️ Cancelar"):
                        st.rerun()

        except Exception as e:
            st.error(f"❌ Erro ao processar arquivo: {e}")
            st.info("Verifique se o arquivo está no formato correto (Excel .xlsx)")

def pagina_gestao_clientes_representante(username_rep):
    """Página de gestão de clientes pelo representante"""
    st.subheader("Gestão de Clientes")

    df = load_clientes(username_rep)
    if df.empty:
        st.info("Nenhum cliente cadastrado.")
        return

    filtro_nome = st.text_input("Filtrar por nome do cliente:", "")
    df_view = df.copy()

    if filtro_nome.strip():
        termo = filtro_nome.strip().lower()
        df_view = df_view[df_view["NOME"].astype(str).str.lower().str.contains(termo)]

    st.write(f"Total de clientes exibidos: {len(df_view)}")

    novos_valores = {}
    for idx, row in df_view.iterrows():
        col1, col2, col3 = st.columns([4, 3, 3])

        with col1:
            st.write(f"**{row['NOME']}**")
            st.write(f"CNPJ: {row.get('CNPJ', '')}")
            st.write(f"Telefone: {row.get('TELEFONE', '')}")

        with col2:
            valor_atual = bool(row.get("VISUALIZA_PRECO", True))
            novo_valor = st.checkbox(
                "Pode ver preços",
                value=valor_atual,
                key=f"visu_preco_{idx}"
            )
            novos_valores[idx] = novo_valor

        with col3:
            st.write(f"Cidade: {row.get('CIDADE', '') if 'CIDADE' in df.columns else ''}")
            st.write(f"Distância: {row.get('DISTANCIA', '') if 'DISTANCIA' in df.columns else ''}")

    if st.button("Salvar todas as alterações"):
        for idx, novo_valor in novos_valores.items():
            df.loc[idx, "VISUALIZA_PRECO"] = novo_valor
        salvar_clientes_df(df, username_rep)

def pagina_gerenciar_cotacoes_representante(username_rep):
    """Página para gerenciar cotações do representante"""
    st.subheader("Gerenciar Cotações")

    cotacoes = load_cotacoes(username_rep)
    itens_cot = load_itens_cotacao(username_rep)

    if cotacoes.empty:
        st.info("Nenhuma cotação registrada ainda")
        return

    filtro_status = st.selectbox(
        "Filtrar por status:",
        ["TODAS", "PENDENTE", "APROVADA", "CANCELADA"]
    )

    df_view = cotacoes.copy()
    if filtro_status != "TODAS":
        df_view = df_view[df_view["status"] == filtro_status]

    df_view = df_view.sort_values("data", ascending=False)

    st.write(f"Total de cotações: {len(df_view)}")

    for _, cot in df_view.iterrows():
        with st.expander(f"Cotação {cot['id']} - {cot['cliente_nome']} - {cot['status']}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Cliente:** {cot['cliente_nome']}")
                st.write(f"**Telefone:** {cot.get('cliente_telefone', '')}")
                st.write(f"**Data:** {cot['data']}")
                st.write(f"**Forma de recebimento:** {cot.get('forma_recebimento', '')}")

            with col2:
                try:
                    total_orig = float(cot.get('total_original', cot['total']))
                    desconto = float(cot.get('desconto_percentual', 0))
                    total_final = float(cot['total'])
                except (ValueError, TypeError):
                    total_orig = total_final = 0
                    desconto = 0

                st.write(f"**Total original:** R$ {total_orig:.2f}")

                if desconto > 0:
                    st.write(f"**Desconto aplicado:** {desconto:.1f}%")

                st.write(f"**Total final:** R$ {total_final:.2f}")

            itens = itens_cot[itens_cot['id_cotacao'] == cot['id']]
            if not itens.empty:
                st.markdown("**Itens:**")
                df_show = itens[['codigo', 'produto', 'quantidade', 'preco_final', 'subtotal_final']].rename(columns={
                    'codigo': 'Código',
                    'produto': 'Produto',
                    'quantidade': 'Qtde',
                    'preco_final': 'Preço Unit.',
                    'subtotal_final': 'Subtotal'
                })
                st.dataframe(df_show, use_container_width=True)

            st.markdown("---")
            st.markdown("**Ações:**")

            col_a, col_b, col_c, col_d = st.columns(4)

            with col_a:
                novo_status = st.selectbox(
                    "Status",
                    ["PENDENTE", "APROVADA", "CANCELADA"],
                    index=["PENDENTE", "APROVADA", "CANCELADA"].index(cot['status']),
                    key=f"status_{cot['id']}"
                )
                if st.button("Atualizar Status", key=f"btn_status_{cot['id']}"):
                    atualizar_status_cotacao(cot['id'], novo_status, username_rep)
                    st.rerun()

            with col_b:
                desconto_input = st.number_input(
                    "Desconto %",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(cot.get('desconto_percentual', 0)),
                    step=0.5,
                    key=f"desc_{cot['id']}"
                )
                if st.button("Aplicar Desconto", key=f"btn_desc_{cot['id']}"):
                    aplicar_desconto_cotacao(cot['id'], desconto_input, username_rep)
                    st.rerun()

            with col_c:
                pdf_bytes = gerar_pdf_cotacao(cot, itens, True)
                st.download_button(
                    label="Baixar PDF",
                    data=pdf_bytes,
                    file_name=f"cotacao_{cot['id']}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{cot['id']}"
                )

# ========================= 
# PÁGINAS - CLIENTE
# ========================= 
def pagina_nova_cotacao(cliente_row):
    """Interface de criação de cotação pelo cliente"""
    username_rep = cliente_row.get('representante_id', '')

    if not username_rep:
        st.error("Cliente não está vinculado a um representante")
        return

    tabela = load_tabela_geral(username_rep)

    if tabela.empty:
        st.warning("Nenhuma tabela de preços disponível. Entre em contato com seu representante.")
        return

    # Buscar cliente na base do representante
    clientes_df = load_clientes(username_rep)
    cliente_busca = clientes_df[
        (clientes_df['CNPJ'] == cliente_row.get('cnpj', '')) | 
        (clientes_df['TELEFONE'] == cliente_row.get('telefone', ''))
    ]

    if cliente_busca.empty:
        st.error("Dados do cliente não encontrados na base do representante")
        return

    cliente_data = cliente_busca.iloc[0]

    st.subheader("Nova Cotacao de Produtos")

    forma_recebimento = st.radio(
        "Como deseja receber os produtos?",
        ["Retirada no centro de distribuição", "Entrega no endereço"]
    )

    entrega = forma_recebimento == "Entrega no endereço"
    pode_ver_preco = cliente_pode_ver_preco(cliente_data)

    col_codigo = "Codigo_1" if "Codigo_1" in tabela.columns else "Codigo"
    col_produto = "Produto_1" if "Produto_1" in tabela.columns else "Produto"
    col_unidade = "Unidade_1" if "Unidade_1" in tabela.columns else "Unidade"

    st.markdown("---")
    st.subheader("Buscar e adicionar produtos")

    if "itens_cotacao" not in st.session_state:
        st.session_state["itens_cotacao"] = []

    termo_busca = st.text_input(
        "Digite ao menos 3 caracteres do código ou nome do produto:",
        key="busca_produto"
    )

    if termo_busca and len(termo_busca.strip()) >= 3:
        termo_lower = termo_busca.lower().strip()
        termo_normalized = unidecode(termo_lower)
        df_view = tabela[
            tabela[col_produto].astype(str).str.lower().apply(unidecode).str.contains(termo_normalized) |
            tabela[col_codigo].astype(str).str.lower().apply(unidecode).str.contains(termo_normalized)
        ].copy()
        df_view = df_view.head(20)

        if df_view.empty:
            st.warning("Nenhum produto encontrado")
        else:
            opcoes = df_view.apply(
                lambda row: f"{row[col_codigo]} - {row[col_produto]}",
                axis=1
            ).tolist()

            escolha = st.selectbox(
                "Selecione um produto:",
                [""] + opcoes,
                key="select_produto"
            )

            if escolha:
                codigo_escolhido = escolha.split(" - ")[0]
                produto_sel = df_view[df_view[col_codigo] == codigo_escolhido].iloc[0]

                preco_retira = get_preco_retira(produto_sel)
                preco_entrega = get_preco_entrega(cliente_data, produto_sel)

                if entrega:
                    preco_final = preco_entrega if preco_entrega is not None else preco_retira
                else:
                    preco_final = preco_retira

                st.markdown("### Detalhes do produto")
                st.write(f"**Código:** {produto_sel[col_codigo]}")
                st.write(f"**Produto:** {produto_sel[col_produto]}")
                st.write(f"**Unidade:** {produto_sel[col_unidade]}")

                if pode_ver_preco:
                    if preco_retira is not None:
                        st.write(f"**Preço para retirada:** R$ {preco_retira:.2f}")
                    if entrega and preco_entrega is not None:
                        st.write(f"**Preço com frete:** R$ {preco_entrega:.2f}")
                else:
                    st.info("Os preços serão calculados e enviados pelo representante.")

                qtd = st.number_input(
                    "Quantidade",
                    min_value=1,
                    value=1,
                    step=1,
                    key="qtd_add"
                )

                if st.button("+ Adicionar à cotação", key="btn_add_produto"):
                    if preco_final is None:
                        st.error("Produto sem preço disponível")
                    else:
                        subtotal_retira = preco_retira * qtd if preco_retira is not None else 0.0
                        subtotal_final = preco_final * qtd

                        st.session_state["itens_cotacao"].append({
                            "codigo": produto_sel[col_codigo],
                            "produto": produto_sel[col_produto],
                            "unidade": produto_sel[col_unidade],
                            "quantidade": qtd,
                            "preco_retira": preco_retira if preco_retira is not None else 0.0,
                            "preco_final": preco_final,
                            "subtotal_retira": subtotal_retira,
                            "subtotal_final": subtotal_final,
                        })
                        st.success("Item adicionado!")
                        st.rerun()

    elif termo_busca:
        st.info("Digite pelo menos 3 caracteres")

    st.markdown("---")
    st.subheader("Itens da sua cotação")

    itens = st.session_state.get("itens_cotacao", [])

    if itens:
        for idx, item in enumerate(itens):
            col1, col2, col3, col4, col5, col6 = st.columns([2, 3, 1, 1, 1, 1])

            with col1:
                st.write(f"**{item['codigo']}**")

            with col2:
                st.write(item["produto"])

            with col3:
                nova_qtd = st.number_input(
                    "Qtde",
                    min_value=1,
                    value=int(item["quantidade"]),
                    step=1,
                    key=f"qtd_{idx}",
                    label_visibility="collapsed"
                )
                if nova_qtd != item["quantidade"]:
                    st.session_state["itens_cotacao"][idx]["quantidade"] = nova_qtd
                    st.session_state["itens_cotacao"][idx]["subtotal_retira"] = item["preco_retira"] * nova_qtd
                    st.session_state["itens_cotacao"][idx]["subtotal_final"] = item["preco_final"] * nova_qtd
                    st.rerun()

            with col4:
                if pode_ver_preco:
                    st.write(f"R$ {item['preco_final']:.2f}")
                else:
                    st.write("-")

            with col5:
                if pode_ver_preco:
                    st.write(f"R$ {item['subtotal_final']:.2f}")
                else:
                    st.write("-")

            with col6:
                if st.button("X", key=f"del_{idx}"):
                    st.session_state["itens_cotacao"].pop(idx)
                    st.rerun()

        st.markdown("---")

        if pode_ver_preco:
            total_final = sum(item["subtotal_final"] for item in itens)
            st.markdown(f"### Total: R$ {total_final:.2f}")
        else:
            st.info("Os valores totais desta cotação serão calculados e enviados pelo representante.")

        col1, col2 = st.columns([1, 4])

        with col1:
            if st.button("Enviar Cotação", type="primary", key="btn_enviar"):
                id_cot = salvar_cotacao(cliente_data, itens, forma_recebimento, username_rep)
                if id_cot:
                    st.success(f"Cotação enviada! ID: {id_cot}")
                    st.session_state["itens_cotacao"] = []
                    st.rerun()

        with col2:
            if st.button("Limpar Tudo", key="btn_limpar"):
                st.session_state["itens_cotacao"] = []
                st.rerun()
    else:
        st.info("Nenhum item adicionado ainda. Busque produtos acima.")

def pagina_meus_pedidos(cliente_logado):
    """Mostra histórico de pedidos do cliente"""
    st.subheader("Meus Pedidos")

    username_rep = cliente_logado.get('representante_id', '')

    if not username_rep:
        st.error("Cliente não está vinculado a um representante")
        return

    # Buscar cliente na base do representante
    clientes_df = load_clientes(username_rep)
    cliente_busca = clientes_df[
        (clientes_df['CNPJ'] == cliente_logado.get('cnpj', '')) | 
        (clientes_df['TELEFONE'] == cliente_logado.get('telefone', ''))
    ]

    if cliente_busca.empty:
        st.error("Dados do cliente não encontrados na base do representante")
        return

    cliente_data = cliente_busca.iloc[0]
    pode_ver_preco = cliente_pode_ver_preco(cliente_data)

    cotacoes = load_cotacoes(username_rep)
    itens_cot = load_itens_cotacao(username_rep)

    tel_cliente = so_digitos(str(cliente_logado.get('telefone', '')))
    cotacoes['TEL_limp'] = cotacoes['cliente_telefone'].apply(so_digitos)

    minhas_cotacoes = cotacoes[
        (cotacoes['cliente_nome'] == cliente_logado.get('nome', '')) |
        (cotacoes['TEL_limp'] == tel_cliente)
    ].sort_values('data', ascending=False)

    if minhas_cotacoes.empty:
        st.info("Você ainda não tem pedidos")
        return

    st.write(f"**Total de pedidos:** {len(minhas_cotacoes)}")

    for idx, (_, cot) in enumerate(minhas_cotacoes.iterrows()):
        with st.expander(f"Pedido {cot['id']} - {cot['data']} - Status: {cot['status']}", expanded=(idx==0)):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Forma de recebimento:** {cot.get('forma_recebimento', 'N/A')}")
                st.write(f"**Status:** {cot['status']}")

            with col2:
                if pode_ver_preco:
                    try:
                        total_orig = float(cot.get('total_original', cot['total']))
                        desconto = float(cot.get('desconto_percentual', 0))
                        total_final = float(cot['total'])
                    except (ValueError, TypeError):
                        total_orig = total_final = 0
                        desconto = 0

                    st.write(f"**Total original:** R$ {total_orig:.2f}")
                    if desconto > 0:
                        st.write(f"**Desconto:** {desconto:.1f}%")
                    st.write(f"**Total final:** R$ {total_final:.2f}")
                else:
                    st.info("Os valores totais deste pedido serão informados pelo representante.")

            itens = itens_cot[itens_cot['id_cotacao'] == cot['id']]
            if not itens.empty:
                st.markdown("**Itens:**")
                df_show = itens[['codigo', 'produto', 'quantidade']].copy()
                if pode_ver_preco:
                    df_show['preco_final'] = itens['preco_final']
                    df_show['subtotal_final'] = itens['subtotal_final']
                else:
                    df_show['preco_final'] = '-'
                    df_show['subtotal_final'] = '-'
                df_show = df_show.rename(columns={
                    'codigo': 'Código',
                    'produto': 'Produto',
                    'quantidade': 'Qtde',
                    'preco_final': 'Preço Unit.',
                    'subtotal_final': 'Subtotal'
                })
                st.dataframe(df_show, use_container_width=True)

            pdf_bytes = gerar_pdf_cotacao(cot, itens, pode_ver_preco)
            st.download_button(
                label="Baixar PDF",
                data=pdf_bytes,
                file_name=f"pedido_{cot['id']}.pdf",
                mime="application/pdf",
                key=f"pdf_{cot['id']}"
            )

def pagina_cliente():
    """Página principal do cliente com Login"""
    local_css()

    if 'cliente_logado' not in st.session_state:
        st.session_state['cliente_logado'] = None

    if st.session_state['cliente_logado'] is None:
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])

        with col_centro:
            st.markdown('<div class="main-header">🛒 Área do Cliente</div>', unsafe_allow_html=True)
            st.markdown('Faça login ou cadastre sua senha.', unsafe_allow_html=True)

            tab1, tab2 = st.tabs(["Login", "Primeiro Acesso (Criar Senha)"])

            with tab1:
                st.subheader("Acesse sua conta")
                login_username = st.text_input("Usuário", key="login_user")
                login_senha = st.text_input("Senha", type="password", key="login_pass")
                st.write("")

                if st.button("ENTRAR", key="btn_login"):
                    if login_username and login_senha:
                        usuario, msg = autenticar_cliente(login_username, login_senha)
                        if usuario is not None:
                            st.session_state['cliente_logado'] = usuario
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos")

            with tab2:
                st.subheader("Crie sua senha")
                st.info("Use seu CNPJ ou Telefone cadastrado pelo representante para validar.")

                cad_cnpj_tel = st.text_input("CNPJ ou Telefone", key="cad_identificador", placeholder="Digite apenas números")

                if cad_cnpj_tel:
                    # Buscar em todos os representantes
                    representantes = load_usuarios_representantes()
                    cliente_encontrado = None
                    rep_encontrado = None

                    id_digitos = so_digitos(cad_cnpj_tel)

                    for _, rep in representantes.iterrows():
                        try:
                            clientes = load_clientes(rep['username'])
                            if not clientes.empty:
                                clientes['CNPJ_limp'] = clientes['CNPJ'].apply(so_digitos)
                                clientes['TEL_limp'] = clientes['TELEFONE'].apply(so_digitos)

                                match = clientes[
                                    (clientes['CNPJ_limp'] == id_digitos) |
                                    (clientes['TEL_limp'] == id_digitos)
                                ]

                                if not match.empty:
                                    cliente_encontrado = match.iloc[0]
                                    rep_encontrado = rep['username']
                                    break
                        except:
                            continue

                    if cliente_encontrado is not None:
                        st.success(f"Olá, {cliente_encontrado['NOME']}!")
                        st.markdown("---")

                        with st.form("form_cad_senha_cliente"):
                            cad_username = st.text_input("Crie seu Usuário de acesso")
                            cad_senha = st.text_input("Crie sua Senha", type="password")
                            cad_senha_confirm = st.text_input("Confirme sua Senha", type="password")
                            submit_cad = st.form_submit_button("CRIAR CONTA")

                            if submit_cad:
                                if cad_username and cad_senha and cad_senha_confirm:
                                    if cad_senha != cad_senha_confirm:
                                        st.error("As senhas não coincidem")
                                    elif len(cad_senha) < 6:
                                        st.error("A senha deve ter pelo menos 6 caracteres")
                                    else:
                                        sucesso, msg = salvar_usuario_cliente(
                                            username=cad_username,
                                            nome=cliente_encontrado['NOME'],
                                            senha=cad_senha,
                                            cnpj=str(cliente_encontrado.get('CNPJ', '')),
                                            telefone=str(cliente_encontrado.get('TELEFONE', '')),
                                            representante_id=rep_encontrado
                                        )
                                        if sucesso:
                                            st.balloons()
                                            st.success(msg + " Vá para a aba Login e entre agora!")
                                        else:
                                            st.error(msg)
                                else:
                                    st.warning("Preencha todos os campos")
                    else:
                        st.error("Cliente não encontrado. Verifique com seu representante.")

        return

    # Cliente logado
    cliente = st.session_state['cliente_logado']

    st.sidebar.title(f"Olá, {cliente.get('nome', 'Cliente')}! 👋")

    menu = st.sidebar.radio(
        "Menu",
        ["Nova Cotação", "Meus Pedidos"]
    )

    if st.sidebar.button("Sair"):
        st.session_state['cliente_logado'] = None
        st.rerun()

    if menu == "Nova Cotação":
        pagina_nova_cotacao(cliente)
    elif menu == "Meus Pedidos":
        pagina_meus_pedidos(cliente)

def pagina_representante():
    """Página principal do representante"""
    local_css()

    if 'representante_logado' not in st.session_state:
        st.session_state['representante_logado'] = None

    if st.session_state['representante_logado'] is None:
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])

        with col_centro:
            st.markdown('<div class="main-header">📊 Área do Representante</div>', unsafe_allow_html=True)
            st.markdown('Acesse o sistema ou crie um cadastro.', unsafe_allow_html=True)

            tab1, tab2 = st.tabs(["Login", "Novo Cadastro"])

            with tab1:
                st.subheader("Acesse o sistema")
                login_user = st.text_input("Usuário", key="rep_user")
                login_pass = st.text_input("Senha", type="password", key="rep_pass")
                st.write("")

                if st.button("ENTRAR", key="btn_rep_login"):
                    if login_user and login_pass:
                        usuario, msg = autenticar_representante(login_user, login_pass)
                        if usuario is not None:
                            st.session_state['representante_logado'] = usuario
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos")

            with tab2:
                st.subheader("Cadastro de Novo Representante")
                st.warning("Para criar uma conta, você precisa do Token de Autorização da empresa.")

                with st.form("form_novo_rep"):
                    nome_rep = st.text_input("Seu Nome Completo")
                    email_rep = st.text_input("Seu E-mail")
                    user_rep = st.text_input("Crie um Usuário (Login)")
                    pass_rep = st.text_input("Crie uma Senha", type="password")
                    pass_rep_conf = st.text_input("Confirme a Senha", type="password")
                    token_seguranca = st.text_input("Token de Admin", type="password", help="Peça ao gerente o código de cadastro")
                    submit_novo_rep = st.form_submit_button("CADASTRAR")

                    if submit_novo_rep:
                        TOKEN_CORRETO = "ADMIN123"

                        if token_seguranca != TOKEN_CORRETO:
                            st.error("Token de Admin inválido! Cadastro não permitido.")
                        elif not (nome_rep and user_rep and pass_rep):
                            st.error("Preencha todos os campos obrigatórios.")
                        elif pass_rep != pass_rep_conf:
                            st.error("As senhas não coincidem.")
                        else:
                            sucesso, msg = salvar_usuario_representante(
                                username=user_rep,
                                nome=nome_rep,
                                senha=pass_rep,
                                email=email_rep
                            )
                            if sucesso:
                                st.success("Conta criada com sucesso! Faça login na outra aba.")
                            else:
                                st.error(msg)

        return

    # Representante logado
    rep = st.session_state['representante_logado']
    username_rep = rep['username']

    st.sidebar.title(f"Olá, {rep.get('nome', 'Representante')}! 👋")

    menu = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Importar Tabela de Preços", "Importar Clientes", "Gestão de Clientes", "Gerenciar Cotações"]
    )

    if st.sidebar.button("Sair"):
        st.session_state['representante_logado'] = None
        st.rerun()

    if menu == "Dashboard":
        st.title("📊 Dashboard")

        col1, col2, col3 = st.columns(3)

        with col1:
            clientes = load_clientes(username_rep)
            st.metric("Total de Clientes", len(clientes))

        with col2:
            cotacoes = load_cotacoes(username_rep)
            st.metric("Total de Cotações", len(cotacoes))

        with col3:
            tabela = load_tabela_geral(username_rep)
            st.metric("Produtos na Tabela", len(tabela))

        st.markdown("---")

        if not cotacoes.empty:
            st.subheader("Cotações Recentes")
            recentes = cotacoes.sort_values('data', ascending=False).head(5)
            st.dataframe(recentes[['id', 'cliente_nome', 'data', 'status', 'total']], use_container_width=True)

    elif menu == "Upload Tabela de Preços":
        pagina_upload_tabela_precos(username_rep)

    elif menu == "Upload Clientes":
        pagina_upload_clientes(username_rep)

    elif menu == "Gestão de Clientes":
        pagina_gestao_clientes_representante(username_rep)

    elif menu == "Gerenciar Cotações":
        pagina_gerenciar_cotacoes_representante(username_rep)

# ========================= 
# APLICAÇÃO PRINCIPAL
# ========================= 
def main():
    st.set_page_config(
        page_title="RC Online",
        page_icon="🎯",
        layout="wide"
    )

    init_auth_files()

    st.sidebar.title("🎯RC Online")
    tipo_usuario = st.sidebar.radio("Tipo de Acesso", ["Cliente", "Representante"])

    if tipo_usuario == "Cliente":
        pagina_cliente()
    else:
        pagina_representante()

if __name__ == "__main__":
    main()
