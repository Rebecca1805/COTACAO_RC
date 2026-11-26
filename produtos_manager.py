"""
Módulo para gerenciar leitura, validação e sincronização de produtos
com Supabase.
ATUALIZADO:
- Limpeza rigorosa (substituição de tabela).
- Preservação apenas de histórico consolidado (Aprovadas/Canceladas).
- Recálculo automático de cotações PENDENTES.
"""

import io
import logging
import math
import pandas as pd
import numpy as np
import re
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import streamlit as st
from datetime import datetime, timezone

logger = logging.getLogger("rc_online")

# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

MAPA_COLUNAS = {
    # Código
    'codigo_1': 'codigo', 'codigo_item': 'codigo', 'codigoitem': 'codigo',
    'code': 'codigo', 'cod': 'codigo', 'item': 'codigo', 'sku': 'codigo',
    
    # Produto
    'produto_1': 'produto', 'nome': 'produto', 'product': 'produto',
    'descricao': 'produto', 'description': 'produto', 'descricaodoproduto': 'produto',
    
    # Unidade
    'unidade_1': 'unidade', 'unit': 'unidade', 'un': 'unidade',
    
    # Preços - Retirada
    'preco_retira_1': 'preco_retira', 'preco_retirada': 'preco_retira',
    'precoretirada': 'preco_retira', 'retirada': 'preco_retira',
    'retira': 'preco_retira', 'balcao': 'preco_retira', 'loja': 'preco_retira',
    
    # Preços - Entrega (Mapeamento padrão e distâncias)
    'preco_entrega_1': 'preco_entrega', 'preco_entrega': 'preco_entrega',
    'precoentrega': 'preco_entrega', 'entrega': 'preco_entrega',
    
    'preco_100a199km': 'preco_100a199km', 'preco100a199km': 'preco_100a199km', 'preco100199km': 'preco_100a199km',
    'preco_200a299km': 'preco_200a299km', 'preco200a299km': 'preco_200a299km', 'preco200299km': 'preco_200a299km',
    'preco_300a399km': 'preco_300a399km', 'preco300a399km': 'preco_300a399km', 'preco300399km': 'preco_300a399km',
    'preco_acima400km': 'preco_acima400km', 'precoac400km': 'preco_acima400km', 'precoacima400km': 'preco_acima400km',
    'preco_acima500km': 'preco_acima500km', 'precoac500km': 'preco_acima500km', 'precoacima500km': 'preco_acima500km',
    'preco_acima600km': 'preco_acima600km', 'precoac600km': 'preco_acima600km', 'precoacima600km': 'preco_acima600km',
}

NOMES_AMIGAVEIS_PRECO = {
    'preco_retira': 'Retira',
    'preco_entrega': 'Entrega (0 a 99 km)',
    'preco_100a199km': '100 a 199 km',
    'preco_200a299km': '200 a 299 km',
    'preco_300a399km': '300 a 399 km',
    'preco_acima400km': '400 a 500 km',
    'preco_acima500km': '501 a 600 km',
    'preco_acima600km': 'Acima de 600 km',
    'preco_unico': 'Preço Único',
}

COLUNAS_OBRIGATORIAS = ['codigo', 'produto']

# =====================================================================
# FUNÇÕES DE LEITURA E PARSING
# =====================================================================

def ler_arquivo(arquivo) -> Optional[pd.DataFrame]:
    try:
        nome_arquivo = arquivo.name.lower()
        if nome_arquivo.endswith('.csv'):
            arquivo.seek(0)
            raw_bytes = arquivo.read()

            texto = None
            for enc in ['utf-8-sig', 'utf-8', 'utf-16', 'latin1', 'cp1252']:
                try:
                    candidato = raw_bytes.decode(enc)
                    if '\x00' not in candidato:
                        texto = candidato
                        break
                except Exception:
                    continue

            if texto is None:
                raise ValueError("Codificação do CSV não reconhecida.")

            # Desembrulha linhas de dados caso o Excel tenha envolvido a linha inteira em aspas
            linhas = texto.splitlines()
            if len(linhas) >= 2 and not linhas[0].strip().startswith('"'):
                linhas_limpas = [linhas[0]]
                for linha in linhas[1:]:
                    l_strip = linha.strip()
                    if len(l_strip) >= 2 and l_strip.startswith('"') and l_strip.endswith('"'):
                        linhas_limpas.append(l_strip[1:-1].replace('""', '"'))
                    else:
                        linhas_limpas.append(linha)
                texto = '\n'.join(linhas_limpas)

            for sep in [',', ';', '\t']:
                try:
                    df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)
                    if len(df.columns) > 1:
                        return df
                except Exception:
                    continue

            raise ValueError("Não foi possível ler o CSV.")
            
        elif nome_arquivo.endswith(('.xls', '.xlsx')):
            arquivo.seek(0)
            return pd.read_excel(arquivo, dtype=str)
    except Exception:
        logger.exception("Falha ao ler arquivo de produtos")
        st.error("Não foi possível ler o arquivo enviado. Verifique se é um CSV ou Excel (.xls, .xlsx) válido.")
        return None
    
def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    def limpar(col):
        c = str(col).strip().lower()

        # troca caracteres acentuados comuns (preço -> preco)
        c = (
            c.replace("ç", "c")
             .replace("ã", "a")
             .replace("á", "a")
             .replace("à", "a")
             .replace("â", "a")
             .replace("é", "e")
             .replace("ê", "e")
             .replace("í", "i")
             .replace("ó", "o")
             .replace("ô", "o")
             .replace("õ", "o")
             .replace("ú", "u")
        )

        # remove símbolos/espaços, deixa só a-z, 0-9 e _
        c = re.sub(r'[^a-z0-9_]', '', c)

        # remove sufixo numérico no fim: entrega_1 -> entrega / entrega1 -> entrega
        c = re.sub(r'_\d+$', '', c)
        c = re.sub(r'\d+$', '', c)

        # colapsa underscores repetidos (se acontecer)
        c = re.sub(r'_+', '_', c).strip('_')

        return c

    # 1) limpeza básica
    df.columns = [limpar(c) for c in df.columns]

    # 2) resolve colunas duplicadas criadas pela limpeza (Excel faz isso direto)
    # Ex.: 'entrega' e 'entrega_1' -> ambos viram 'entrega'
    # Regra: mantém a primeira e renomeia as próximas com sufixo incremental
    cols = []
    contagem = {}
    for c in df.columns:
        if c not in contagem:
            contagem[c] = 0
            cols.append(c)
        else:
            contagem[c] += 1
            cols.append(f"{c}_{contagem[c]}")
    df.columns = cols

    # 3) rename usando o mapa (seu MAPA_COLUNAS deve mapear: entrega -> preco_entrega etc.)
    df = df.rename(columns=MAPA_COLUNAS)

    return df

def validar_dados(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    msgs = []
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando: msgs.append(f"❌ Faltando colunas: {faltando}")
    return len(faltando) == 0, msgs

def interpretar_preco(val) -> Tuple[float, bool, str]:
    """
    Converte valor no padrão brasileiro (1234,56 ou 1.234,56) para float.
    Retorna (valor_float, eh_valido, texto_original).
    Células vazias retornam (0.0, True, '') para não gerar falso alerta.
    """
    if val is None or pd.isna(val):
        return 0.0, True, ""

    if isinstance(val, (int, float)):
        num = float(val)
        if math.isnan(num) or math.isinf(num) or num < 0:
            return 0.0, False, str(val)
        return num, True, str(val)

    texto_original = str(val).strip()
    if texto_original == "" or texto_original.lower() in {"nan", "none", "null"}:
        return 0.0, True, ""

    s = texto_original.replace('R$', '').replace('r$', '').replace(' ', '').strip()
    if s == "":
        return 0.0, False, texto_original

    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')

    try:
        num = float(s)
        if math.isnan(num) or math.isinf(num) or num < 0:
            return 0.0, False, texto_original
        return num, True, texto_original
    except Exception:
        return 0.0, False, texto_original

def converter_preco(val) -> float:
    """Mantém compatibilidade retornando apenas o float convertido."""
    valor, _, _ = interpretar_preco(val)
    return valor

def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    # Guarda o número da linha original da planilha (linha 1 = cabeçalho, linha 2 = 1º dado)
    df = df.copy()
    df['_linha_planilha'] = df.index + 2

    # Remove linhas totalmente vazias
    colunas_dados = [c for c in df.columns if c != '_linha_planilha']
    df = df.dropna(subset=colunas_dados, how='all').copy()
    
    # Garante código como string limpa e remove vazios / 'nan'
    if 'codigo' in df.columns:
        df['codigo'] = df['codigo'].fillna('').astype(str).str.strip()
        df = df[
            (df['codigo'] != '') &
            (df['codigo'].str.lower() != 'nan') &
            (df['codigo'].str.lower() != 'none')
        ]
        # Remove duplicatas de código no arquivo (mantém o último)
        df = df.drop_duplicates(subset=['codigo'], keep='last')

    # Garante que produto também não esteja vazio
    if 'produto' in df.columns:
        df['produto'] = df['produto'].fillna('').astype(str).str.strip()
        df = df[
            (df['produto'] != '') &
            (df['produto'].str.lower() != 'nan') &
            (df['produto'].str.lower() != 'none')
        ]

    # Trata preços e coleta avisos de linha/coluna para textos inválidos
    avisos_precos: List[Dict[str, Any]] = []
    cols_preco = [c for c in df.columns if 'preco' in c]

    for c in cols_preco:
        valores_convertidos = []
        nome_col_amigavel = NOMES_AMIGAVEIS_PRECO.get(c, c)

        for _, row in df.iterrows():
            val_float, valido, texto_orig = interpretar_preco(row[c])
            valores_convertidos.append(val_float)

            if not valido:
                avisos_precos.append({
                    'linha': int(row['_linha_planilha']),
                    'coluna': nome_col_amigavel,
                    'codigo': str(row.get('codigo', '')),
                    'produto': str(row.get('produto', '')),
                    'valor': texto_orig,
                })

        df[c] = valores_convertidos

    df = df.drop(columns=['_linha_planilha'], errors='ignore')
    df.attrs['avisos_precos'] = avisos_precos
    return df

def processar_arquivo_produtos(arquivo):
    df = ler_arquivo(arquivo)
    if df is None: return None
    
    df = normalizar_colunas(df)
    valido, msgs = validar_dados(df)
    
    if not valido:
        for m in msgs: st.error(m)
        return None

    df_limpo = limpar_dados(df)
    if df_limpo.empty:
        st.error("❌ O arquivo enviado não possui produtos válidos (verifique se as colunas Código e Produto estão preenchidas).")
        return None
        
    return df_limpo

def calcular_impacto_sincronizacao(supabase, df: pd.DataFrame, representante_id: str, tabela: str = 'produtos') -> dict:
    """
    Calcula quantos produtos ativos serão removidos ou inativados (preservados por histórico)
    ANTES de qualquer escrita no banco.
    """
    all_prods = (
        supabase.table(tabela)
        .select('id, codigo, ativo')
        .eq('representante_id', representante_id)
        .execute()
        .data
    ) or []

    prods_ativos = [p for p in all_prods if p.get('ativo', True)]
    total_atual = len(prods_ativos)

    if not all_prods or df is None or df.empty:
        return {
            'total_atual': total_atual,
            'ids_final_delete': [],
            'ids_para_inativar': [],
            'qtd_removiveis': 0,
            'qtd_preservados': 0,
            'exige_confirmacao': False,
        }

    codigos_novos = set(df['codigo'].astype(str).tolist())
    ids_candidatos_saida = [p['id'] for p in all_prods if str(p['codigo']) not in codigos_novos]
    qtd_ativos_saindo = len([p for p in prods_ativos if str(p['codigo']) not in codigos_novos])

    if not ids_candidatos_saida:
        return {
            'total_atual': total_atual,
            'ids_final_delete': [],
            'ids_para_inativar': [],
            'qtd_removiveis': 0,
            'qtd_preservados': 0,
            'exige_confirmacao': False,
        }

    cot_protegidas = (
        supabase.table('cotacoes')
        .select('id')
        .neq('status', 'PENDENTE')
        .eq('representante_id', representante_id)
        .execute()
        .data
    ) or []

    ids_cot_protegidas = [c['id'] for c in cot_protegidas]
    ids_produtos_protegidos = set()

    if ids_cot_protegidas:
        for i in range(0, len(ids_candidatos_saida), 100):
            lote_prod = ids_candidatos_saida[i:i+100]
            resp = (
                supabase.table('cotacao_itens')
                .select('produto_id')
                .in_('produto_id', lote_prod)
                .in_('cotacao_id', ids_cot_protegidas)
                .execute()
            )
            for item in (resp.data or []):
                ids_produtos_protegidos.add(item['produto_id'])

    ids_final_delete = [id_ for id_ in ids_candidatos_saida if id_ not in ids_produtos_protegidos]
    ids_para_inativar = [
        p['id'] for p in prods_ativos
        if p['id'] in ids_produtos_protegidos
    ]

    exige_confirmacao = (total_atual > 0) and ((qtd_ativos_saindo / total_atual) > 0.5)

    return {
        'total_atual': total_atual,
        'ids_final_delete': ids_final_delete,
        'ids_para_inativar': ids_para_inativar,
        'qtd_removiveis': qtd_ativos_saindo,
        'qtd_preservados': len(ids_produtos_protegidos),
        'exige_confirmacao': exige_confirmacao,
    }


def sincronizar_produtos_supabase(
    supabase,
    df,
    tabela='produtos',
    limpar_antes=False,
    representante_id=None,
    confirmar_exclusao_em_massa=False
):
    """
    1. Valida impacto antes de qualquer alteração no banco.
    2. Atualiza/Insere produtos novos (Upsert) marcando ativo = True.
    3. Remove produtos fora da planilha sem histórico e marca ativo = False nos que têm histórico.
    4. Atualiza preços das cotações PENDENTES.
    Retorna (sucesso: bool, mensagem: str, nivel: 'success' | 'warning' | 'error').
    """
    progresso = None
    try:
        if not representante_id:
            return False, "ID do representante não fornecido.", "error"

        if df is None or df.empty:
            return False, "O arquivo enviado não contém produtos válidos. Nenhuma alteração foi feita no catálogo.", "error"

        # ---------------------------------------------------------
        # 0. TRAVA DE SEGURANÇA ANTES DE QUALQUER GRAVAÇÃO
        # ---------------------------------------------------------
        impacto = calcular_impacto_sincronizacao(supabase, df, representante_id, tabela=tabela)
        if impacto['exige_confirmacao'] and not confirmar_exclusao_em_massa:
            return (
                False,
                f"Operação bloqueada: {impacto['qtd_removiveis']} de {impacto['total_atual']} produtos ativos sairiam do catálogo. "
                "Marque a caixa de confirmação para continuar.",
                "error",
            )

        agora_iso = datetime.now(timezone.utc).isoformat()
        df = df.copy()
        df['representante_id'] = representante_id
        df['updated_at'] = agora_iso
        df['ativo'] = True
        
        # ---------------------------------------------------------
        # 1. UPSERT (Atualiza/reativa a base com a tabela nova)
        # ---------------------------------------------------------
        colunas_validas = {
            'representante_id', 'codigo', 'produto', 'unidade',
            'preco_retira', 'preco_entrega',
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km',
            'updated_at', 'ativo'
        }
        df = df[[c for c in df.columns if c in colunas_validas]].copy()
        records = df.to_dict('records')
        
        for r in records:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
                
        batch_size = 100
        progresso = st.progress(0, text="Atualizando catálogo...")
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table(tabela).upsert(batch, on_conflict='representante_id, codigo').execute()
            progresso.progress(min((i+batch_size)/len(records), 0.75))
            
        # ---------------------------------------------------------
        # 2. LIMPEZA E INATIVAÇÃO (Substituição Inteligente)
        # ---------------------------------------------------------
        ids_final_delete = impacto['ids_final_delete']
        ids_para_inativar = impacto['ids_para_inativar']
        qtd_preservados = impacto['qtd_preservados']
        qtd_removidos = 0
        
        if ids_final_delete:
            progresso.progress(0.80, text="Removendo itens fora de linha sem histórico...")
            cot_pend = (
                supabase.table('cotacoes')
                .select('id')
                .eq('representante_id', representante_id)
                .eq('status', 'PENDENTE')
                .execute()
                .data
            ) or []
            ids_cot_pend = [c['id'] for c in cot_pend]

            if ids_cot_pend:
                for i in range(0, len(ids_final_delete), 100):
                    lote_prod = ids_final_delete[i:i+100]
                    for j in range(0, len(ids_cot_pend), 100):
                        lote_cot = ids_cot_pend[j:j+100]
                        (
                            supabase.table('cotacao_itens')
                            .delete()
                            .in_('produto_id', lote_prod)
                            .in_('cotacao_id', lote_cot)
                            .execute()
                        )

            for i in range(0, len(ids_final_delete), 100):
                lote_del = ids_final_delete[i:i+100]
                supabase.table(tabela).delete().in_('id', lote_del).execute()

            qtd_removidos = len(ids_final_delete)

        if ids_para_inativar:
            progresso.progress(0.85, text="Inativando itens antigos com histórico...")
            for i in range(0, len(ids_para_inativar), 100):
                lote_inativar = ids_para_inativar[i:i+100]
                (
                    supabase.table(tabela)
                    .update({'ativo': False, 'updated_at': agora_iso})
                    .in_('id', lote_inativar)
                    .execute()
                )

        # ---------------------------------------------------------
        # 3. RECÁLCULO DE COTAÇÕES PENDENTES
        # ---------------------------------------------------------
        progresso.progress(0.9, text="Atualizando preços das cotações pendentes...")
        qtd_cotacoes_atualizadas, recalculo_ok = recalcular_cotacoes_pendentes(supabase, representante_id)
        
        if progresso:
            progresso.empty()
        
        msg = f"✅ Sucesso! {len(records)} produtos ativos."
        if qtd_removidos > 0:
            msg += f" 🗑️ {qtd_removidos} fora de linha removidos."
        if qtd_preservados > 0:
            msg += f" 🛡️ {qtd_preservados} descontinuados ocultados da busca e mantidos no histórico."

        if not recalculo_ok:
            msg += " ⚠️ Tabela atualizada, mas não foi possível recalcular as cotações pendentes automaticamente."
            return True, msg, "warning"

        if qtd_cotacoes_atualizadas > 0:
            msg += f" 🔄 {qtd_cotacoes_atualizadas} cotações pendentes atualizadas."
        
        return True, msg, "success"

    except Exception:
        if progresso:
            progresso.empty()
        logger.exception("Falha crítica ao sincronizar produtos no Supabase")
        return False, "Não foi possível atualizar a tabela de preços no momento. Confira o arquivo e tente novamente.", "error"


def recalcular_cotacoes_pendentes(supabase, representante_id):
    """
    Atualiza os preços dos itens em cotações PENDENTES com base na nova tabela ativa.
    Retorna (quantidade_atualizada, sucesso_booleano).
    """
    try:
        resp = supabase.table('cotacoes')\
            .select('id, forma_recebimento, clientes(coluna_preco)')\
            .eq('representante_id', representante_id)\
            .eq('status', 'PENDENTE')\
            .execute()
        
        cotacoes_pendentes = resp.data
        if not cotacoes_pendentes:
            return 0, True
        
        prods_resp = (
            supabase.table('produtos')
            .select('*')
            .eq('representante_id', representante_id)
            .eq('ativo', True)
            .execute()
        )
        mapa_produtos = {p['codigo']: p for p in prods_resp.data}
        
        count_atualizadas = 0
        
        for cot in cotacoes_pendentes:
            cot_id = cot['id']
            forma_recebimento = cot.get('forma_recebimento')
            
            cliente_data = cot.get('clientes') or {}
            coluna_cliente = cliente_data.get('coluna_preco') or 'preco_entrega'
            
            if forma_recebimento == 'Retirada no centro de distribuição':
                coluna_preco_target = 'preco_retira'
            else:
                coluna_preco_target = coluna_cliente
            
            itens_resp = supabase.table('cotacao_itens').select('*').eq('cotacao_id', cot_id).execute()
            itens = itens_resp.data
            
            total_original_novo = 0.0
            teve_alteracao = False
            
            for item in itens:
                cod_prod = item['codigo']
                
                if cod_prod in mapa_produtos:
                    prod_novo = mapa_produtos[cod_prod]
                    novo_preco_base = float(prod_novo.get(coluna_preco_target) or 0.0)
                    qtd = float(item['quantidade'])
                    desconto = float(item.get('desconto_percentual') or 0.0)
                    novo_subtotal = (novo_preco_base * qtd) * (1 - desconto/100)
                    
                    supabase.table('cotacao_itens').update({
                        'preco_unitario': novo_preco_base,
                        'subtotal': novo_subtotal,
                        'produto': prod_novo.get('produto'),
                        'unidade': prod_novo.get('unidade')
                    }).eq('id', item['id']).execute()
                    
                    total_original_novo += novo_subtotal
                    teve_alteracao = True
                else:
                    total_original_novo += float(item['subtotal'])
            
            if teve_alteracao:
                cot_full = supabase.table('cotacoes').select('desconto_geral_percentual').eq('id', cot_id).single().execute()
                desc_geral = float(cot_full.data.get('desconto_geral_percentual') or 0.0)
                novo_total_final = total_original_novo * (1 - desc_geral/100)
                
                supabase.table('cotacoes').update({
                    'total_original': total_original_novo,
                    'total_final': novo_total_final
                }).eq('id', cot_id).execute()
                
                count_atualizadas += 1
                
        return count_atualizadas, True

    except Exception:
        logger.exception("Falha ao recalcular cotações pendentes")
        return 0, False

def exibir_preview_dados(df: pd.DataFrame):
    avisos_precos = df.attrs.get('avisos_precos', [])
    if avisos_precos:
        st.warning(
            f"⚠️ Atenção: encontramos **{len(avisos_precos)}** célula(s) com texto inválido nas colunas de preço. "
            "Se você continuar, esses campos serão gravados como **R$ 0,00**."
        )
        with st.expander("🔍 Ver linhas e colunas com preço inválido", expanded=True):
            df_avisos = pd.DataFrame(avisos_precos).rename(columns={
                'linha': 'Linha na planilha',
                'coluna': 'Coluna',
                'codigo': 'Código',
                'produto': 'Produto',
                'valor': 'Valor encontrado',
            })
            st.dataframe(df_avisos, hide_index=True, width="stretch")

    st.write(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
    st.dataframe(df.head())




