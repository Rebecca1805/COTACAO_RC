import os
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
import re  # pra limpar CNPJ/telefone
from fpdf import FPDF
from fpdf import FPDF

# =========================
# CONFIGURAÇÕES INICIAIS
# =========================

REP_PASS = os.environ.get("REP_PASS", "123456")  # pode trocar essa senha depois
REP_NAME = os.environ.get("REP_NAME", "RC")
DATA_DIR = "data"
STORAGE_DIR = "storage"

CLIENTES_PATH = os.path.join(DATA_DIR, "CLIENTES RC.xlsx")
TABELA_PATH = os.path.join(DATA_DIR, "TABELA GERAL CSV.csv")

COTACOES_PATH = os.path.join(STORAGE_DIR, "cotacoes.csv")
ITENS_COTACAO_PATH = os.path.join(STORAGE_DIR, "itens_cotacao.csv")

os.makedirs(STORAGE_DIR, exist_ok=True)


# =========================
# FUNÇÕES DE CARGA DE DADOS
# =========================

@st.cache_data
def load_clientes():
    """
    Lê a planilha de clientes.
    Usa a coluna 'Preco 100a199km' como 'coluna_preco' = nome da coluna de preço
    na tabela geral para aquele cliente (ex.: 'Preco200a299km').
    """
    df = pd.read_excel(CLIENTES_PATH)

    # Remove linhas vazias
    df = df[df["NOME"].notna()].copy()

    # Normaliza nomes de colunas removendo espaços redundantes para
    # evitar problemas com variantes como 'Preco 100a199km' vs 'Preco100a199km'
    df.columns = [str(c).strip() for c in df.columns]

    # Converte CNPJ e TELEFONE para string sem decimal (removendo .0 do float)
    if any(c.upper() == "CNPJ" for c in df.columns):
        df["CNPJ"] = df.get("CNPJ", "").fillna(0).astype(int).astype(str)
    if any(c.upper() == "TELEFONE" for c in df.columns):
        df["TELEFONE"] = df.get("TELEFONE", "").fillna(0).astype(int).astype(str)

    # Se houver a coluna `DISTANCIA`, ela é a fonte de verdade: pode conter
    # o nome da coluna de preço (ex.: 'Preco300a399km') ou um número (ex.: 310).
    # Vamos priorizar `DISTANCIA` quando presente. Caso contrário, tentamos
    # detectar alguma coluna que já contenha o nome do campo de preço.
    def _map_preco_from_dist(row):
        # se DISTANCIA já contém o nome da coluna (ex: 'Preco300a399km')
        if "DISTANCIA" in row and pd.notna(row["DISTANCIA"]):
            s = str(row["DISTANCIA"]).strip()
            if s.lower().startswith("preco"):
                return s.replace(" ", "")
            # tentar extrair número e mapear faixas
            digits = re.sub(r"\D", "", s)
            if digits:
                try:
                    d = int(digits)
                except Exception:
                    return str(row.get("coluna_preco", "Preco100a199km")).replace(" ", "")
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
        # fallback: use existing coluna_preco if present
        return str(row.get("coluna_preco", "Preco100a199km")).replace(" ", "")

    # Se houver coluna DISTANCIA, usamos o mapeamento a partir dela
    if any(c.upper() == "DISTANCIA" for c in df.columns):
        df["coluna_preco"] = df.apply(_map_preco_from_dist, axis=1)
    else:
        # Tentar encontrar uma coluna existente que contenha 'Preco' no nome
        preco_col = None
        for c in df.columns:
            if re.search(r"(?i)preco", str(c)):
                preco_col = c
                break
        if preco_col:
            # essa coluna provavelmente já contém o nome da faixa (ou valor); copiamos
            df = df.rename(columns={preco_col: "coluna_preco"})
            df["coluna_preco"] = df["coluna_preco"].astype(str).str.replace(" ", "")
        else:
            # fallback seguro
            df["coluna_preco"] = "Preco100a199km"

    return df


@st.cache_data
def load_tabela_geral():
    """
    Lê a tabela geral de produtos (UTF-8 + CSV).
    """
    df = pd.read_csv(
        TABELA_PATH,
        sep=",",
        encoding="utf-8",
        dtype=str,
    )
    return df


def parse_preco(valor):
    """Converte string tipo '18,14' em float 18.14."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    if not s:
        return None
    try:
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return None


def get_preco_entrega(cliente_row, produto_row):
    """Preço com frete, usando a coluna da faixa do cliente."""
    coluna_preco = str(cliente_row["coluna_preco"]).replace(" ", "")
    if coluna_preco not in produto_row.index:
        return None
    return parse_preco(produto_row[coluna_preco])


def get_preco_retira(produto_row):
    """Preço para retirada (coluna 'Retira')."""
    if "Retira" not in produto_row.index:
        return None
    return parse_preco(produto_row["Retira"])


def so_digitos(valor):
    """Remove tudo que não for número."""
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))

# =========================
# FUNÇÕES DE ARMAZENAMENTO
# =========================

def load_cotacoes():
    """
    Carrega cotações do CSV sem cache, para garantir que mudanças
    salvas (desconto, status) apareçam imediatamente após rerun.
    """
    if not os.path.exists(COTACOES_PATH):
        return pd.DataFrame(
            columns=[
                "id", "cliente_nome", "cliente_telefone",
                "representante", "status", "data",
                "forma_recebimento",
                "total_original", "desconto_percentual", "total"
            ]
        )
    df = pd.read_csv(COTACOES_PATH)

    # Garante as colunas novas caso o arquivo seja antigo
    if "total_original" not in df.columns:
        df["total_original"] = df["total"]
    if "desconto_percentual" not in df.columns:
        df["desconto_percentual"] = 0.0

    return df

def load_itens_cotacao():
    """
    Carrega itens das cotações do CSV sem cache.
    """
    if not os.path.exists(ITENS_COTACAO_PATH):
        return pd.DataFrame(
            columns=[
                "id_cotacao", "codigo", "produto", "unidade",
                "quantidade", "preco_retira", "preco_final",
                "subtotal_retira", "subtotal_final"
            ]
        )
    return pd.read_csv(ITENS_COTACAO_PATH)


def gerar_id_cotacao(cliente_nome):
    """
    Gera ID da cotação: 4 primeiros dígitos do cliente + data_hora compactada.
    Exemplo: LOUR20251203143000 (LOUR = Loureiro, 20251203143000 = 2025-12-03 14:30:00)
    """
    # Extrai 4 primeiros caracteres do nome (maiúsculos, sem espaços)
    cliente_prefix = re.sub(r"\W", "", cliente_nome.upper())[:4].ljust(4, "X")
    # Data/hora compactada: YYYYMMDDHHMISS
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{cliente_prefix}{timestamp}"


def salvar_cotacao(cliente_row, itens, forma_recebimento):
    """
    itens: lista de dicts com
      - codigo, produto, unidade, quantidade,
        preco_retira, preco_final,
        subtotal_retira, subtotal_final
    """
    if not itens:
        st.error("Nenhum item na cotação.")
        return None

    cotacoes = load_cotacoes()
    itens_cot = load_itens_cotacao()

    id_cotacao = gerar_id_cotacao(cliente_row["NOME"])
    total_final = sum(item["subtotal_final"] for item in itens)

    nova_cot = {
        "id": id_cotacao,
        "cliente_nome": cliente_row["NOME"],
        "cliente_telefone": cliente_row.get("TELEFONE", ""),
        "representante": "",  # depois podemos puxar de uma coluna
        "status": "PENDENTE",
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "forma_recebimento": forma_recebimento,
        "total_original": total_final,
        "desconto_percentual": 0.0,
        "total": total_final,
    }

    cotacoes = pd.concat(
        [cotacoes, pd.DataFrame([nova_cot])],
        ignore_index=True,
    )

    novos_itens = []
    for item in itens:
        novos_itens.append(
            {
                "id_cotacao": id_cotacao,
                "codigo": item["codigo"],
                "produto": item["produto"],
                "unidade": item["unidade"],
                "quantidade": item["quantidade"],
                "preco_retira": item["preco_retira"],
                "preco_final": item["preco_final"],
                "subtotal_retira": item["subtotal_retira"],
                "subtotal_final": item["subtotal_final"],
            }
        )

    itens_cot = pd.concat(
        [itens_cot, pd.DataFrame(novos_itens)],
        ignore_index=True,
    )

    cotacoes.to_csv(COTACOES_PATH, index=False)
    itens_cot.to_csv(ITENS_COTACAO_PATH, index=False)

    return id_cotacao


def atualizar_status_cotacao(id_cotacao, novo_status):
    cotacoes = load_cotacoes()
    if id_cotacao not in cotacoes["id"].values:
        st.error("Cotação não encontrada.")
        return

    cotacoes.loc[cotacoes["id"] == id_cotacao, "status"] = novo_status
    cotacoes.to_csv(COTACOES_PATH, index=False)
    st.success(f"Status da cotação {id_cotacao} atualizado para {novo_status}.")


def gerar_pdf_cotacao(cot_row, itens_df):
    """
    Gera um PDF da cotação e devolve os bytes para download.
    """
    pdf = FPDF()
    pdf.add_page()

    # Cabeçalho
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Cotacao de Produtos", ln=True)

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"ID: {cot_row.get('id', '')}", ln=True)
    pdf.cell(0, 8, f"Cliente: {cot_row.get('cliente_nome', '')}", ln=True)
    pdf.cell(0, 8, f"Telefone: {cot_row.get('cliente_telefone', '')}", ln=True)
    pdf.cell(0, 8, f"Data: {cot_row.get('data', '')}", ln=True)
    pdf.cell(0, 8, f"Forma de recebimento: {cot_row.get('forma_recebimento', '')}", ln=True)

    # Totais
    try:
        total_original = float(cot_row.get("total_original", cot_row.get("total", 0.0)))
    except Exception:
        total_original = float(cot_row.get("total", 0.0))

    try:
        desconto = float(cot_row.get("desconto_percentual", 0.0))
    except Exception:
        desconto = 0.0

    pdf.cell(0, 8, f"Total original: R$ {total_original:.2f}", ln=True)
    if desconto:
        pdf.cell(0, 8, f"Desconto: {desconto:.1f}%", ln=True)
    pdf.cell(0, 8, f"Total final: R$ {float(cot_row.get('total', 0.0)):.2f}", ln=True)

    pdf.ln(4)

    # Tabela de itens
    pdf.set_font("Arial", "B", 10)
    pdf.cell(20, 8, "Cod.", border=1)
    pdf.cell(60, 8, "Produto", border=1)
    pdf.cell(12, 8, "Un.", border=1)
    pdf.cell(12, 8, "Qtde", border=1)
    pdf.cell(28, 8, "Retirada", border=1)
    pdf.cell(32, 8, "Total c/ frete", border=1, ln=True)

    pdf.set_font("Arial", "", 9)
    for _, row in itens_df.iterrows():
        codigo = str(row.get("codigo", ""))
        produto = str(row.get("produto", ""))[:30]
        unidade = str(row.get("unidade", ""))
        qtde = str(row.get("quantidade", ""))
        try:
            preco_retira = float(row.get("preco_retira", 0.0))
        except Exception:
            preco_retira = 0.0
        try:
            subtotal_final = float(row.get("subtotal_final", 0.0))
        except Exception:
            subtotal_final = 0.0

        pdf.cell(20, 6, codigo, border=1)
        pdf.cell(60, 6, produto, border=1)
        pdf.cell(12, 6, unidade, border=1)
        pdf.cell(12, 6, qtde, border=1)
        pdf.cell(28, 6, f"{preco_retira:.2f}", border=1)
        pdf.cell(32, 6, f"{subtotal_final:.2f}", border=1, ln=True)

    # Retorna bytes do PDF
    # Compatibilidade: dependendo da versão, `pdf.output(dest="S")` pode
    # retornar `str` ou `bytearray`/`bytes`. Normalizamos para `bytes`.
    out = None
    try:
        out = pdf.output(dest="S")
    except Exception:
        out = None

    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str):
        return out.encode("latin-1")

    # Tentativa final: algumas versões expõem `output_bytes()`
    if hasattr(pdf, "output_bytes"):
        try:
            res = pdf.output_bytes()
            if isinstance(res, (bytes, bytearray)):
                return bytes(res)
            if isinstance(res, str):
                return res.encode("latin-1")
        except Exception:
            pass

    # Se nada funcionou, lançar erro claro
    raise RuntimeError("Não foi possível exportar PDF: formato de saída inesperado.")


# =========================
# PÁGINA DO CLIENTE
# =========================

def pagina_cliente():
    st.header("Área do Cliente - Cotação de Produtos")

    clientes = load_clientes()
    tabela = load_tabela_geral()

    st.subheader("Identificação do cliente")

    id_input = st.text_input(
        "Digite seu CNPJ ou telefone (apenas números):"
    )

    if not id_input:
        st.info("Informe seu CNPJ ou telefone para continuar.")
        return

    # normaliza entrada e cadastros
    id_digitos = so_digitos(id_input)

    clientes_busca = clientes.copy()
    if "CNPJ" in clientes_busca.columns:
        clientes_busca["CNPJ_limp"] = clientes_busca["CNPJ"].apply(so_digitos)
    else:
        clientes_busca["CNPJ_limp"] = ""

    if "TELEFONE" in clientes_busca.columns:
        clientes_busca["TEL_limp"] = clientes_busca["TELEFONE"].apply(so_digitos)
    else:
        clientes_busca["TEL_limp"] = ""

    match = clientes_busca[
        (clientes_busca["CNPJ_limp"] == id_digitos)
        | (clientes_busca["TEL_limp"] == id_digitos)
    ]

    if match.empty:
        st.error("Cliente não encontrado. Verifique o CNPJ/telefone informado.")
        return

    if len(match) > 1:
        # bem raro, mas só pra garantir
        st.warning("Mais de um cadastro encontrado, usando o primeiro.")
    cliente_row = match.iloc[0]

    st.success(f"Cliente identificado: {cliente_row['NOME']}")

    # Escolha de retirada x entrega
    forma_recebimento = st.radio(
        "Como deseja receber os produtos?",
        ["Retirada no centro de distribuição", "Entrega no endereço"]
    )
    entrega = forma_recebimento == "Entrega no endereço"

    # Colunas reais da tabela de produtos
    col_codigo = "Codigo_1" if "Codigo_1" in tabela.columns else "Codigo"
    col_produto = "Produto_1" if "Produto_1" in tabela.columns else "Produto"
    col_unidade = "Unidade_1" if "Unidade_1" in tabela.columns else "Unidade"

    st.subheader("Buscar e adicionar produtos à cotação")

    if "itens_cotacao" not in st.session_state:
        st.session_state["itens_cotacao"] = []

    termo_busca = st.text_input(
        "Digite ao menos 3 caracteres do código ou nome do produto:"
    )

    if termo_busca and len(termo_busca.strip()) >= 3:
        termo_lower = termo_busca.lower().strip()

        df_view = tabela[
            tabela[col_produto].astype(str).str.lower().str.contains(termo_lower)
            | tabela[col_codigo].astype(str).str.lower().str.contains(termo_lower)
        ].copy()

        # limitar resultados pra não virar dump de tabela
        max_resultados = 20
        df_view = df_view.head(max_resultados)

        if df_view.empty:
            st.warning("Nenhum produto encontrado para esse termo.")
        else:
            opcoes = df_view.apply(
                lambda row: f"{row[col_codigo]} - {row[col_produto]}", axis=1
            ).tolist()

            escolha = st.selectbox(
                "Selecione um produto dentre os resultados:",
                [""] + opcoes,
                key="select_produto_busca"
            )

            if escolha:
                codigo_escolhido = escolha.split(" - ")[0]
                produto_sel = df_view[df_view[col_codigo] == codigo_escolhido].iloc[0]

                preco_retira = get_preco_retira(produto_sel)
                preco_entrega = get_preco_entrega(cliente_row, produto_sel)

                # preço usado de fato na cotação
                if entrega:
                    preco_final = preco_entrega if preco_entrega is not None else preco_retira
                else:
                    preco_final = preco_retira

                st.markdown("### Detalhes do produto selecionado")
                st.write(f"**Código:** {produto_sel[col_codigo]}")
                st.write(f"**Produto:** {produto_sel[col_produto]}")
                st.write(f"**Unidade:** {produto_sel[col_unidade]}")

                if preco_retira is not None:
                    st.write(f"**Preço para retirada:** R$ {preco_retira:.2f}")
                else:
                    st.warning("Preço de retirada não disponível.")

                if entrega:
                    if preco_entrega is not None:
                        st.write(f"**Preço com frete (entrega):** R$ {preco_entrega:.2f}")
                    else:
                        st.warning("Preço com frete não disponível para este produto.")

                qtd = st.number_input("Quantidade", min_value=1, value=1, step=1)

                if st.button("Adicionar esse produto à cotação"):
                    if preco_final is None:
                        st.error("Não é possível adicionar um item sem preço.")
                    else:
                        subtotal_retira = preco_retira * qtd if preco_retira is not None else 0.0
                        subtotal_final = preco_final * qtd

                        st.session_state["itens_cotacao"].append(
                            {
                                "codigo": produto_sel[col_codigo],
                                "produto": produto_sel[col_produto],
                                "unidade": produto_sel[col_unidade],
                                "quantidade": qtd,
                                "preco_retira": preco_retira if preco_retira is not None else 0.0,
                                "preco_final": preco_final,
                                "subtotal_retira": subtotal_retira,
                                "subtotal_final": subtotal_final,
                            }
                        )
                        st.success("Item adicionado à cotação!")

    elif termo_busca and len(termo_busca.strip()) < 3:
        st.info("Digite pelo menos 3 caracteres para buscar.")

    # Lista dos itens da cotação
    st.markdown("---")
    st.subheader("Itens da sua cotação")

    itens = st.session_state.get("itens_cotacao", [])
    if itens:
        df_itens = pd.DataFrame(itens)
        df_itens["preco_retira"] = df_itens["preco_retira"].astype(float)
        df_itens["preco_final"] = df_itens["preco_final"].astype(float)
        df_itens["subtotal_retira"] = df_itens["subtotal_retira"].astype(float)
        df_itens["subtotal_final"] = df_itens["subtotal_final"].astype(float)

        df_show = df_itens[[
            "codigo", "produto", "unidade", "preco_retira",
            "quantidade", "subtotal_retira", "subtotal_final"
        ]].rename(columns={
            "codigo": "Código",
            "produto": "Produto",
            "unidade": "Unidade",
            "preco_retira": "Preço Retirada",
            "quantidade": "Qtde",
            "subtotal_retira": "Subtotal Retirada",
            "subtotal_final": "Total com Frete",
        })

        st.dataframe(df_show)

        total_final = df_itens["subtotal_final"].sum()
        st.markdown(f"### Total estimado (considerando forma de recebimento): R$ {total_final:.2f}")

        if st.button("Enviar cotação ao representante"):
            id_cot = salvar_cotacao(cliente_row, itens, forma_recebimento)
            if id_cot:
                st.success(f"Cotação enviada com sucesso! ID: {id_cot}")
                st.session_state["itens_cotacao"] = []
    else:
        st.info("Nenhum item na cotação ainda. Busque um produto e adicione.")


# =========================
# PÁGINA DO REPRESENTANTE
# =========================

def pagina_representante():
    st.header("Área do Representante - Cotações")

    cotacoes = load_cotacoes()
    itens_cot = load_itens_cotacao()

    if cotacoes.empty:
        st.info("Ainda não há cotações cadastradas.")
        return

    # Resumo rápido no topo
    cotacoes_stats = cotacoes.copy()
    cotacoes_stats["data_dt"] = pd.to_datetime(cotacoes_stats.get("data", None), errors="coerce")
    hoje = datetime.now().date()
    inicio_mes = hoje.replace(day=1)

    qtd_pendentes = int((cotacoes_stats["status"] == "PENDENTE").sum())
    qtd_aprovadas_hoje = int(
        ((cotacoes_stats["status"] == "APROVADA") & (cotacoes_stats["data_dt"].dt.date == hoje)).sum()
    )
    datas_aprov = cotacoes_stats["data_dt"].dt.date
    valor_mes = cotacoes_stats.loc[
        (cotacoes_stats["status"] == "APROVADA") & (datas_aprov >= inicio_mes),
        "total",
    ]
    valor_mes = pd.to_numeric(valor_mes, errors="coerce").fillna(0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Cotações pendentes", qtd_pendentes)
    col2.metric("Cotações aprovadas", qtd_aprovadas_hoje)
    col3.metric("Valor total (mês)", f"R$ {valor_mes:,.2f}")

    st.subheader("Lista de cotações")

    # Mostra um resumo, sem poluir demais
    colunas_lista = [
        "id", "cliente_nome", "data",
        "forma_recebimento", "status", "total"
    ]
    colunas_lista = [c for c in colunas_lista if c in cotacoes.columns]
    st.dataframe(cotacoes[colunas_lista])

    ids = cotacoes["id"].tolist()
    id_escolhido = st.selectbox(
        "Selecione uma cotação para detalhar:",
        [""] + ids,
        key="select_cotacao",
    )

    if not id_escolhido:
        return

    cot_row = cotacoes[cotacoes["id"] == id_escolhido].iloc[0]

    st.markdown("### Detalhes da cotação")

    st.markdown(f"**Cliente:** {cot_row['cliente_nome']}")
    st.markdown(f"**Telefone:** {cot_row['cliente_telefone']}")
    st.markdown(f"**Forma de recebimento:** {cot_row.get('forma_recebimento', '')}")
    st.markdown(f"**Status atual:** {cot_row['status']}")
    st.markdown(f"**Data:** {cot_row['data']}")

    try:
        total_original = float(cot_row.get("total_original", cot_row["total"]))
    except Exception:
        total_original = float(cot_row["total"])

    try:
        desconto_atual = float(cot_row.get("desconto_percentual", 0.0))
    except Exception:
        desconto_atual = 0.0

    st.markdown(f"**Total original (sem desconto):** R$ {total_original:.2f}")
    st.markdown(f"**Desconto aplicado:** {desconto_atual:.1f}%")
    st.markdown(f"**Total após desconto:** R$ {float(cot_row['total']):.2f}")

    st.markdown("---")
    st.subheader("Itens da cotação")

    itens = itens_cot[itens_cot["id_cotacao"] == id_escolhido]

    if itens.empty:
        st.warning("Nenhum item encontrado para essa cotação.")
    else:
        df_show = itens[[
            "codigo", "produto", "unidade",
            "quantidade", "preco_retira", "subtotal_retira",
            "preco_final", "subtotal_final"
        ]].rename(columns={
            "codigo": "Código",
            "produto": "Produto",
            "unidade": "Unidade",
            "quantidade": "Qtde",
            "preco_retira": "Preço Retirada",
            "subtotal_retira": "Subtotal Retirada",
            "preco_final": "Preço Final",
            "subtotal_final": "Subtotal Final",
        })

        st.dataframe(df_show)

        # Botão para baixar PDF
        pdf_bytes = gerar_pdf_cotacao(cot_row, itens)
        st.download_button(
            label="Baixar PDF da cotação",
            data=pdf_bytes,
            file_name=f"cotacao_{id_escolhido}.pdf",
            mime="application/pdf",
        )

    st.markdown("---")
    st.subheader("Aplicar / atualizar desconto")

    novo_desconto = st.number_input(
        "Desconto (%) sobre o total original",
        min_value=0.0,
        max_value=100.0,
        value=desconto_atual,
        step=0.5,
        key="desconto_input",
    )

    if st.button("Salvar desconto", key="btn_salvar_desconto"):
        novo_total = total_original * (1 - novo_desconto / 100.0)

        # Atualiza a linha no DataFrame e salva
        cotacoes.loc[cotacoes["id"] == id_escolhido, "desconto_percentual"] = novo_desconto
        cotacoes.loc[cotacoes["id"] == id_escolhido, "total_original"] = total_original
        cotacoes.loc[cotacoes["id"] == id_escolhido, "total"] = round(novo_total, 2)
        cotacoes.to_csv(COTACOES_PATH, index=False)

        st.success("✓ Desconto atualizado com sucesso!")
        st.rerun()

    st.markdown("---")
    st.subheader("Atualizar status da cotação")

    opcoes_status = ["PENDENTE", "APROVADA", "REPROVADA", "EM NEGOCIACAO"]
    status_atual = cot_row["status"] if cot_row["status"] in opcoes_status else "PENDENTE"

    novo_status = st.selectbox(
        "Novo status",
        opcoes_status,
        index=opcoes_status.index(status_atual),
        key="status_select",
    )

    if st.button("Salvar status", key="btn_salvar_status"):
        atualizar_status_cotacao(id_escolhido, novo_status)
        st.rerun()


# =========================
# MAIN
# =========================

def main():
    st.set_page_config(page_title=f"Cotações {REP_NAME}", layout="wide")

    st.markdown(
        """
        <style>
        /* Esconde o menu do Streamlit e o rodapé */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Fundo do app */
        [data-testid="stAppViewContainer"] {
            background-color: #ffffff;
        }

        /* Fundo da sidebar */
        [data-testid="stSidebar"] {
            background-color: #0b245c;
        }
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }
        [data-testid="stSidebar"] input {
            color: #0b245c !important;
            background-color: #f1f4fb !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.title("Cotação de Mercadorias")
    perfil = st.sidebar.radio("Você é:", ["Cliente", "Representante"])

    if perfil == "Cliente":
        pagina_cliente()
    else:
        st.sidebar.subheader("Acesso restrito")
        rep_code = st.sidebar.text_input(
            "Código de acesso do representante",
            type="password",
            key="rep_code",
        )

        if not rep_code:
            st.info("Informe o código de acesso do representante.")
            return

        if rep_code != REP_PASS:
            st.error("Código de acesso inválido.")
            return

        pagina_representante()


if __name__ == "__main__":
    main()
