import hmac
import html
import logging
import os
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import re
import unicodedata
from fpdf import FPDF
import bcrypt
from supabase import create_client, Client

# =====================================================================
# CONFIGURAÇÃO DE LOGS (SEG-6)
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("rc_online")

def registrar_erro(contexto: str, erro: Exception = None):
    """
    Registra o erro técnico completo apenas no terminal/logs do servidor,
    sem exibir detalhes internos ao usuário e sem incluir dados sensíveis.
    """
    if erro is not None:
        logger.exception(f"Falha em [{contexto}]")
    else:
        logger.error(f"Falha em [{contexto}]")

# Importa o módulo de gerenciamento de produtos
from produtos_manager import (
    processar_arquivo_produtos,
    sincronizar_produtos_supabase,
    calcular_impacto_sincronizacao,
    exibir_preview_dados,
    ler_arquivo,
    normalizar_colunas,
    validar_dados,
    limpar_dados
)

def normalizar_texto(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s

def data_brasil(data_iso):
    """Converte string ISO ou datetime UTC para string formatada BR (-3h)"""
    if not data_iso:
        return ""
    if isinstance(data_iso, str):
        try:
            dt = pd.to_datetime(data_iso)
        except Exception:
            return data_iso
    else:
        dt = data_iso
    
    # Ajuste manual de -3 horas (simulando Brasília)
    if dt.tzinfo:
        dt = dt.tz_convert('America/Sao_Paulo') if 'tz_convert' in dir(dt.dt) else dt - pd.Timedelta(hours=3)
        # Se vier com timezone do pandas, removemos para ficar naive local
        if hasattr(dt, 'tz_localize'):
            dt = dt.tz_localize(None)
    else:
        # Se não tem timezone, assumimos que é UTC e subtraímos 3
        dt = dt - pd.Timedelta(hours=3)
        
    return dt

def parse_money(valor):
    """
    Converte string de dinheiro BR (ex: '1.234,56') para float (1234.56).
    Aceita também float/int direto.
    """
    if valor is None or pd.isna(valor) or valor == "":
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Converte para string e limpa
    texto = str(valor).strip()
    
    # Remove R$, espaços e pontos de milhar (ex: 1.000 -> 1000)
    texto = texto.replace("R$", "").replace(" ", "").replace(".", "")
    
    # Substitui vírgula decimal por ponto (ex: 50,00 -> 50.00)
    texto = texto.replace(",", ".")
    
    try:
        return float(texto)
    except ValueError:
        return 0.0
 
def processar_tabela_produtos(arquivo):
    """
    Lê arquivos CSV ou Excel, padroniza as colunas e converte preços.
    Retorna um DataFrame pronto para o Supabase ou exibe erro no st.
    """
    try:
        # 1. Identificar extensão e ler o arquivo
        nome_arquivo = arquivo.name.lower()
        
        if nome_arquivo.endswith('.csv'):
            # Tenta ler com diferentes encodings e separadores comuns no Brasil
            try:
                df = pd.read_csv(arquivo, sep=',', decimal=',', quotechar='"', encoding='utf-8')
            except Exception:
                try:
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, sep=';', decimal=',', encoding='latin1')
                except Exception as e:
                    registrar_erro("Leitura de CSV na função processar_tabela_produtos", e)
                    st.error("Não foi possível ler o arquivo CSV. Verifique se o separador é vírgula ou ponto-e-vírgula.")
                    return None
        elif nome_arquivo.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(arquivo)
        else:
            st.error("Formato de arquivo não suportado. Use CSV ou Excel.")
            return None

        # 2. Padronização dos Nomes das Colunas (Mapa de Correção)
        df.columns = [c.strip().lower() for c in df.columns]
        
        mapa_colunas = {
            'codigo_1': 'codigo',
            'produto_1': 'produto',
            'unidade_1': 'unidade',
            'entrega_1': 'entrega',
        }
        
        df = df.rename(columns=mapa_colunas)

        # 3. Validação das Colunas Obrigatórias
        colunas_esperadas = ['codigo', 'produto', 'retira', 'entrega']
        if not all(col in df.columns for col in colunas_esperadas):
            st.error(f"O arquivo não possui as colunas obrigatórias: {colunas_esperadas}. Colunas encontradas: {list(df.columns)}")
            return None

        # 4. Tratamento de Preços (Limpeza Robusta)
        colunas_preco = [c for c in df.columns if 'preco' in c or c in ['retira', 'entrega']]
        
        for col in colunas_preco:
            def limpar_preco(x):
                if pd.isna(x): return 0.0
                if isinstance(x, (int, float)): return float(x)
                
                s = str(x).strip().replace('R$', '').replace(' ', '')
                if ',' in s:
                    s = s.replace('.', '').replace(',', '.')
                
                try:
                    return float(s)
                except Exception:
                    return 0.0

            df[col] = df[col].apply(limpar_preco)

        return df

    except Exception as e:
        registrar_erro("Processamento de tabela de produtos", e)
        st.error("Não foi possível processar a tabela de produtos. Verifique o arquivo e tente novamente.")
        return None
    
# =====================================================================
# CONFIGURAÇÃO DO SUPABASE
# =====================================================================

try:
    supabase_url = st.secrets["SUPABASE_URL"]
    
    # Usar service_role para operações administrativas (bypass RLS)
    if "SUPABASE_SERVICE_KEY" in st.secrets:
        supabase_key = st.secrets["SUPABASE_SERVICE_KEY"]
    else:
        supabase_key = st.secrets["SUPABASE_KEY"]
    
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    registrar_erro("Conexão inicial com o Supabase", e)
    st.error("⚠️ Não foi possível conectar ao sistema no momento. Tente novamente em instantes ou avise o suporte.")
    st.stop()

# =====================================================================
# ESTILOS CSS
# =====================================================================

def local_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gilroy:wght@400;600;700&family=Thasadith:wght@400;700&display=swap');
    
    * { font-family: 'Gilroy', sans-serif; }
    
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
    
    .stSidebar .stRadio label, .stSidebar .stSelectbox label, 
    .stSidebar .stButton button, .stSidebar h1, .stSidebar h2, .stSidebar p {
        color: white !important;
        font-family: 'Gilroy', sans-serif;
    }
    
    .stSidebar .stRadio div[role=radiogroup] label, .stSidebar .stSelectbox div label {
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

# =====================================================================
# FUNÇÕES GERAIS E SEGURANÇA
# =====================================================================

def so_digitos(valor):
    """Remove tudo que não for número"""
    if pd.isna(valor): return ""
    return re.sub(r'\D', '', str(valor))

def escapar_html(valor) -> str:
    """Escapa caracteres especiais HTML (<, >, &, ", ') vindos de texto digitado ou do banco."""
    if valor is None or pd.isna(valor):
        return ""
    return html.escape(str(valor), quote=True)

def parse_preco(valor):
    """(Alias para manter compatibilidade)"""
    return parse_money(valor)

def hash_senha(senha):
    """Gera hash da senha"""
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha, senha_hash):
    """Verifica senha"""
    try:
        return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))
    except Exception as e:
        registrar_erro("Verificação de hash de senha", e)
        return False

# =====================================================================
# CONTROLE DE TENTATIVAS DE LOGIN (SEG-4)
# =====================================================================

MAX_TENTATIVAS_LOGIN = 5
BLOQUEIO_MINUTOS = 15

def limpar_tentativas_login(identificador: str, tipo_usuario: str):
    """Zera contador após login bem-sucedido ou fim do prazo de bloqueio."""
    id_norm = str(identificador).strip().lower()
    if not id_norm:
        return
    try:
        supabase.table('tentativas_login').update({
            'tentativas': 0,
            'bloqueado_ate': None,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('identificador', id_norm).eq('tipo_usuario', tipo_usuario).execute()
    except Exception as e:
        registrar_erro(f"Limpar tentativas de login ({tipo_usuario})", e)

def verificar_bloqueio_login(identificador: str, tipo_usuario: str):
    """
    Verifica se o identificador está bloqueado temporariamente.
    Retorna (esta_bloqueado: bool, mensagem: str)
    """
    id_norm = str(identificador).strip().lower()
    if not id_norm:
        return False, ""

    try:
        resp = (
            supabase.table('tentativas_login')
            .select('*')
            .eq('identificador', id_norm)
            .eq('tipo_usuario', tipo_usuario)
            .execute()
        )
        if not resp.data:
            return False, ""

        registro = resp.data[0]
        bloqueado_ate_str = registro.get('bloqueado_ate')

        if bloqueado_ate_str:
            bloqueado_ate = pd.to_datetime(bloqueado_ate_str)
            if bloqueado_ate.tzinfo is None:
                bloqueado_ate = bloqueado_ate.tz_localize('UTC')

            agora = datetime.now(timezone.utc)

            if agora < bloqueado_ate:
                segundos_restantes = int((bloqueado_ate - agora).total_seconds())
                minutos_restantes = max(1, (segundos_restantes + 59) // 60)
                return True, f"⛔ Acesso temporariamente bloqueado por excesso de tentativas. Tente novamente em {minutos_restantes} minuto(s)."
            else:
                # Tempo de bloqueio expirou: zera o contador automaticamente
                limpar_tentativas_login(id_norm, tipo_usuario)

        return False, ""
    except Exception as e:
        registrar_erro(f"Verificar bloqueio de login ({tipo_usuario})", e)
        return False, ""

def registrar_falha_login(identificador: str, tipo_usuario: str) -> str:
    """
    Incrementa tentativas erradas e aplica bloqueio ao atingir o limite.
    Retorna mensagem informativa para exibir ao usuário.
    """
    id_norm = str(identificador).strip().lower()
    if not id_norm:
        return "Credenciais inválidas."

    try:
        resp = (
            supabase.table('tentativas_login')
            .select('*')
            .eq('identificador', id_norm)
            .eq('tipo_usuario', tipo_usuario)
            .execute()
        )

        agora = datetime.now(timezone.utc)
        tentativas_atuais = 0
        registro_id = None

        if resp.data:
            registro = resp.data[0]
            registro_id = registro['id']
            tentativas_atuais = int(registro.get('tentativas', 0))

        novas_tentativas = tentativas_atuais + 1
        bloqueado_ate_iso = None

        if novas_tentativas >= MAX_TENTATIVAS_LOGIN:
            bloqueado_ate_iso = (agora + pd.Timedelta(minutes=BLOQUEIO_MINUTOS)).isoformat()
            msg = f"⛔ Muitas tentativas incorretas. Acesso bloqueado por {BLOQUEIO_MINUTOS} minutos."
        else:
            restantes = MAX_TENTATIVAS_LOGIN - novas_tentativas
            msg = f"Senha incorreta. Você tem mais {restantes} tentativa(s) antes do bloqueio temporário."

        payload = {
            'identificador': id_norm,
            'tipo_usuario': tipo_usuario,
            'tentativas': novas_tentativas,
            'bloqueado_ate': bloqueado_ate_iso,
            'updated_at': agora.isoformat()
        }

        if registro_id:
            supabase.table('tentativas_login').update(payload).eq('id', registro_id).execute()
        else:
            supabase.table('tentativas_login').insert(payload).execute()

        return msg
    except Exception as e:
        registrar_erro(f"Registrar falha de login ({tipo_usuario})", e)
        return "Usuário ou senha incorretos."   

# =====================================================================
# AUTENTICAÇÃO - REPRESENTANTE E ADMINISTRADORA
# =====================================================================

def autenticar_representante(email, senha):
    email_limpo = str(email).strip().lower()
    if not email_limpo:
        return None, "Informe o e-mail."

    bloqueado, msg_bloqueio = verificar_bloqueio_login(email_limpo, 'REPRESENTANTE')
    if bloqueado:
        return None, msg_bloqueio

    try:
        # Usa cliente isolado para não sobrescrever a chave administrativa do cliente global
        auth_client = create_client(supabase_url, supabase_key)
        response = auth_client.auth.sign_in_with_password({"email": email_limpo, "password": senha})
        user_id = response.user.id

        rep_resp = supabase.table('representantes').select('*').eq('id', user_id).execute()
        if not rep_resp.data:
            logger.warning(f"Usuário autenticado sem perfil na tabela representantes (id={user_id})")
            return None, "Cadastro de representante não localizado. Contate a administração."

        limpar_tentativas_login(email_limpo, 'REPRESENTANTE')
        return rep_resp.data[0], "Login realizado com sucesso!"
    except Exception as e:
        logger.warning(f"Falha na autenticação do representante ({type(e).__name__})")
        msg_falha = registrar_falha_login(email_limpo, 'REPRESENTANTE')
        return None, f"Usuário ou senha incorretos. {msg_falha}"
        
def criar_representante_admin(nome, email, senha, telefone):
    """Cria representante via API administrativa do Supabase com troca obrigatória de senha no 1º acesso (SEG-12)"""
    try:
        # Cria cliente limpo com a chave administrativa para não sofrer interferência de logins anteriores
        admin_client = create_client(supabase_url, supabase_key)
        response = admin_client.auth.admin.create_user({
            "email": email.strip(),
            "password": senha,
            "email_confirm": True
        })
        user_id = response.user.id

        # Insere o perfil na tabela representantes exigindo troca de senha no 1º acesso
        supabase.table('representantes').insert({
            'id': user_id,
            'nome': nome.strip(),
            'email': email.strip(),
            'telefone': so_digitos(telefone) if telefone else None,
            'trocar_senha': True
        }).execute()

        return True, f"Representante '{nome}' cadastrado com sucesso! Ele deverá trocar a senha no primeiro acesso."
    except Exception as e:
        registrar_erro("Cadastro de representante pela administradora", e)
        return False, "Não foi possível cadastrar o representante. Verifique se o e-mail já não está cadastrado e tente novamente."

def atualizar_senha_representante(user_id: str, nova_senha: str):
    """Atualiza a senha no Supabase Auth e libera o acesso do representante (SEG-12)"""
    try:
        # Cria cliente limpo com a chave administrativa para garantir permissão de troca
        admin_client = create_client(supabase_url, supabase_key)
        admin_client.auth.admin.update_user_by_id(
            str(user_id).strip(),
            {"password": nova_senha}
        )
        supabase.table('representantes').update({
            'trocar_senha': False
        }).eq('id', user_id).execute()
        return True, "Senha atualizada com sucesso!"
    except Exception as e:
        registrar_erro("Troca de senha no primeiro acesso do representante", e)
        return False, "Não foi possível atualizar sua senha no momento. Tente novamente."
    
# =====================================================================
# AUTENTICAÇÃO E LÓGICA - CLIENTE
# =====================================================================

def autenticar_cliente(identificador, senha):
    """Busca cliente por CNPJ/Tel, verifica bloqueio e valida senha"""
    id_limpo = so_digitos(identificador)
    if not id_limpo:
        return None, "Digite apenas números."

    bloqueado, msg_bloqueio = verificar_bloqueio_login(id_limpo, 'CLIENTE')
    if bloqueado:
        return None, msg_bloqueio

    try:
        response = supabase.table('clientes').select('*').or_(f"cnpj.eq.{id_limpo},telefone.eq.{id_limpo}").execute()
        if not response.data:
            msg_falha = registrar_falha_login(id_limpo, 'CLIENTE')
            return None, f"Cliente não encontrado ou credenciais inválidas. {msg_falha}"

        cliente = response.data[0]
        if not cliente.get('senha_hash'):
            return None, "Conta não ativada. Crie sua senha primeiro."

        if verificar_senha(senha, cliente['senha_hash']):
            limpar_tentativas_login(id_limpo, 'CLIENTE')
            return cliente, "Login com sucesso!"
        else:
            msg_falha = registrar_falha_login(id_limpo, 'CLIENTE')
            return None, msg_falha
    except Exception as e:
        registrar_erro("Autenticação de cliente", e)
        return None, "Erro ao validar acesso. Tente novamente."

def ativar_senha_cliente(identificador, nova_senha):
    """Ativa senha apenas para cliente validado pelo representante e ainda sem senha (SEG-1)"""
    id_limpo = so_digitos(identificador)
    if not id_limpo:
        return False, "Identificador inválido. Digite apenas números."
    
    try:
        response = supabase.table('clientes').select('*').or_(f"cnpj.eq.{id_limpo},telefone.eq.{id_limpo}").execute()
        if not response.data:
            return False, "Cadastro não localizado. Fale com seu representante."
        
        cliente = response.data[0]

        # Trava 1: Prospect ainda não validado não pode ativar senha
        if cliente.get('status_cliente') != 'CLIENTE':
            return False, "Seu cadastro ainda aguarda validação do representante."

        # Trava 2: Conta já possui senha ativa (impede sequestro/sobrescrita)
        if cliente.get('senha_hash'):
            return False, "Esta conta já possui senha cadastrada. Faça login na aba 'Já tenho senha' ou peça ao representante para resetar."

        supabase.table('clientes').update({
            'senha_hash': hash_senha(nova_senha)
        }).eq('id', cliente['id']).execute()
        return True, "Senha criada com sucesso! Agora acesse a aba 'Já tenho senha' para entrar."
    except Exception as e:
        registrar_erro("Ativação de senha do cliente", e)
        return False, "Não foi possível ativar a senha no momento. Tente novamente."

# Mantemos estas por compatibilidade caso seu código antigo use
def buscar_cliente_para_cadastro(identificador):
    id_limpo = so_digitos(identificador)
    try:
        response = supabase.table('clientes').select('*').or_(f"cnpj.eq.{id_limpo},telefone.eq.{id_limpo}").execute()
        if response.data:
            return response.data[0], response.data[0]['representante_id']
    except Exception as e:
        registrar_erro("Busca de cliente para cadastro", e)
    return None, None

def criar_senha_cliente(cliente_id, senha):
    try:
        supabase.table('clientes').update({'senha_hash': hash_senha(senha)}).eq('id', cliente_id).execute()
        return True, "Senha criada!"
    except Exception as e:
        registrar_erro("Criação de senha do cliente", e)
        return False, "Não foi possível criar a senha. Tente novamente."

# =====================================================================
# FUNÇÕES DE DADOS - CLIENTES
# =====================================================================

def carregar_clientes(representante_id):
    """Carrega clientes do representante"""
    try:
        response = supabase.table('clientes').select('*').eq('representante_id', representante_id).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        registrar_erro("Carregar clientes do representante", e)
        st.error("Não foi possível carregar a lista de clientes no momento.")
        return pd.DataFrame()

def atualizar_visualiza_preco(cliente_id, pode_ver, representante_id):
    """Atualiza flag de visualização de preço garantindo isolamento por representante"""
    try:
        supabase.table('clientes').update({
            'visualiza_preco': pode_ver
        }).eq('id', cliente_id).eq('representante_id', representante_id).execute()
        return True
    except Exception as e:
        registrar_erro("Atualizar permissão de visualização de preço", e)
        st.error("Não foi possível atualizar a permissão de preços.")
        return False

def atualizar_permite_retirada(cliente_id, permite_retirada, representante_id):
    """Atualiza flag de permissão de retirada garantindo isolamento por representante"""
    try:
        supabase.table('clientes').update({
            'permite_retirada': permite_retirada
        }).eq('id', cliente_id).eq('representante_id', representante_id).execute()
        return True
    except Exception as e:
        registrar_erro("Atualizar permissão de retirada do cliente", e)
        st.error("Não foi possível atualizar a permissão de retirada.")
        return False

def upload_clientes_excel(arquivo, representante_id):
    """
    Lê Excel ou CSV de clientes e faz upsert no banco usando ID para evitar conflitos
    """
    try:
        # 0. BUSCAR CLIENTES EXISTENTES (Para resolver conflitos de ID)
        existing_df = carregar_clientes(representante_id)
        map_cnpj = {}
        map_tel = {}
        
        if not existing_df.empty:
            if 'cnpj' in existing_df.columns:
                for _, row in existing_df.iterrows():
                    c_limpo = so_digitos(str(row['cnpj']))
                    if c_limpo: map_cnpj[c_limpo] = row['id']
                    
            if 'telefone' in existing_df.columns:
                for _, row in existing_df.iterrows():
                    t_limpo = so_digitos(str(row['telefone']))
                    if t_limpo: map_tel[t_limpo] = row['id']

        # 1. Ler arquivo
        nome_arquivo = arquivo.name.lower()
        if nome_arquivo.endswith('.csv'):
            df = pd.read_csv(arquivo, dtype=str)
        else:
            df = pd.read_excel(arquivo, dtype=str)
        
        # 2. Normalizar cabeçalhos
        df.columns = [str(c).strip().upper().replace('_', '').replace(' ', '') for c in df.columns]
        
        # 3. Validar
        if 'NOME' not in df.columns:
            st.error("❌ O arquivo não possui a coluna 'NOME'. Verifique o cabeçalho.")
            return

        df = df[df['NOME'].notna()].copy()
        
        if df.empty:
            st.warning("⚠️ O arquivo parece vazio.")
            return
            
        clientes = []
        count_sem_doc = 0
        count_atualizados = 0
        count_novos = 0
        
        for _, row in df.iterrows():
            
            # --- TRATAMENTO DE DADOS ---
            cnpj_limpo = so_digitos(str(row.get('CNPJ', '')))
            tel_limpo = so_digitos(str(row.get('TELEFONE', '')))
            
            # --- LÓGICA DE DETECÇÃO DE ID ---
            cliente_id = None
            
            if cnpj_limpo and cnpj_limpo in map_cnpj:
                cliente_id = map_cnpj[cnpj_limpo]
            elif tel_limpo and tel_limpo in map_tel:
                cliente_id = map_tel[tel_limpo]
            
            if cliente_id:
                count_atualizados += 1
            else:
                count_novos += 1

            if not cnpj_limpo and not tel_limpo:
                count_sem_doc += 1
            
            # --- DISTÂNCIA ---
            coluna_preco = 'preco_entrega'
            dist_val = 0
            val_dist = row.get('DISTANCIA')
            if pd.notna(val_dist):
                try:
                    dist_limpa = re.sub(r'\D', '', str(val_dist))
                    if dist_limpa:
                        dist_val = int(dist_limpa)
                        if dist_val < 100: coluna_preco = 'preco_entrega'
                        elif dist_val < 200: coluna_preco = 'preco_100a199km'
                        elif dist_val < 300: coluna_preco = 'preco_200a299km'
                        elif dist_val < 400: coluna_preco = 'preco_300a399km'
                        elif dist_val <= 500: coluna_preco = 'preco_acima400km'
                        elif dist_val <= 600: coluna_preco = 'preco_acima500km'
                        else: coluna_preco = 'preco_acima600km'
                except Exception:
                    dist_val = 0

            # --- VISUALIZA PREÇO ---
            visualiza = True
            val_visu = str(row.get('VISUALIZAPRECO', '')).lower().strip()
            if val_visu in ['não', 'nao', 'n', 'false', '0', 'block']:
                visualiza = False

            # --- PERMITE RETIRADA (desabilitada por padrão) ---
            permite_ret = False
            val_ret = str(row.get('PERMITERETIRADA', '')).lower().strip()
            if val_ret in ['sim', 's', 'true', '1', 'yes', 'liberado']:
                permite_ret = True
            
            cliente_dict = {
                'representante_id': representante_id,
                'nome': str(row['NOME']).strip().upper(),
                'cnpj': cnpj_limpo,
                'telefone': tel_limpo,
                'cidade': str(row.get('CIDADE', '')).strip(),
                'distancia_km': dist_val,
                'coluna_preco': coluna_preco,
                'visualiza_preco': visualiza,
                'permite_retirada': permite_ret,
                'status_cliente': 'CLIENTE'
            }

            if not cliente_id:
                cliente_dict['senha_hash'] = None
            
            if cliente_id:
                cliente_dict['id'] = cliente_id
            
            clientes.append(cliente_dict)
        
        if not clientes:
            st.warning("Nenhum cliente válido encontrado.")
            return

        supabase.table('clientes').upsert(clientes, on_conflict='id').execute()
        
        st.success(f"✅ Processo finalizado! {len(clientes)} clientes processados.")
        st.caption(f"📝 Novos: {count_novos} | 🔄 Atualizados: {count_atualizados}")
        
        if count_sem_doc > 0:
            st.warning(f"⚠️ Nota: {count_sem_doc} clientes sem CNPJ/Telefone.")
        
    except Exception as e:
        registrar_erro("Upload de planilha de clientes", e)
        st.error("Não foi possível importar a planilha de clientes. Verifique se não há CNPJs duplicados ou inválidos e tente novamente.")


# =====================================================================
# FUNÇÕES DE DADOS - PRODUTOS
# =====================================================================

def carregar_produtos(representante_id):
    """Carrega todos os produtos ativos do representante (paginado acima de 1.000 registros)"""
    try:
        todos_produtos = []
        tamanho_pagina = 1000
        inicio = 0

        while True:
            response = (
                supabase.table('produtos')
                .select('*')
                .eq('representante_id', representante_id)
                .eq('ativo', True)
                .range(inicio, inicio + tamanho_pagina - 1)
                .execute()
            )
            lote = response.data or []
            todos_produtos.extend(lote)

            if len(lote) < tamanho_pagina:
                break
            inicio += tamanho_pagina

        return pd.DataFrame(todos_produtos)
    except Exception as e:
        registrar_erro("Carregar produtos do representante", e)
        st.error("Não foi possível carregar os produtos no momento.")
        return pd.DataFrame()
    
@st.cache_data(ttl=300)  # 5 minutos
def carregar_catalogo_representante(representante_id: str) -> pd.DataFrame:
    todos_produtos = []
    tamanho_pagina = 1000
    inicio = 0

    while True:
        response = (
            supabase.table('produtos')
            .select('id,codigo,produto,unidade,preco_retira,preco_entrega,preco_100a199km,preco_200a299km,preco_300a399km,preco_acima400km,preco_acima500km,preco_acima600km')
            .eq('representante_id', representante_id)
            .eq('ativo', True)
            .range(inicio, inicio + tamanho_pagina - 1)
            .execute()
        )
        lote = response.data or []
        todos_produtos.extend(lote)

        if len(lote) < tamanho_pagina:
            break
        inicio += tamanho_pagina

    return pd.DataFrame(todos_produtos)

def buscar_produtos(representante_id, termo):
    """Busca produtos por código ou nome (sem exigir acento)"""
    try:
        termo_limpo = (termo or "").strip()
        if not termo_limpo:
            return pd.DataFrame()

        termo_norm = normalizar_texto(termo_limpo)

        # Puxa o catálogo do representante via cache
        df = carregar_catalogo_representante(representante_id)

        if df.empty:
            return pd.DataFrame()

        # Garante strings
        df["codigo"] = df["codigo"].astype(str)
        df["produto"] = df["produto"].astype(str)

        # Normaliza para busca sem acento
        df["codigo_norm"] = df["codigo"].apply(normalizar_texto)
        df["produto_norm"] = df["produto"].apply(normalizar_texto)

        # Filtro no código ou produto (sem acento)
        mask = (
            df["codigo_norm"].str.contains(termo_norm, na=False) |
            df["produto_norm"].str.contains(termo_norm, na=False)
        )

        df_filtrado = df[mask].copy()

        # Remove colunas auxiliares antes de retornar
        df_filtrado.drop(columns=["codigo_norm", "produto_norm"], errors="ignore", inplace=True)

        return df_filtrado.head(20)

    except Exception as e:
        registrar_erro("Buscar produtos no catálogo", e)
        st.error("Não foi possível realizar a busca de produtos no momento.")
        return pd.DataFrame()

def get_preco_produto(produto_row, coluna_preco, forma_recebimento):
    """
    Retorna o preço do produto baseado na coluna de preço do cliente 
    e forma de recebimento (retirada ou entrega com múltiplas distâncias)
    """
    if forma_recebimento == 'Retirada no centro de distribuição':
        preco = produto_row.get('preco_retira')
    else:
        preco = produto_row.get(coluna_preco)
    
    return preco if preco and not pd.isna(preco) else None


def obter_opcoes_distancia():
    """
    Retorna as opções de distância disponíveis no sistema.
    Ordem: retirada, entrega (0 a 99 km), depois distâncias crescentes.
    """
    return [
        ("Retirada no centro de distribuição", "preco_retira"),
        ("Entrega (0 a 99 km)", "preco_entrega"),
        ("100 a 199 km", "preco_100a199km"),
        ("200 a 299 km", "preco_200a299km"),
        ("300 a 399 km", "preco_300a399km"),
        ("400 a 500 km", "preco_acima400km"),
        ("501 a 600 km", "preco_acima500km"),
        ("Acima de 600 km", "preco_acima600km"),
    ]

def formatar_opcao_distancia(opcao_label):
    """Formata o label da opção de distância para exibição"""
    return f"📍 {opcao_label}"

def upload_tabela_precos_csv(arquivo, representante_id):
    """
    Versão DEFINITIVA para ler qualquer variação de nome de coluna e formato de arquivo.
    """
    try:
        # 1. Leitura Robusta do Arquivo
        nome_arquivo = arquivo.name.lower()
        arquivo.seek(0)
        df = None
        
        # Leitura de EXCEL (.xlsx, .xls)
        if nome_arquivo.endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(arquivo, dtype=str)
            except Exception as e:
                registrar_erro("Leitura de Excel na tabela de preços", e)
                st.error("Não foi possível ler a planilha Excel. Verifique se o arquivo não está corrompido.")
                return

        # Leitura de CSV (.csv) com várias tentativas de codificação
        elif nome_arquivo.endswith('.csv'):
            encodings = ['utf-8-sig', 'latin-1', 'cp1252', 'utf-8']
            separadores = [',', ';', '\t']
            
            for enc in encodings:
                for sep in separadores:
                    try:
                        arquivo.seek(0)
                        temp_df = pd.read_csv(arquivo, sep=sep, encoding=enc, dtype=str, engine='python')
                        
                        if len(temp_df.columns) > 1:
                            df = temp_df
                            break
                    except Exception:
                        continue
                if df is not None:
                    break
        
        if df is None:
            st.error("❌ Não consegui ler o arquivo. Tente salvar como 'CSV UTF-8' ou Excel (.xlsx).")
            return

        df = df.dropna(how='all')

        # ==========================================================
        # 2. MAPA DE COLUNAS FLEXÍVEL (REGEX)
        # ==========================================================
        mapa_colunas = {
            'Codigo': [r'c[oó]digo', r'ref', r'sku', r'item', r'cod\.'],
            'Produto': [r'produto', r'descri[cç][aã]o', r'nome', r'material'],
            'Unidade': [r'unidade', r'un\.', r'^un$'], 
            'Retira': [r'retira', r'balc[aã]o', r'loja'],
            'Entrega': [r'entrega', r'cif', r'transp'],
            'Preco100a199km': [r'100.*199', r'100.*a.*199'],
            'Preco200a299km': [r'200.*299', r'200.*a.*299'],
            'Preco300a399km': [r'300.*399', r'300.*a.*399'],
            'PrecoAcima400km': [r'400', r'acima.*400'],
            'PrecoAcima500km': [r'500', r'acima.*500'],
            'PrecoAcima600km': [r'600', r'acima.*600']
        }

        colunas_originais = [str(c).strip() for c in df.columns.tolist()]
        colunas_renomeadas = {}

        for col_real in colunas_originais:
            col_lower = col_real.lower()
            for coluna_alvo, padroes in mapa_colunas.items():
                for padrao in padroes:
                    if re.search(padrao, col_lower):
                        colunas_renomeadas[col_real] = coluna_alvo
                        break
                if col_real in colunas_renomeadas:
                    break

        df = df.rename(columns=colunas_renomeadas)
        
        # === DIAGNÓSTICO PARA O USUÁRIO ===
        if 'Codigo' not in df.columns or 'Produto' not in df.columns:
            st.error("❌ Não consegui identificar as colunas principais.")
            st.warning("Preciso de uma coluna que contenha **'Código'** (ou Ref/SKU) e outra com **'Produto'** (ou Descrição/Nome).")
            
            with st.expander("👀 Ver colunas que o sistema encontrou"):
                st.write("Nomes originais no arquivo:")
                st.write(colunas_originais)
                st.write("---")
                st.write("Como o sistema tentou renomear:")
                st.write(colunas_renomeadas)
            return

        df = df[(df['Codigo'].notna()) & (df['Codigo'] != '') & (df['Produto'].notna())]

        # ==========================================================
        # 3. LIMPEZA E UPLOAD
        # ==========================================================
        status_msg = st.empty()
        status_msg.info("⏳ Substituindo tabela de preços...")
        
        try:
            supabase.table('produtos').delete().eq('representante_id', representante_id).execute()
        except Exception as e:
            registrar_erro("Limpar tabela antiga de produtos antes do upload", e)
            st.error("Não foi possível limpar a tabela anterior. Tente novamente.")
            return

        produtos = []
        agora_iso = datetime.now(timezone.utc).isoformat()
        erros_conversao = 0
        
        progresso_text = "Processando linhas..."
        my_bar = st.progress(0, text=progresso_text)
        total_linhas = len(df)

        for idx, row in df.iterrows():
            try:
                if idx % 50 == 0:
                    my_bar.progress(min(idx / total_linhas, 1.0), text=f"Processando item {idx}/{total_linhas}")

                p = {
                    'representante_id': representante_id,
                    'codigo': str(row.get('Codigo', '')).strip(),
                    'produto': str(row.get('Produto', '')).strip(),
                    'unidade': str(row.get('Unidade', '')).strip() if pd.notna(row.get('Unidade')) else None,
                    'preco_retira': parse_money(row.get('Retira')),
                    'preco_entrega': parse_money(row.get('Entrega')), 
                    'preco_100a199km': parse_money(row.get('Preco100a199km')),
                    'preco_200a299km': parse_money(row.get('Preco200a299km')),
                    'preco_300a399km': parse_money(row.get('Preco300a399km')),
                    'preco_acima400km': parse_money(row.get('PrecoAcima400km')),
                    'preco_acima500km': parse_money(row.get('PrecoAcima500km')),
                    'preco_acima600km': parse_money(row.get('PrecoAcima600km')),
                    'created_at': agora_iso 
                }
                produtos.append(p)
            except Exception as e:
                registrar_erro(f"Conversão de linha na planilha de produtos (linha {idx})", e)
                erros_conversao += 1
         
        if not produtos:
            st.error("❌ Nenhum produto válido para salvar.")
            return

        batch_size = 1000
        for i in range(0, len(produtos), batch_size):
            batch = produtos[i:i + batch_size]
            try:
                supabase.table('produtos').insert(batch).execute()
            except Exception as e:
                registrar_erro("Inserção em lote na tabela de produtos", e)
                st.error("❌ Não foi possível salvar os produtos no banco de dados. Tente novamente.")
                break
        
        my_bar.empty()
        status_msg.empty()
        st.success(f"✅ Tabela atualizada! {len(produtos)} produtos cadastrados.")
        if erros_conversao > 0:
            st.warning(f"⚠️ {erros_conversao} linhas ignoradas por erro de formatação.")

    except Exception as e:
        registrar_erro("Upload geral da tabela de preços CSV/Excel", e)
        st.error("❌ Não foi possível concluir o envio da tabela de preços. Tente novamente.")

# =====================================================================
# FUNÇÕES DE DADOS - COTAÇÕES
# =====================================================================

AVISO_PRECOS_REFERENCIAIS = (
    "Observação: Os preços apresentados são referenciais e estão sujeitos a alteração "
    "até o fechamento e aprovação do pedido pelo Representante."
)

def carregar_cotacoes(representante_id):
    """Carrega cotações do representante"""
    try:
        response = supabase.table('cotacoes').select('*, clientes(nome, telefone)').eq('representante_id', representante_id).order('created_at', desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        registrar_erro("Carregar cotações do representante", e)
        st.error("Não foi possível carregar as cotações no momento.")
        return pd.DataFrame()

def carregar_cotacoes_cliente(cliente_id):
    """Carrega cotações de um cliente"""
    try:
        response = supabase.table('cotacoes').select('*').eq('cliente_id', cliente_id).order('created_at', desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        registrar_erro("Carregar cotações do cliente", e)
        st.error("Não foi possível carregar seus pedidos no momento.")
        return pd.DataFrame()

def carregar_itens_cotacao(cotacao_id):
    """Carrega itens de uma cotação"""
    try:
        response = supabase.table('cotacao_itens').select('*').eq('cotacao_id', cotacao_id).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        registrar_erro("Carregar itens da cotação", e)
        st.error("Não foi possível carregar os itens desta cotação.")
        return pd.DataFrame()

def gerar_id_cotacao(cliente_nome):
    """Gera ID único da cotação"""
    cliente_prefix = re.sub(r'\W', '', cliente_nome.upper())[:4].ljust(4, 'X')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{cliente_prefix}{timestamp}"

def salvar_cotacao(representante_id, cliente_id, cliente_nome, itens, forma_recebimento):
    """
    Salva cotação e itens no banco
    """
    try:
        total = sum([item['subtotal'] for item in itens])
        cotacao_id = gerar_id_cotacao(cliente_nome)
        
        supabase.table('cotacoes').insert({
            'id': cotacao_id,
            'representante_id': representante_id,
            'cliente_id': cliente_id,
            'status': 'PENDENTE',
            'forma_recebimento': forma_recebimento,
            'total_original': total,
            'desconto_geral_percentual': 0,
            'total_final': total
        }).execute()
        
        itens_para_inserir = []
        for item in itens:
            itens_para_inserir.append({
                'cotacao_id': cotacao_id,
                'produto_id': item.get('produto_id'),
                'codigo': item['codigo'],
                'produto': item['produto'],
                'unidade': item['unidade'],
                'quantidade': item['quantidade'],
                'preco_unitario': item['preco_unitario'],
                'desconto_percentual': item.get('desconto_percentual', 0),
                'subtotal': item['subtotal']
            })
        
        supabase.table('cotacao_itens').insert(itens_para_inserir).execute()
        
        st.success(f"✅ Cotação {cotacao_id} criada com sucesso!")
        return cotacao_id
        
    except Exception as e:
        registrar_erro("Salvar nova cotação", e)
        st.error("Não foi possível enviar sua cotação no momento. Tente novamente.")
        return None

def atualizar_status_cotacao(cotacao_id, novo_status, representante_id):
    """Atualiza status da cotação garantindo isolamento por representante"""
    try:
        supabase.table('cotacoes').update({
            'status': novo_status
        }).eq('id', cotacao_id).eq('representante_id', representante_id).execute()
        st.success(f"Status atualizado para {novo_status}!")
    except Exception as e:
        registrar_erro("Atualizar status da cotação", e)
        st.error("Não foi possível atualizar o status da cotação.")

def aplicar_desconto_geral(cotacao_id, desconto_percentual, representante_id):
    """Aplica desconto geral na cotação garantindo isolamento por representante"""
    try:
        cot = (
            supabase.table('cotacoes')
            .select('*')
            .eq('id', cotacao_id)
            .eq('representante_id', representante_id)
            .single()
            .execute()
        )
        total_original = float(cot.data['total_original'])
        novo_total = total_original * (1 - desconto_percentual / 100)

        supabase.table('cotacoes').update({
            'desconto_geral_percentual': desconto_percentual,
            'total_final': novo_total
        }).eq('id', cotacao_id).eq('representante_id', representante_id).execute()

        st.success(f"Desconto de {desconto_percentual}% aplicado!")
    except Exception as e:
        registrar_erro("Aplicar desconto geral na cotação", e)
        st.error("Não foi possível aplicar o desconto no momento.")

def recalcular_e_salvar_itens(cotacao_id, df_itens_editado, desconto_geral_atual, representante_id):
    """
    1. Confirma que a cotação pertence ao representante logado
    2. Atualiza descontos individuais e subtotais de cada item
    3. Recalcula o total da cotação e salva no banco
    """
    try:
        check = (
            supabase.table('cotacoes')
            .select('id')
            .eq('id', cotacao_id)
            .eq('representante_id', representante_id)
            .execute()
        )
        if not check.data:
            st.error("Cotação não encontrada ou sem permissão de acesso.")
            return False

        soma_subtotais = 0.0

        for _, row in df_itens_editado.iterrows():
            preco = float(row['Preço Unit.'])
            qtd = float(row['Qtde'])
            raw_desc = row.get('Desconto (%)', 0.0)
            desc_item = 0.0 if pd.isna(raw_desc) else float(raw_desc)
            desc_item = max(0.0, min(100.0, desc_item))

            novo_subtotal = (preco * qtd) * (1 - desc_item / 100)
            soma_subtotais += novo_subtotal

            supabase.table('cotacao_itens').update({
                'desconto_percentual': desc_item,
                'subtotal': novo_subtotal
            }).eq('cotacao_id', cotacao_id).eq('codigo', str(row['Código']).strip()).execute()
            
        total_final = soma_subtotais * (1 - desconto_geral_atual / 100)

        supabase.table('cotacoes').update({
            'total_original': soma_subtotais,
            'total_final': total_final,
            'desconto_geral_percentual': desconto_geral_atual
        }).eq('id', cotacao_id).eq('representante_id', representante_id).execute()

        return True
    except Exception as e:
        registrar_erro("Recalcular e salvar itens da cotação", e)
        st.error("Não foi possível salvar os valores recalculados. Tente novamente.")
        return False

# =====================================================================
# GERAÇÃO DE PDF
# =====================================================================

def gerar_pdf_cotacao(cotacao_id, mostrar_precos=True, representante_id=None, cliente_id=None):
    """
    Gera PDF da cotação validando o dono da sessão (representante_id ou cliente_id)
    """
    try:
        query = supabase.table('cotacoes').select('*, clientes(nome, telefone)').eq('id', cotacao_id)

        if representante_id:
            query = query.eq('representante_id', representante_id)
        elif cliente_id:
            query = query.eq('cliente_id', cliente_id)
        else:
            return b''

        cot_response = query.single().execute()
        cotacao = cot_response.data
        if not cotacao:
            return b''

        itens_response = supabase.table('cotacao_itens').select('*').eq('cotacao_id', cotacao_id).execute()
        itens = itens_response.data
        cliente = cotacao.get('clientes', {})
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Cotacao de Produtos', ln=True)
        
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, f"ID: {cotacao['id']}", ln=True)
        pdf.cell(0, 8, f"Cliente: {cliente.get('nome', 'N/A')}", ln=True)
        pdf.cell(0, 8, f"Telefone: {cliente.get('telefone', 'N/A')}", ln=True)
        pdf.cell(0, 8, f"Data: {cotacao['created_at'][:10] if cotacao.get('created_at') else ''}", ln=True)
        pdf.cell(0, 8, f"Forma de recebimento: {cotacao.get('forma_recebimento', 'N/A')}", ln=True)
        
        pdf.ln(4)
        
        if mostrar_precos:
            total_final = float(cotacao.get('total_final', 0))
            soma_subtotais = float(cotacao.get('total_original', 0))
            desconto_extra_pct = float(cotacao.get('desconto_geral_percentual', 0))
            
            total_bruto_real = 0.0
            for item in itens:
                p = float(item.get('preco_unitario', 0))
                q = float(item.get('quantidade', 0))
                total_bruto_real += (p * q)
            
            total_desc_itens = total_bruto_real - soma_subtotais
            total_desc_extra = soma_subtotais - total_final
            
            pdf.cell(0, 8, f"Total Real (Sem descontos): R$ {total_bruto_real:.2f}", ln=True)
            
            if total_desc_itens > 0.01:
                pdf.set_text_color(200, 0, 0)
                pdf.cell(0, 8, f"Desconto nos Itens: - R$ {total_desc_itens:.2f}", ln=True)
                pdf.set_text_color(0, 0, 0)
                
            if total_desc_extra > 0.01:
                pdf.set_text_color(200, 0, 0)
                msg_extra = f"Desconto Extra: - R$ {total_desc_extra:.2f}"
                if desconto_extra_pct > 0:
                    msg_extra += f" ({desconto_extra_pct:.1f}%)"
                pdf.cell(0, 8, msg_extra, ln=True)
                pdf.set_text_color(0, 0, 0)
            
            pdf.ln(2)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f"TOTAL FINAL: R$ {total_final:.2f}", ln=True)
            pdf.set_font('Arial', '', 11)
            
        else:
            pdf.cell(0, 8, "Valores a serem informados pelo representante.", ln=True)
        
        pdf.ln(4)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(22, 8, 'Cod.', border=1)
        pdf.cell(66, 8, 'Produto', border=1)
        pdf.cell(12, 8, 'Un.', border=1)
        pdf.cell(14, 8, 'Qtd', border=1)
        
        if mostrar_precos:
            pdf.cell(23, 8, 'Unit.', border=1)
            pdf.cell(18, 8, 'Desc.', border=1)
            pdf.cell(30, 8, 'Subtotal', border=1, ln=True)
        else:
            pdf.cell(71, 8, 'Precos a informar', border=1, ln=True)
        
        pdf.set_font('Arial', '', 9)
        for item in itens:
            pdf.cell(22, 6, str(item.get('codigo', ''))[:10], border=1)
            pdf.cell(66, 6, str(item.get('produto', ''))[:32], border=1)
            pdf.cell(12, 6, str(item.get('unidade', ''))[:5], border=1)
            pdf.cell(14, 6, str(item.get('quantidade', '')), border=1)
            
            if mostrar_precos:
                preco = float(item.get('preco_unitario', 0))
                desc_item = float(item.get('desconto_percentual') or 0)
                subtotal = float(item.get('subtotal', 0))
                desc_txt = f"{desc_item:.1f}%" if desc_item > 0 else "-"
                
                pdf.cell(23, 6, f"{preco:.2f}", border=1)
                pdf.cell(18, 6, desc_txt, border=1)
                pdf.cell(30, 6, f"{subtotal:.2f}", border=1, ln=True)
            else:
                pdf.cell(71, 6, '-', border=1, ln=True)
        
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 8)
        pdf.multi_cell(
            0,
            5,
            'Observacao: Os precos apresentados sao referenciais e estao sujeitos a alteracao ate o fechamento e aprovacao do pedido pelo representante.'
        )
        pdf.ln(2)
        pdf.set_font('Arial', '', 8)
        pdf.cell(0, 8, 'Gerado via RC Online', ln=True, align='R')
        
        return pdf.output(dest='S').encode('latin-1', errors='replace')
        
    except Exception as e:
        registrar_erro("Gerar PDF da cotação", e)
        st.error("Não foi possível gerar o PDF desta cotação no momento.")
        return b''
    
# =====================================================================
# PÁGINAS DA APLICAÇÃO - REPRESENTANTE
# =====================================================================

def pagina_dashboard(representante_id):
    """Painel Gerencial do representante"""
    st.title("📊 Painel Gerencial")
    
    # --- CÁLCULO DE DADOS ---
    clientes = carregar_clientes(representante_id)
    produtos = carregar_produtos(representante_id)
    cotacoes = carregar_cotacoes(representante_id)
    
    # --- LINHA 1: INDICADORES GERAIS ---
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total de Clientes", len(clientes))
    with col2: st.metric("Produtos Ativos", len(produtos))
    with col3: st.metric("Total de Pedidos", len(cotacoes))
    with col4:
        if not cotacoes.empty:
            vendas = cotacoes[cotacoes['status'] == 'APROVADA']['total_final'].sum()
            st.metric("Vendas Aprovadas", f"R$ {vendas:,.2f}")
        else:
            st.metric("Vendas Aprovadas", "R$ 0,00")

    st.markdown("---")

    # --- LINHA 2: GESTÃO DE COTAÇÕES ---
    st.subheader("🚦 Status dos Pedidos")
    c1, c2, c3 = st.columns(3)
    
    if not cotacoes.empty:
        # Converter a coluna de data para datetime pandas
        cotacoes['data_dt'] = pd.to_datetime(cotacoes['created_at'])
        
        pendentes = cotacoes[cotacoes['status'] == 'PENDENTE']
        aprovadas = cotacoes[cotacoes['status'] == 'APROVADA']
        canceladas = cotacoes[cotacoes['status'] == 'CANCELADA']
        
        with c1:
            st.info(f"🕒 **Pendentes: {len(pendentes)}**")
            # --- CORREÇÃO DO CÁLCULO DE TEMPO ---
            if not pendentes.empty:
                mais_antiga = pendentes['data_dt'].min()
                
                # Pegamos o agora em UTC para bater com o horário do banco
                agora = datetime.now(timezone.utc)
                
                # --- CORREÇÃO DO ERRO ---
                # Removemos a informação de fuso horário de AMBOS para permitir a subtração
                
                # 1. Remove fuso da data do banco (se tiver)
                if mais_antiga.tzinfo:
                    mais_antiga = mais_antiga.tz_localize(None)
                
                # 2. Remove fuso do agora (ESSA LINHA QUE FALTAVA)
                agora = agora.replace(tzinfo=None)
                
                # Agora ambos são "naive" (sem fuso) e podem ser subtraídos
                delta = agora - mais_antiga
                
                dias = delta.days
                horas = delta.seconds // 3600
                minutos = (delta.seconds % 3600) // 60
                
                if dias > 0:
                    st.caption(f"⚠️ A mais antiga aguarda há **{dias}d {horas}h**")
                elif horas > 0:
                    st.caption(f"⚠️ A mais antiga aguarda há **{horas}h {minutos}min**")
                else:
                    st.caption(f"⚠️ A mais antiga aguarda há **{minutos} min**")
            else:
                st.caption("Nenhuma pendência! 🎉")

        with c2: st.success(f"✅ **Aprovadas: {len(aprovadas)}**")
        with c3: st.error(f"❌ **Canceladas: {len(canceladas)}**")
    else:
        st.info("Nenhuma cotação para analisar.")

    st.markdown("---")
    
    # --- LINHA 3: TABELA DETALHADA ---
    if not cotacoes.empty:
        st.subheader("📋 Listagem Recente")
        df_display = cotacoes.copy()
        
        # 1. Nome Cliente
        if 'clientes' in df_display.columns:
            df_display['cliente_nome'] = df_display['clientes'].apply(lambda x: x.get('nome', 'N/A') if isinstance(x, dict) else 'N/A')
        
        # 2. Formatar Data (CORREÇÃO DE FUSO -3h)
        # Usamos pd.Timedelta(-3, unit='h') para ajustar visualmente para o Brasil
        df_display['Data'] = (df_display['data_dt'] - pd.Timedelta(hours=3)).dt.strftime('%d/%m/%Y %H:%M')
        
        df_display['Valor Final'] = df_display['total_final'].apply(lambda x: f"R$ {float(x):.2f}" if x else "R$ 0.00")
        
        df_final = df_display[['id', 'Data', 'cliente_nome', 'status', 'Valor Final']].rename(columns={
            'id': 'ID Pedido', 'cliente_nome': 'Cliente', 'status': 'Status'
        })
        
        st.dataframe(df_final, width='stretch', hide_index=True)

def pagina_upload_tabela_precos(representante_id):
    """Página para upload da tabela de preços com validação robusta"""
    st.subheader("📤 Gerenciar Tabela de Preços")

    # Exibe mensagem salva antes do rerun (não some em 2 segundos)
    feedback_sync = st.session_state.pop("feedback_sincronizacao", None)
    if feedback_sync:
        nivel, texto = feedback_sync
        if nivel == "warning":
            st.warning(texto)
        else:
            st.success(texto)
    # ========== STATUS ATUAL ==========
    produtos = carregar_produtos(representante_id)

    if not produtos.empty:
        col_data = 'updated_at' if 'updated_at' in produtos.columns else (
            'created_at' if 'created_at' in produtos.columns else None
        )

        if col_data:
            ultima_atualizacao = pd.to_datetime(produtos[col_data]).max()
            if getattr(ultima_atualizacao, "tzinfo", None):
                ultima_atualizacao = ultima_atualizacao.tz_localize(None)
            ultima_atualizacao = ultima_atualizacao - pd.Timedelta(hours=3)
            data_fmt = ultima_atualizacao.strftime('%d/%m/%Y às %H:%M')
            st.success(f"✅ Tabela Ativa (Última atualização: **{data_fmt}**)")
        else:
            st.success("✅ Tabela Ativa")

        # Produtos (quantidade) — simples e direto
        st.write(f"**Produtos na tabela:** {len(produtos)}")

        # (Opcional) controle de falhas: preços zerados/ausentes (sem mini-dashboard)
        cols_calc = ['preco_retira', 'preco_entrega']
        cols_existentes = [c for c in cols_calc if c in produtos.columns]
        if cols_existentes:
            qtd_sem_preco = (produtos[cols_existentes].fillna(0).astype(float) == 0).sum().sum()
            if qtd_sem_preco > 0:
                st.warning(f"⚠️ Existem **{qtd_sem_preco}** preços zerados/ausentes na tabela.")

        # Visualização da tabela atual
        with st.expander("👁️ Visualizar tabela atual", expanded=False):
            cols_view = ['codigo', 'produto', 'unidade', 'preco_retira', 'preco_entrega']
            cols_disponiveis = [c for c in cols_view if c in produtos.columns]
            st.dataframe(produtos[cols_disponiveis].head(50), width="stretch")

    else:
        st.info("📋 Nenhuma tabela de preços cadastrada ainda.")

    # ========== UPLOAD DE NOVO ARQUIVO ==========
    st.markdown("---")
    st.markdown("### 📥 Carregar Nova Tabela de Preços")

    arquivo_upload = st.file_uploader(
        "Selecione o arquivo",
        type=['csv', 'xlsx', 'xls'],
        help="Limit 200MB per file • CSV, XLSX, XLS"
    )

    st.caption("Formatos suportados: CSV (.csv), Excel (.xlsx, .xls)")

    with st.expander("ℹ️ Regras do arquivo (colunas)", expanded=False):
        st.markdown("""
        **Colunas obrigatórias:**
        - `Código` (ou `codigo`, `Code`, `SKU`)
        - `Produto` (ou `Nome`, `Descrição`)

        **Colunas recomendadas:**
        - `Unidade` (UN, KG, etc)
        - `Retira` ou `Preço Retirada` (preço sem frete)
        - `Entrega` ou `Preço Entrega` (preço com frete)

        **Nota:** O sistema aceita variações de nomes de colunas e formata automaticamente.
        """)

    if arquivo_upload is not None:
        # ========== PROCESSAR E VALIDAR ==========
        df_processado = processar_arquivo_produtos(arquivo_upload)

        if df_processado is not None:
            st.success("✅ Arquivo processado com sucesso e pronto para sincronizar!")

            # Resumo/preview da tabela carregada
            exibir_preview_dados(df_processado)

           # Alerta no lugar certo (perto do botão)
            st.warning(
                "⚠️ Ao atualizar, a tabela ativa passa a ser a do arquivo enviado. "
                "Itens que não existirem mais no arquivo serão removidos da tabela do dia."
            )

            # Calcula impacto real por código ANTES de liberar o botão
            impacto = calcular_impacto_sincronizacao(supabase, df_processado, representante_id)
            exige_confirmacao = impacto['exige_confirmacao']
            confirmou_exclusao = False

            if exige_confirmacao:
                st.error(
                    f"🚨 Atenção: **{impacto['qtd_removiveis']}** de **{impacto['total_atual']}** produtos atuais "
                    "serão removidos do catálogo (mais de 50%)."
                )
                confirmou_exclusao = st.checkbox(
                    f"Confirmo a remoção de {impacto['qtd_removiveis']} produtos do catálogo",
                    value=False,
                    key="chk_confirmar_reducao_catalogo"
                )

            pode_sincronizar = (not exige_confirmacao) or confirmou_exclusao

            # ========== CONFIRMAÇÃO ==========
            st.markdown("---")
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write("")

            with col2:
                if st.button(
                    "🚀 Atualizar Dados",
                    type="primary",
                    key="btn_sincronizar",
                    disabled=not pode_sincronizar
                ):
                    with st.spinner("⏳ Sincronizando produtos..."):
                        sucesso, mensagem, nivel = sincronizar_produtos_supabase(
                            supabase=supabase,
                            df=df_processado,
                            tabela='produtos',
                            limpar_antes=True,
                            representante_id=representante_id,
                            confirmar_exclusao_em_massa=confirmou_exclusao
                        )
                    if sucesso:
                        carregar_catalogo_representante.clear()
                        st.session_state["feedback_sincronizacao"] = (nivel, mensagem)
                        st.session_state['recarregar_pagina'] = True
                        st.rerun()

                    else:
                        logger.error(f"Falha ao sincronizar tabela de preços: {mensagem}")
                        st.error(mensagem)


def pagina_upload_clientes(representante_id):
    """Página para upload de clientes"""
    st.subheader("📤 Gerenciar Clientes")
    
    # Verificar se já existem clientes
    clientes = carregar_clientes(representante_id)
    
    if not clientes.empty:
        st.success("✅ Você já possui clientes cadastrados")
        st.info(f"Clientes cadastrados: {len(clientes)}")
        
        with st.expander("👁️ Visualizar clientes atuais"):
            colunas_exibir = ['nome', 'cnpj', 'telefone', 'cidade']
            # Garante que as colunas sejam tratadas como string para não quebrar a tabela
            df_show = clientes.copy()
            for col in ['cnpj', 'telefone']:
                if col in df_show.columns:
                    df_show[col] = df_show[col].astype(str).replace('nan', '')
            
            colunas_disponiveis = [c for c in colunas_exibir if c in df_show.columns]
            st.dataframe(df_show[colunas_disponiveis], hide_index=True)
        
        st.warning("⚠️ Carregar uma nova planilha substituirá os dados atuais")
    else:
        st.info("📋 Nenhum cliente cadastrado ainda")
    
    st.markdown("---")
    st.markdown("### 📥 Carregar Nova Planilha de Clientes")
    st.markdown("""
    **Formato esperado do arquivo Excel (.xlsx):**
    - Colunas obrigatórias: `NOME`, `DISTANCIA`, `CNPJ` ou `TELEFONE`
    - Colunas opcionais: `CIDADE`, `VISUALIZAPRECO`
    """)
    
    arquivo_upload = st.file_uploader(
        "Selecione o arquivo Excel com os clientes",
        type=['xlsx'],
        help="Arquivo Excel (.xlsx) com dados dos clientes"
    )
    
    if arquivo_upload is not None:
        try:
            # Preview - CORREÇÃO AQUI: dtype=str força ler tudo como texto
            df_preview = pd.read_excel(arquivo_upload, dtype=str)
            
            # Normalizar cabeçalhos para evitar erro de 'NOME' vs 'Nome'
            df_preview.columns = [str(c).strip().upper() for c in df_preview.columns]
            
            if 'NOME' in df_preview.columns:
                 df_preview = df_preview[df_preview['NOME'].notna()].copy()
            
            st.success("✅ Arquivo carregado com sucesso!")
            st.info(f"Total de clientes: {len(df_preview)}")
            
            # Validar coluna obrigatória
            if 'NOME' not in df_preview.columns:
                st.error("❌ Coluna obrigatória faltando: NOME")
            else:
                st.success("✅ Coluna NOME presente")
            
            with st.expander("👁️ Pré-visualizar dados"):
                # Preenche valores nulos com vazio para não mostrar "NaN"
                st.dataframe(df_preview.fillna(""), hide_index=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Confirmar e Salvar Clientes", type="primary", key="btn_confirmar_clientes"):
                    arquivo_upload.seek(0)
                    upload_clientes_excel(arquivo_upload, representante_id)
                    # Pequeno delay para garantir que deu tempo de ver a mensagem
                    import time
                    time.sleep(2)
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancelar", key="btn_cancelar_clientes"):
                    st.rerun()
                    
        except Exception as e:
            registrar_erro("Pré-visualização do arquivo de clientes", e)
            st.error("Não foi possível ler o arquivo enviado. Verifique se está no formato correto (Excel .xlsx).")
            
def pagina_gestao_clientes(representante_id):
    """Página de gestão de clientes (Cadastro e Edição)"""
    st.subheader("👥 Gestão de Clientes")
    
    # =========================================================
    # 1. CADASTRO MANUAL DE NOVO CLIENTE
    # =========================================================
    with st.expander("➕ Cadastrar Novo Cliente Manualmente", expanded=False):
        with st.form("form_novo_cliente"):
            st.write("Preencha os dados abaixo para cadastrar um cliente individualmente.")
            
            c1, c2 = st.columns(2)
            with c1:
                nome_novo = st.text_input("Nome do Cliente / Razão Social", key="nome_cliente_novo")
                cnpj_novo = st.text_input("CNPJ (apenas números)", key="cnpj_cliente_novo")
                telefone_novo = st.text_input("Telefone (com DDD)", key="telefone_cliente_novo")
            
            with c2:
                cidade_novo = st.text_input("Cidade", key="cidade_cliente_novo")
                distancia_novo = st.number_input("Distância (KM)", min_value=0, value=0, help="Define a tabela de preço automaticamente", key="distancia_cliente_novo")
                pode_ver_preco_novo = st.toggle("Pode visualizar preços?", value=True)
                permite_retirada_novo = st.toggle("Pode retirar no centro de distribuição?", value=False)
            
            submitted = st.form_submit_button("Cadastrar Cliente")
            
            if submitted:
                if not nome_novo:
                    st.error("O campo Nome é obrigatório.")
                elif not (cnpj_novo or telefone_novo):
                    st.error("É necessário informar ao menos CNPJ ou Telefone.")
                else:
                    # --- NOVA LÓGICA DE DISTÂNCIA NO MANUAL ---
                    dist = int(distancia_novo)
                    coluna_preco = 'preco_entrega' # Padrão (0-100km)
                    
                    if dist < 100: coluna_preco = 'preco_entrega'
                    elif dist < 200: coluna_preco = 'preco_100a199km'
                    elif dist < 300: coluna_preco = 'preco_200a299km'
                    elif dist < 400: coluna_preco = 'preco_300a399km'
                    elif dist <= 500: coluna_preco = 'preco_acima400km'
                    elif dist <= 600: coluna_preco = 'preco_acima500km'
                    else: coluna_preco = 'preco_acima600km'
                    # -----------------------------------------
                    
                    try:
                        supabase.table('clientes').insert({
                            'representante_id': representante_id,
                            'nome': nome_novo.upper(),
                            'cnpj': so_digitos(cnpj_novo),
                            'telefone': so_digitos(telefone_novo),
                            'cidade': cidade_novo,
                            'distancia_km': dist,
                            'coluna_preco': coluna_preco,
                            'visualiza_preco': pode_ver_preco_novo,
                            'permite_retirada': permite_retirada_novo,
                            'status_cliente': 'CLIENTE',
                            'senha_hash': None
                        }).execute()
                        
                        st.success(f"✅ Cliente {nome_novo} cadastrado! Ele já pode criar sua própria senha no 1º acesso.")
                        st.rerun()
                    except Exception as e:
                        registrar_erro("Cadastro manual de cliente", e)
                        st.error("Não foi possível cadastrar o cliente. Verifique se o CNPJ já não existe ou tente novamente.")
    st.markdown("---")
    
    # =========================================================
    # 2. LISTAGEM E EDIÇÃO
    # =========================================================
    
    df = carregar_clientes(representante_id)
    
    if df.empty:
        st.info("📋 Nenhum cliente cadastrado ainda")
        return
    
    # Filtro por nome
    filtro_nome = st.text_input(
        "🔍 Buscar cliente por nome, CNPJ ou cidade", 
        "",
        key="busca_cli_gestao" 
    )
    
    df_view = df.copy()
    if filtro_nome.strip():
        termo = filtro_nome.strip().lower()
        # Filtra em várias colunas
        df_view = df_view[
            df_view['nome'].str.lower().str.contains(termo, na=False) | 
            df_view['cnpj'].str.contains(termo, na=False) |
            df_view['cidade'].str.lower().str.contains(termo, na=False)
        ]
    
    st.write(f"**Clientes encontrados:** {len(df_view)}")
    
    # Cabeçalho visual da tabela
    st.markdown("""
    <div style="display: flex; font-weight: bold; padding: 10px 0; border-bottom: 2px solid #ddd;">
        <div style="flex: 3;">Dados do Cliente</div>
        <div style="flex: 2;">Permissões</div>
        <div style="flex: 2;">Ações (Reset Senha)</div>
    </div>
    """, unsafe_allow_html=True)
    
    for idx, row in df_view.iterrows():
        # Usamos container para organizar as linhas
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])
            
            with col1:
                st.write(f"🏢 **{row['nome']}**")
                info = []
                if row.get('cnpj'): info.append(f"CNPJ: {row['cnpj']}")
                if row.get('telefone'): info.append(f"Tel: {row['telefone']}")
                info.append(f"{row.get('distancia_km', 0)} km")
                st.caption(" | ".join(info))
                
            with col2:
                # Toggle de visualização de preço
                valor_atual = bool(row.get('visualiza_preco', True))
                novo_valor = st.toggle(
                    "Ver Preços",
                    value=valor_atual,
                    key=f"visupreco_{row['id']}"
                )
                
                # Se mudou o valor, salva imediatamente no banco validando o representante
                if novo_valor != valor_atual:
                    atualizar_visualiza_preco(row['id'], novo_valor, representante_id)
                    st.toast(f"Permissão de preços de {row['nome']} atualizada!")

                # Toggle de permissão de retirada (desabilitada por padrão)
                retirada_atual = bool(row.get('permite_retirada', False))
                nova_retirada = st.toggle(
                    "Permite Retirada",
                    value=retirada_atual,
                    key=f"permiteretirada_{row['id']}"
                )

                if nova_retirada != retirada_atual:
                    atualizar_permite_retirada(row['id'], nova_retirada, representante_id)
                    st.toast(f"Permissão de retirada de {row['nome']} atualizada!")
            
            with col3:
                # Botão de Reset de Senha (isolado por representante_id)
                if st.button("🔄 Resetar Senha", key=f"reset_{row['id']}"):
                    try:
                        supabase.table('clientes').update({
                            'senha_hash': None
                        }).eq('id', row['id']).eq('representante_id', representante_id).execute()
                        
                        st.success(f"Senha de {row['nome']} limpa! O cliente já pode cadastrar uma nova senha no 1º acesso.")
                    except Exception as e:
                        registrar_erro("Reset de senha do cliente", e)
                        st.error("Não foi possível resetar a senha no momento. Tente novamente.")
            st.markdown("---")

def pagina_gerenciar_cotacoes(representante_id):
    """Página para gerenciar cotações"""
    st.subheader("📋 Gerenciar Cotações")
    
    cotacoes = carregar_cotacoes(representante_id)
    
    if cotacoes.empty:
        st.info("📋 Nenhuma cotação registrada ainda")
        return
    
    filtro_status = st.selectbox("Filtrar por status", ["TODAS", "PENDENTE", "APROVADA", "CANCELADA"], key="filtro_status_cotacoes")
    
    df_view = cotacoes.copy()
    if filtro_status != "TODAS":
        df_view = df_view[df_view['status'] == filtro_status]
    
    df_view = df_view.sort_values('created_at', ascending=False)
    st.write(f"**Total de cotações:** {len(df_view)}")
    
    for _, cot in df_view.iterrows():
        cliente_nome = cot.get('clientes', {}).get('nome', 'N/A') if isinstance(cot.get('clientes'), dict) else 'N/A'
        telefone = cot.get('clientes', {}).get('telefone', 'N/A') if isinstance(cot.get('clientes'), dict) else 'N/A'
        
        data_criacao = cot.get('created_at')
        if data_criacao:
            dt_obj = pd.to_datetime(data_criacao)
            if dt_obj.tzinfo: dt_obj = dt_obj.tz_localize(None)
            dt_obj = dt_obj - pd.Timedelta(hours=3)
            data_fmt = dt_obj.strftime('%d/%m/%Y %H:%M')
        else:
            data_fmt = 'N/A'
        
        # --- CÁLCULOS DETALHADOS PARA VISUALIZAÇÃO ---
        # Carregamos os itens aqui para poder somar o bruto
        itens_calc = carregar_itens_cotacao(cot['id'])
        
        total_real_bruto = 0.0
        total_desc_itens = 0.0
        total_desc_extra = 0.0
        total_final = float(cot.get('total_final', 0))
        
        if not itens_calc.empty:
            # Calcula o bruto (sem desconto) linha a linha
            itens_calc['bruto_item'] = itens_calc['preco_unitario'] * itens_calc['quantidade']
            total_real_bruto = itens_calc['bruto_item'].sum()
            
            # O que está salvo em 'total_original' na cotação é a soma dos subtotais (já com desc. item)
            soma_subtotais = float(cot.get('total_original', 0))
            
            # Diferenças
            total_desc_itens = total_real_bruto - soma_subtotais
            total_desc_extra = soma_subtotais - total_final
        # ---------------------------------------------

        with st.expander(f"📄 Cotação {cot['id']} - {cliente_nome} - {cot['status']}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Cliente:** {cliente_nome}")
                st.markdown(f"**Data:** {data_fmt}")
                st.markdown(f"**Entrega:** {cot.get('forma_recebimento', 'N/A')}")
            
            with col2:
                # --- VISUALIZAÇÃO SOLICITADA (SEG-7: valores sanitizados) ---
                st.metric("Total Final", f"R$ {total_final:,.2f}")
                desc_geral_pct = float(cot.get('desconto_geral_percentual') or 0)
                
                st.markdown(f"""
                <div style="font-size: 12px; color: #555;">
                <b>Total Real (Sem descontos):</b> R$ {total_real_bruto:,.2f}<br>
                <span style="color: #d9534f;">▼ Desc. nos Itens: R$ {total_desc_itens:,.2f}</span><br>
                <span style="color: #d9534f;">▼ Desc. Extra ({escapar_html(f"{desc_geral_pct:g}")}%): R$ {total_desc_extra:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)
                # -------------------------------
                
            st.markdown("---")
            
            st.markdown("**📦 Editor de Itens e Descontos**")
            # Usamos o dataframe que já carregamos lá em cima
            itens = itens_calc
            
            if not itens.empty:
                df_edit = itens.copy()
                if 'desconto_percentual' not in df_edit.columns: df_edit['desconto_percentual'] = 0.0
                df_edit['desconto_percentual'] = df_edit['desconto_percentual'].fillna(0.0).astype(float)
                
                df_edit = df_edit[['codigo', 'produto', 'quantidade', 'preco_unitario', 'desconto_percentual', 'subtotal']]
                df_edit = df_edit.rename(columns={
                    'codigo': 'Código', 'produto': 'Produto', 'quantidade': 'Qtde',
                    'preco_unitario': 'Preço Unit.', 'desconto_percentual': 'Desconto (%)', 'subtotal': 'Subtotal'
                })
                
                df_editado = st.data_editor(
                    df_edit,
                    column_config={
                        "Código": st.column_config.TextColumn(disabled=True, width="small"),
                        "Produto": st.column_config.TextColumn(disabled=True, width="medium"), 
                        "Qtde": st.column_config.NumberColumn(disabled=True, width="small"),
                        "Preço Unit.": st.column_config.NumberColumn(format="R$ %.2f", disabled=True, width="small"),
                        "Subtotal": st.column_config.NumberColumn(format="R$ %.2f", disabled=True, width="small"),
                        "Desconto (%)": st.column_config.NumberColumn(min_value=0, max_value=100, step=0.5, format="%.1f%%", width="small")
                    },
                    hide_index=True, width='stretch', key=f"editor_{cot['id']}"
                )
                
                c_desc, c_save = st.columns([1, 2])
                with c_desc:
                    desc_geral = float(cot.get('desconto_geral_percentual', 0))
                    novo_desconto_geral = st.number_input("Desconto Extra no Total (%)", min_value=0.0, max_value=100.0, value=desc_geral, step=0.5, key=f"desc_geral_{cot['id']}")
                with c_save:
                    st.write("")
                    st.write("")
                    if st.button("💾 Salvar Tudo", type="primary", key=f"btn_save_all_{cot['id']}"):
                        sucesso = recalcular_e_salvar_itens(cot['id'], df_editado, novo_desconto_geral, representante_id)
                        if sucesso:
                            st.success("Cotação recalculada e salva com sucesso!")
                            st.rerun()
            else:
                st.warning("⚠️ Esta cotação não possui itens registrados.")
                if st.button("🗑️ Excluir esta cotação vazia", key=f"btn_del_cot_{cot['id']}"):
                    supabase.table('cotacoes').delete().eq('id', cot['id']).eq('representante_id', representante_id).execute()
                    st.success("Cotação excluída.")
                    st.rerun()

            st.markdown("---")
            c_status, c_acoes = st.columns([1, 1])
            
            with c_status:
                st.markdown("**Alterar Status**")
                status_opcoes = ["PENDENTE", "APROVADA", "CANCELADA"]
                idx_atual = status_opcoes.index(cot['status']) if cot['status'] in status_opcoes else 0
                col_st_1, col_st_2 = st.columns([2, 1])
                with col_st_1:
                    novo_status = st.selectbox("Status", status_opcoes, index=idx_atual, key=f"status_{cot['id']}", label_visibility="collapsed")
                with col_st_2:
                    if st.button("Atualizar", key=f"btn_status_{cot['id']}"):
                        atualizar_status_cotacao(cot['id'], novo_status, representante_id)
                        st.rerun()
            
            with c_acoes:
                st.markdown("**Ações**")
                col_ac_1, col_ac_2 = st.columns(2)
                with col_ac_1:
                    pdf_bytes = gerar_pdf_cotacao(cot['id'], True, representante_id=representante_id)
                    st.download_button(label="📄 Baixar PDF", data=pdf_bytes, file_name=f"cotacao_{cot['id']}.pdf", mime="application/pdf", key=f"pdf_{cot['id']}")
                with col_ac_2:
                    if telefone and telefone != "N/A":
                        tel_limpo = so_digitos(telefone)
                        if tel_limpo:
                            texto_msg = f"Olá! Estou analisando sua cotação *{cot['id']}*."
                            link_whats = f"https://wa.me/55{tel_limpo}?text={texto_msg}"
                            st.link_button(label="💬 WhatsApp", url=link_whats, type="secondary")

def pagina_administradora():
    """Área restrita da administradora para gestão de representantes"""
    local_css()

    if 'admin_logada' not in st.session_state:
        st.session_state.admin_logada = False

    if not st.session_state.admin_logada:
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        with col_centro:
            st.markdown('<div class="main-header">Área da Administradora</div>', unsafe_allow_html=True)
            with st.form("form_login_admin"):
                senha_admin = st.text_input("Senha da Administradora", type="password")
                if st.form_submit_button("ENTRAR", width="stretch"):
                    bloqueado, msg_bloqueio = verificar_bloqueio_login("admin_principal", "ADMIN")
                    if bloqueado:
                        st.error(msg_bloqueio)
                    else:
                        senha_correta = st.secrets.get("ADMIN_PASSWORD", "")
                        if senha_correta and hmac.compare_digest(
                            str(senha_admin).encode("utf-8"),
                            str(senha_correta).encode("utf-8")
                        ):
                            limpar_tentativas_login("admin_principal", "ADMIN")
                            st.session_state.admin_logada = True
                            st.rerun()
                        else:
                            msg_falha = registrar_falha_login("admin_principal", "ADMIN")
                            st.error(f"❌ {msg_falha}")
        return

    # --- ÁREA LOGADA DA ADMINISTRADORA ---
    st.sidebar.title("Painel Administradora")
    if st.sidebar.button("Sair da Administração"):
        st.session_state.admin_logada = False
        st.rerun()

    st.title("🔐 Gestão de Representantes")
    st.write("Cadastre novos representantes autorizados a acessar o sistema.")

    with st.expander("➕ Cadastrar Novo Representante", expanded=True):
        with st.form("form_cadastro_rep_admin"):
            nome_rep = st.text_input("Nome Completo *")
            email_rep = st.text_input("E-mail de Acesso *")
            telefone_rep = st.text_input("Telefone / WhatsApp (com DDD)")
            pass_rep = st.text_input("Senha Inicial *", type="password")
            pass_rep_conf = st.text_input("Confirme a Senha *", type="password")

            if st.form_submit_button("CADASTRAR REPRESENTANTE", type="primary"):
                if not (nome_rep and email_rep and pass_rep):
                    st.error("❌ Preencha Nome, E-mail e Senha.")
                elif len(pass_rep) < 6:
                    st.error("❌ A senha deve ter pelo menos 6 caracteres.")
                elif pass_rep != pass_rep_conf:
                    st.error("❌ As senhas não coincidem.")
                else:
                    sucesso, msg = criar_representante_admin(nome_rep, email_rep, pass_rep, telefone_rep)
                    if sucesso:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

    st.markdown("---")
    st.subheader("📋 Representantes Cadastrados")
    try:
        reps = supabase.table('representantes').select('id, nome, email, telefone, created_at').execute()
        if reps.data:
            df_reps = pd.DataFrame(reps.data)
            st.dataframe(df_reps[['nome', 'email', 'telefone']], hide_index=True, width="stretch")
        else:
            st.info("Nenhum representante cadastrado.")
    except Exception as e:
        registrar_erro("Listar representantes na área da administradora", e)
        st.error("Não foi possível carregar a lista de representantes no momento.")


def pagina_representante():
    """Página principal do representante"""
    local_css()
    
    if 'representante_logado' not in st.session_state:
        st.session_state.representante_logado = None
    
    if st.session_state.representante_logado is None:
        # Tela apenas de Login (cadastro público removido no SEG-3)
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        
        with col_centro:
            st.markdown('<div class="main-header">Área do Representante</div>', unsafe_allow_html=True)
            st.info("ℹ️ Acesso restrito a representantes cadastrados pela administração.")
            
            with st.form("form_login_rep"):
                st.subheader("Acesse o sistema")
                login_email = st.text_input("E-mail", key="rep_email")
                login_senha = st.text_input("Senha", type="password", key="rep_senha")
                
                if st.form_submit_button("ENTRAR", width="stretch"):
                    if login_email and login_senha:
                        usuario, msg = autenticar_representante(login_email, login_senha)
                        if usuario is not None:
                            st.session_state.representante_logado = usuario
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos")
        return
    
    # Representante logado
    rep = st.session_state.representante_logado
    representante_id = rep['id']

    # =========================================================
    # TRAVA DE PRIMEIRO ACESSO (SEG-12)
    # =========================================================
    if rep.get('trocar_senha', False):
        st.sidebar.title(f"Olá, {rep.get('nome', 'Representante')}!")
        if st.sidebar.button("Sair"):
            st.session_state.representante_logado = None
            st.rerun()

        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        with col_centro:
            st.markdown('<div class="main-header">Primeiro Acesso</div>', unsafe_allow_html=True)
            st.warning("🔐 Por segurança, você precisa criar uma senha pessoal antes de acessar o painel.")

            with st.form("form_troca_senha_primeiro_acesso"):
                senha_provisoria_atual = st.text_input("Senha Provisória Atual", type="password")
                nova_senha = st.text_input("Nova Senha Pessoal (mínimo 6 caracteres)", type="password")
                confirma_nova_senha = st.text_input("Confirme a Nova Senha Pessoal", type="password")

                if st.form_submit_button("SALVAR NOVA SENHA E ENTRAR", type="primary", width="stretch"):
                    if not (senha_provisoria_atual and nova_senha and confirma_nova_senha):
                        st.error("❌ Preencha todos os campos.")
                    elif len(nova_senha) < 6:
                        st.error("❌ A nova senha deve ter pelo menos 6 caracteres.")
                    elif nova_senha == senha_provisoria_atual:
                        st.error("❌ A nova senha precisa ser diferente da senha provisória.")
                    elif nova_senha != confirma_nova_senha:
                        st.error("❌ A confirmação da nova senha não coincide.")
                    else:
                        usuario_ok, _ = autenticar_representante(rep.get('email', ''), senha_provisoria_atual)
                        if usuario_ok is None:
                            st.error("❌ A senha provisória atual está incorreta.")
                        else:
                            sucesso, msg = atualizar_senha_representante(representante_id, nova_senha)
                            if sucesso:
                                st.session_state.representante_logado['trocar_senha'] = False
                                st.success("✅ Senha definida com sucesso! Liberando seu painel...")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
        return
    # =========================================================
    
    st.sidebar.title(f"Olá, {rep.get('nome', 'Representante')}!")
    menu = st.sidebar.radio(
        "Menu",
        ["Painel Gerencial", "Importar Tabela de Preços", "Importar Clientes", "Gestão de Clientes", "Gerenciar Cotações"]
    )
    
    if st.sidebar.button("Sair"):
        st.session_state.representante_logado = None
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <small style='color: white; font-size: 10px; opacity: 0.7;'>
    Contato e Suporte<br>
    atendimento@beccai.com.br<br>
    (11) 95451.9325<br>
    Desenvolvido por www.beccai.com.br<br>
    ---<br>
    Versão 2.0 | Janeiro 2026
    </small>
    """, unsafe_allow_html=True)
    
    if menu == "Painel Gerencial":
        pagina_dashboard(representante_id)
    elif menu == "Importar Tabela de Preços":
        pagina_upload_tabela_precos(representante_id)
    elif menu == "Importar Clientes":
        pagina_upload_clientes(representante_id)
    elif menu == "Gestão de Clientes":
        pagina_gestao_clientes(representante_id)
    elif menu == "Gerenciar Cotações":
        pagina_gerenciar_cotacoes(representante_id)

# =====================================================================
# PÁGINAS DA APLICAÇÃO - CLIENTE
# =====================================================================

def pagina_nova_cotacao(cliente):
    """Interface de criação de cotação pelo cliente"""
    representante_id = cliente['representante_id']

    # --- NOVO: Exibir mensagem de cotação enviada ---
    if "msg_sucesso_envio" in st.session_state:
        st.success(st.session_state["msg_sucesso_envio"])
        del st.session_state["msg_sucesso_envio"] # Apaga para não mostrar de novo
    # -----------------------------------------------

    # --- CALLBACKS (Funções que rodam ANTES da tela recarregar) ---
    def add_item_callback(novo_item):
        st.session_state["itens_cotacao"].append(novo_item)
        # Limpa os campos com segurança
        st.session_state["busca_produto"] = ""
        st.session_state["qtd_add"] = 1
        if "select_produto" in st.session_state:
            del st.session_state["select_produto"]
        # Sinaliza sucesso para mostrar mensagem depois
        st.session_state["msg_sucesso"] = "Item adicionado com sucesso!"

    def limpar_tudo_callback():
        st.session_state["itens_cotacao"] = []
        st.session_state["busca_produto"] = ""
        st.session_state["qtd_add"] = 1
        if "select_produto" in st.session_state:
            del st.session_state["select_produto"]
    # -------------------------------------------------------------

    st.subheader("🛒 Nova Cotação de Produtos")
    
    # Exibir mensagem de sucesso se houver (vindo do callback)
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state["msg_sucesso"])
        del st.session_state["msg_sucesso"] # Remove para não aparecer de novo

    # ============================================================
    # 1. VERIFICAÇÃO DE CARRINHO (Movido para cima para a trava funcionar)
    # ============================================================
    if 'itens_cotacao' not in st.session_state:
        st.session_state.itens_cotacao = []
    
    # Verifica se já existem itens na lista
    tem_itens_no_carrinho = len(st.session_state.itens_cotacao) > 0

    # ============================================================
    # 2. DEFINIÇÃO DA COLUNA DE PREÇO E PERMISSÃO DE RETIRADA
    # ============================================================
    coluna_preco_cliente = cliente.get("coluna_preco")
    if not coluna_preco_cliente:
        coluna_preco_cliente = "preco_entrega"

    permite_retirada_cliente = bool(cliente.get("permite_retirada", False))

    if permite_retirada_cliente:
        opcoes_recebimento = ["Entrega", "Retirada no centro de distribuição"]
        forma_recebimento = st.radio(
            "Como deseja receber os produtos?",
            opcoes_recebimento,
            key="forma_recebimento_cotacao",
            disabled=tem_itens_no_carrinho,
            help="Para alterar a forma de recebimento, remova os itens da cotação atual."
        )
        if tem_itens_no_carrinho:
            st.caption("🔒 *Para mudar a forma de recebimento, clique em 'Limpar Tudo' no final da página.*")
    else:
        forma_recebimento = "Entrega"
        st.info("🚚 **Forma de recebimento:** Entrega (caso precise retirar no centro de distribuição, verifique com seu seu Representante).")

    if forma_recebimento == "Retirada no centro de distribuição":
        # Corrigido para "preco_retira" para bater com o banco
        coluna_preco = "preco_retira" 
    else:
        # Se for entrega, usa a coluna baseada na distância
        coluna_preco = coluna_preco_cliente
    
    pode_ver_preco = bool(cliente.get('visualiza_preco', True))
    
    st.markdown("---")
    st.subheader("🔍 Buscar e adicionar produtos")
    
    # Inicializar carrinho na sessão
    if 'itens_cotacao' not in st.session_state:
        st.session_state.itens_cotacao = []
    
    # Busca de produtos
    termo_busca = st.text_input(
        "Digite ao menos 3 caracteres do código ou nome do produto",
        key="busca_produto"
    )
    
    if termo_busca and len(termo_busca.strip()) >= 3:
        termo = termo_busca.strip()
        termo_norm = normalizar_texto(termo)

        # Busca no backend (como já está) e depois filtra sem acento no Python
        df_produtos = buscar_produtos(representante_id, termo)

        if df_produtos.empty:
            st.warning("Nenhum produto encontrado")
        else:
            # garante colunas como string
            df_produtos["produto"] = df_produtos["produto"].astype(str)
            df_produtos["codigo"] = df_produtos["codigo"].astype(str)

            # cria colunas normalizadas
            df_produtos["produto_norm"] = df_produtos["produto"].apply(normalizar_texto)
            df_produtos["codigo_norm"] = df_produtos["codigo"].apply(normalizar_texto)

            # filtro acento-insensitive por produto OU código
            mask = (
                df_produtos["produto_norm"].str.contains(termo_norm, na=False) |
                df_produtos["codigo_norm"].str.contains(termo_norm, na=False)
            )
            df_filtrado = df_produtos[mask].copy()

            if df_filtrado.empty:
                st.warning("Nenhum produto encontrado")
            else:
                opcoes = df_filtrado.apply(
                    lambda row: f"{row['codigo']} - {row['produto']}",
                    axis=1
                ).tolist()

                escolha = st.selectbox(
                    "Clique abaixo e escolha um produto da lista",
                    opcoes,
                    key="select_produto"
                )

                if escolha:
                    codigo_escolhido = escolha.split(' - ')[0]
                    produto_sel = df_filtrado[df_filtrado['codigo'] == codigo_escolhido].iloc[0]

                    # Dados básicos
                    preco_retira = produto_sel.get('preco_retira')
                    id_produto_banco = produto_sel.get('id') or produto_sel.get('ID') or produto_sel.get('Id')

                    # Calcular preço
                    preco_final = get_preco_produto(produto_sel, coluna_preco, forma_recebimento)

                    st.markdown("**Detalhes do produto:**")
                    st.write(f"Código: {produto_sel['codigo']}")
                    st.write(f"Produto: {produto_sel['produto']}")
                    st.write(f"Unidade: {produto_sel['unidade']}")

                    if pode_ver_preco:
                        if forma_recebimento == 'Retirada no centro de distribuição':
                            if preco_retira:
                                st.write(f"Preço para retirada: R$ {float(preco_retira):.2f}")
                        else:
                            if preco_final:
                                st.write(f"Preço com frete: R$ {float(preco_final):.2f}")
                    else:
                        st.info("Os preços serão calculados e enviados pelo representante.")

                    qtd = st.number_input("Quantidade", min_value=1, value=1, step=1, key="qtd_add")

                    # --- PREPARAÇÃO DOS DADOS ANTES DO BOTÃO ---
                    if not id_produto_banco:
                        st.error("ERRO: Produto sem ID. Recarregue a página.")
                    else:
                        val_final = float(preco_final) if preco_final is not None else 0.0
                        subtotal_retira = (float(preco_retira) * qtd) if preco_retira is not None else 0.0
                        subtotal_final = val_final * qtd

                        item_para_adicionar = {
                            "produto_id": id_produto_banco,
                            "codigo": produto_sel['codigo'],
                            "produto": produto_sel['produto'],
                            "unidade": produto_sel['unidade'],
                            "quantidade": qtd,
                            "preco_retira": float(preco_retira) if preco_retira is not None else 0.0,
                            "preco_final": val_final,
                            "subtotal_retira": subtotal_retira,
                            "subtotal_final": subtotal_final,
                        }

                        st.button(
                            "+ Adicionar à cotação",
                            key="btn_add_produto",
                            on_click=add_item_callback,
                            args=(item_para_adicionar,)
                        )
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
                # Mudamos a KEY para incluir o código do produto. 
                # Assim ela fica única e não se confunde se a ordem mudar.
                nova_qtd = st.number_input(
                    "Qtde",
                    min_value=1,
                    value=int(item["quantidade"]),
                    step=1,
                    key=f"qtd_{item['codigo']}_{idx}", # <--- CORREÇÃO
                    label_visibility="collapsed"
                )
                if nova_qtd != item["quantidade"]:
                    st.session_state["itens_cotacao"][idx]["quantidade"] = nova_qtd
                    # Atualiza subtotais ao mudar quantidade na lista
                    st.session_state["itens_cotacao"][idx]["subtotal_retira"] = item["preco_retira"] * nova_qtd
                    st.session_state["itens_cotacao"][idx]["subtotal_final"] = item["preco_final"] * nova_qtd
                    st.rerun()

            with col4:
                if pode_ver_preco:
                    # Verifica qual preço mostrar
                    preco_show = item['preco_retira'] if forma_recebimento == 'Retirada no centro de distribuição' else item['preco_final']
                    st.write(f"R$ {preco_show:.2f}")
                else:
                    st.write("-")

            with col5:
                if pode_ver_preco:
                    # Verifica qual subtotal mostrar
                    sub_show = item['subtotal_retira'] if forma_recebimento == 'Retirada no centro de distribuição' else item['subtotal_final']
                    st.write(f"R$ {sub_show:.2f}")
                else:
                    st.write("-")

            with col6:
                if st.button("X", key=f"del_{idx}"):
                    st.session_state["itens_cotacao"].pop(idx)
                    st.rerun()

        st.markdown("---")

        if pode_ver_preco:
            # Calcula total baseado na escolha atual
            if forma_recebimento == 'Retirada no centro de distribuição':
                total_final = sum(item["subtotal_retira"] for item in itens)
            else:
                total_final = sum(item["subtotal_final"] for item in itens)
                
            st.markdown(f"### Total Estimado: R$ {total_final:.2f}")
            st.caption(f"ℹ️ {AVISO_PRECOS_REFERENCIAIS}")
        else:
            st.info("Os valores totais desta cotação serão calculados e enviados pelo representante.")
            st.caption(f"ℹ️ {AVISO_PRECOS_REFERENCIAIS}")

        col1, col2 = st.columns([1, 4])

        with col1:
            if st.button("Enviar Cotação", type="primary", key="btn_enviar"):
                
                # Preparação dos dados para envio
                itens_para_salvar = []
                for item in itens:
                    item_pronto = item.copy()
                    
                    if forma_recebimento == 'Retirada no centro de distribuição':
                        item_pronto['preco_unitario'] = item['preco_retira']
                        item_pronto['subtotal'] = item['subtotal_retira']
                    else:
                        item_pronto['preco_unitario'] = item['preco_final']
                        item_pronto['subtotal'] = item['subtotal_final']
                    
                    itens_para_salvar.append(item_pronto)
                
                id_cot = salvar_cotacao(
                    cliente['representante_id'], 
                    cliente['id'], 
                    cliente['nome'], 
                    itens_para_salvar,
                    forma_recebimento
                )
                
                if id_cot:
                    # Guardamos a mensagem na sessão para ela sobreviver ao rerun
                    st.session_state["msg_sucesso_envio"] = f"✅ Cotação enviada com sucesso! ID: {id_cot}. Acompanhe em 'Meus Pedidos'."
                    st.session_state["itens_cotacao"] = []
                    st.rerun()

        with col2:
            # --- BOTÃO LIMPAR COM CALLBACK (Correção do erro) ---
            st.button("Limpar Tudo", key="btn_limpar", on_click=limpar_tudo_callback)

    else:
        st.info("Nenhum item adicionado ainda. Busque produtos acima.")

def pagina_meus_pedidos(cliente):
    """Mostra histórico de pedidos do cliente"""
    st.subheader("📦 Meus Pedidos")
    
    # 1. Pegamos a permissão geral do perfil do cliente
    permissao_geral_perfil = bool(cliente.get('visualiza_preco', True)) 
    
    cotacoes = carregar_cotacoes_cliente(cliente['id'])
    
    if cotacoes.empty:
        st.info("Você ainda não tem pedidos")
        return
    
    st.write(f"**Total de pedidos:** {len(cotacoes)}")
    
    for idx, (_, cot) in enumerate(cotacoes.iterrows()):
        
        # 2. DEFINIÇÃO DA REGRA DE VISUALIZAÇÃO PARA ESTA COTAÇÃO ESPECÍFICA
        # O cliente vê o preço se tiver permissão geral OU se a cotação já estiver APROVADA
        status_aprovada = cot['status'] == 'APROVADA'
        mostrar_precos_nesta_cotacao = permissao_geral_perfil or status_aprovada # <--- Lógica corrigida aqui
        
        with st.expander(
            f"📄 Pedido {cot['id']} - {cot['created_at'][:10] if cot.get('created_at') else ''} - Status: {cot['status']}",
            expanded=(idx == 0)
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Forma de recebimento:** {cot.get('forma_recebimento', 'N/A')}")
                
                # Destacar o status visualmente
                if cot['status'] == 'APROVADA':
                    st.success(f"**Status:** {cot['status']}")
                elif cot['status'] == 'PENDENTE':
                    st.warning(f"**Status:** {cot['status']}")
                else:
                    st.error(f"**Status:** {cot['status']}")
            
            # Carrega itens antes do resumo para calcular valores com e sem desconto
            itens = carregar_itens_cotacao(cot['id'])

            with col2:
                # 3. Usamos a variável específica da cotação, não mais a geral
                if mostrar_precos_nesta_cotacao:
                    try:
                        soma_subtotais = float(cot.get('total_original', 0))
                        desconto = float(cot.get('desconto_geral_percentual', 0))
                        total_final = float(cot.get('total_final', 0))
                    except (ValueError, TypeError):
                        soma_subtotais = total_final = 0.0
                        desconto = 0.0

                    if not itens.empty:
                        total_bruto = float((itens['preco_unitario'].astype(float) * itens['quantidade'].astype(float)).sum())
                    else:
                        total_bruto = soma_subtotais

                    desc_itens_reais = max(0.0, total_bruto - soma_subtotais)
                    desc_pedido_reais = max(0.0, soma_subtotais - total_final)

                    st.write(f"**Total bruto (sem descontos):** R$ {total_bruto:.2f}")
                    if desc_itens_reais > 0.01:
                        st.write(f"**Desconto nos itens:** - R$ {desc_itens_reais:.2f}")
                    if desconto > 0 or desc_pedido_reais > 0.01:
                        st.write(f"**Desconto no pedido ({desconto:.1f}%):** - R$ {desc_pedido_reais:.2f}")
                    st.write(f"**Total final:** R$ {total_final:.2f}")
                else:
                    st.info("Aguardando aprovação do representante para exibir valores finais.")

            # Itens
            if not itens.empty:
                st.markdown("**Itens:**")
                
                df_show = itens[['codigo', 'produto', 'quantidade']].copy()
                
                # 4. Controla visualização na tabela de itens
                if mostrar_precos_nesta_cotacao:
                    df_show['preco_unitario'] = itens['preco_unitario'].apply(lambda x: f"R$ {float(x):.2f}")
                    if 'desconto_percentual' in itens.columns:
                        df_show['desconto_percentual'] = itens['desconto_percentual'].fillna(0.0).apply(
                            lambda x: f"{float(x):.1f}%" if float(x) > 0 else "-"
                        )
                    else:
                        df_show['desconto_percentual'] = "-"
                    df_show['subtotal'] = itens['subtotal'].apply(lambda x: f"R$ {float(x):.2f}")
                else:
                    df_show['preco_unitario'] = '-'
                    df_show['desconto_percentual'] = '-'
                    df_show['subtotal'] = '-'
                
                df_show = df_show.rename(columns={
                    'codigo': 'Código',
                    'produto': 'Produto',
                    'quantidade': 'Qtde',
                    'preco_unitario': 'Preço Unit.',
                    'desconto_percentual': 'Desconto (%)',
                    'subtotal': 'Subtotal'
                })
                
                st.dataframe(df_show, width='stretch', hide_index=True)
            
            st.caption(f"ℹ️ {AVISO_PRECOS_REFERENCIAIS}")
                      
            # 5. Controla visualização no PDF (validando cliente_id da sessão)
            pdf_bytes = gerar_pdf_cotacao(cot['id'], mostrar_precos_nesta_cotacao, cliente_id=cliente['id'])
            st.download_button(
                label="📄 Baixar PDF",
                data=pdf_bytes,
                file_name=f"pedido_{cot['id']}.pdf",
                mime="application/pdf",
                key=f"pdf_cliente_{cot['id']}"
            )
            st.markdown("---")
            
            # Botão WhatsApp Melhorado
            try:
                rep_data = supabase.table('representantes').select('telefone, nome').eq('id', cliente['representante_id']).single().execute()
                tel_rep = rep_data.data.get('telefone')
                nome_rep = rep_data.data.get('nome', 'Representante')
                
                if tel_rep:
                    tel_limpo = so_digitos(tel_rep)
                    if tel_limpo:
                        # Mensagem mais completa
                        texto_msg = f"Olá {nome_rep}! Sou {cliente['nome']}. Gostaria de falar sobre o pedido *{cot['id']}*."
                        link_whats = f"https://wa.me/55{tel_limpo}?text={texto_msg}"
                        
                        st.link_button(
                            label="📲 Whatsapp do Representante", 
                            url=link_whats,
                            type="secondary", # Ou 'primary' se quiser destaque
                            help=f"Envia mensagem para {nome_rep} sobre este pedido"
                        )
            except Exception as e:
                # Se der erro ao buscar telefone, apenas ignora
                pass

# =====================================================================
# PÁGINA DO CLIENTE (COM CORREÇÃO DE SEGURANÇA)
# =====================================================================
def pagina_cliente():
    """Página principal do cliente (Login e Ativação via CNPJ/Telefone)"""
    local_css()
    
    if 'cliente_logado' not in st.session_state:
        st.session_state.cliente_logado = None
    
    # --- VERIFICAÇÃO DE SESSÃO ---
    # Se já estiver logado, verifica se o usuário ainda existe no banco
    if st.session_state.cliente_logado:
        try:
            c_id = st.session_state.cliente_logado['id']
            resp = supabase.table('clientes').select('*').eq('id', c_id).execute()
            if resp.data:
                st.session_state.cliente_logado = resp.data[0]
            else:
                st.session_state.cliente_logado = None
                st.rerun()
        except Exception as e:
            registrar_erro("Verificação de sessão do cliente", e)


    # --- TELA DE LOGIN / PRIMEIRO ACESSO ---
    if st.session_state.cliente_logado is None:
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        
        with col_centro:
            st.markdown("<h2 style='text-align: center; color: #0b245c;'>Área do Cliente</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Faça login ou cadastre sua senha.</p>", unsafe_allow_html=True)
            
            # Mudamos as abas para refletir a lógica correta
            tab_login, tab_ativar = st.tabs(["Já tenho senha", "Criar senha (1º Acesso)"])
            
            # === ABA 1: LOGIN ===
            with tab_login:
                with st.form("form_login_cliente"):
                    st.write("**Acesse sua conta**")
                    # AQUI ESTÁ A MUDANÇA: Pede CNPJ ou Telefone
                    identificador = st.text_input("CNPJ ou Telefone", placeholder="Somente números")
                    senha = st.text_input("Senha", type="password")
                    
                    if st.form_submit_button("ENTRAR", width="stretch"):
                        if not identificador or not senha:
                            st.warning("Preencha todos os campos")
                        else:
                            # Chama a função correta que busca por CNPJ/Tel
                            cliente, msg = autenticar_cliente(identificador, senha)
                            if cliente:
                                st.session_state.cliente_logado = cliente
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            
            # === ABA 2: ATIVAR CONTA (Primeiro Acesso) ===
            with tab_ativar:
                st.info("ℹ️ Use seu CNPJ ou Telefone cadastrado pelo representante para validar.")
                
                with st.form("form_ativacao_cliente"):
                    st.write("**Crie sua senha**")
                    # AQUI TAMBÉM: Busca o cadastro existente
                    identificador_ativ = st.text_input("CNPJ ou Telefone", placeholder="Ex: 61223557000196")
                    
                    st.write("---")
                    nova_senha = st.text_input("Crie sua Senha", type="password", placeholder="......")
                    confirma_senha = st.text_input("Confirme sua Senha", type="password", placeholder="......")
                    
                    btn_criar = st.form_submit_button("CRIAR CONTA", width="stretch")
                    
                    if btn_criar:
                        if not identificador_ativ:
                            st.warning("Digite seu CNPJ ou Telefone.")
                        elif not nova_senha or len(nova_senha) < 4:
                            st.warning("A senha deve ter pelo menos 6 caracteres.")
                        elif nova_senha != confirma_senha:
                            st.error("As senhas não coincidem.")
                        else:
                            # Chama a função que localiza o cliente da planilha e atualiza a senha
                            sucesso, msg = ativar_senha_cliente(identificador_ativ, nova_senha)
                            if sucesso:
                                st.success(msg)
                                # Opcional: Pausa breve para ler a mensagem antes de forçar login manual
                            else:
                                st.error(msg)
        return

    # --- ÁREA LOGADA (Menu do Cliente) ---
    cliente = st.session_state.cliente_logado
    
    st.sidebar.title(f"Olá, {cliente.get('nome', 'Cliente').split()[0]}!")
    # Mostra o identificador (CNPJ ou Tel) na barra lateral para confirmação
    st.sidebar.caption(f"ID: {cliente.get('cnpj') or cliente.get('telefone')}")
    
    menu = st.sidebar.radio("Menu", ["Nova Cotação", "Meus Pedidos"])
    
    if st.sidebar.button("Sair"):
        st.session_state.cliente_logado = None
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <small style='color: white; font-size: 10px; opacity: 0.7;'>
    Contato e Suporte<br>
    atendimento@beccai.com.br<br>
    (11) 95451.9325<br>
    Desenvolvido por www.beccai.com.br<br>
    ---<br>
    Versão 2.0 | Janeiro 2026
    </small>
    """, unsafe_allow_html=True)
    
    if menu == "Nova Cotação":
        pagina_nova_cotacao(cliente)
    elif menu == "Meus Pedidos":
        pagina_meus_pedidos(cliente)

# =====================================================================
# MAIN
# =====================================================================

def main():
    st.set_page_config(
        page_title="RC Online",
        page_icon="📊",
        layout="wide"
    )
    
    local_css()
    
    st.sidebar.title("RC Online")
    tipo_usuario = st.sidebar.radio("Tipo de Acesso", ["Cliente", "Representante", "Administradora"])
    
    if tipo_usuario == "Cliente":
        pagina_cliente()
    elif tipo_usuario == "Representante":
        pagina_representante()
    else:
        pagina_administradora()

if __name__ == "__main__":
    main()


























