"""
Módulo para gerenciar leitura, validação e sincronização de produtos
com Supabase.
ATUALIZADO:
- Limpeza rigorosa (substituição de tabela).
- Preservação apenas de histórico consolidado (Aprovadas/Canceladas).
- Recálculo automático de cotações PENDENTES.
"""

import logging
import pandas as pd
import numpy as np
import re
from typing import Optional, Tuple, List
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
    
    'preco_100a199km': 'preco_100a199km', 'preco100a199km': 'preco_100a199km',
    'preco_200a299km': 'preco_200a299km', 'preco200a299km': 'preco_200a299km',
    'preco_300a399km': 'preco_300a399km', 'preco300a399km': 'preco_300a399km',
    'preco_acima400km': 'preco_acima400km', 'precoac400km': 'preco_acima400km', 'precoacima400km': 'preco_acima400km',
    'preco_acima500km': 'preco_acima500km', 'precoac500km': 'preco_acima500km', 'precoacima500km': 'preco_acima500km',
    'preco_acima600km': 'preco_acima600km', 'precoac600km': 'preco_acima600km', 'precoacima600km': 'preco_acima600km',
}

COLUNAS_OBRIGATORIAS = ['codigo', 'produto']

# =====================================================================
# FUNÇÕES DE LEITURA E PARSING
# =====================================================================

def ler_arquivo(arquivo) -> Optional[pd.DataFrame]:
    try:
        nome_arquivo = arquivo.name.lower()
        if nome_arquivo.endswith('.csv'):
            tentativas = [
                {'sep': ',', 'encoding': 'utf-8', 'dtype': str},
                {'sep': ',', 'encoding': 'latin1', 'dtype': str},
                {'sep': ';', 'encoding': 'utf-8', 'dtype': str},
                {'sep': ';', 'encoding': 'latin1', 'dtype': str},
            ]
            for tent in tentativas:
                try:
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, **tent)
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

def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    # Remove linhas totalmente vazias
    df = df.dropna(how='all').copy()
    
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

    # Trata preços
    cols_preco = [c for c in df.columns if 'preco' in c]
    for c in cols_preco:
        df[c] = df[c].apply(converter_preco)
        
    return df

def converter_preco(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('R$', '').replace(' ', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except Exception: return 0.0

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

# =====================================================================
# SINCRONIZAÇÃO E RECÁLCULO (LÓGICA NOVA)
# =====================================================================

def calcular_impacto_sincronizacao(supabase, df: pd.DataFrame, representante_id: str, tabela: str = 'produtos') -> dict:
    """
    Calcula quantos produtos atuais serão removidos (excluindo os protegidos por histórico)
    ANTES de qualquer escrita no banco.
    """
    all_prods = (
        supabase.table(tabela)
        .select('id, codigo')
        .eq('representante_id', representante_id)
        .execute()
        .data
    ) or []

    total_atual = len(all_prods)
    if total_atual == 0 or df is None or df.empty:
        return {
            'total_atual': total_atual,
            'ids_final_delete': [],
            'qtd_removiveis': 0,
            'qtd_preservados': 0,
            'exige_confirmacao': False,
        }

    codigos_novos = set(df['codigo'].astype(str).tolist())
    ids_candidatos_exclusao = [p['id'] for p in all_prods if str(p['codigo']) not in codigos_novos]

    if not ids_candidatos_exclusao:
        return {
            'total_atual': total_atual,
            'ids_final_delete': [],
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
        for i in range(0, len(ids_candidatos_exclusao), 100):
            lote_prod = ids_candidatos_exclusao[i:i+100]
            resp = (
                supabase.table('cotacao_itens')
                .select('produto_id')
                .in_('produto_id', lote_prod)
                .in_('cotacao_id', ids_cot_protegidas)
                .execute()
            )
            for item in (resp.data or []):
                ids_produtos_protegidos.add(item['produto_id'])

    ids_final_delete = [id_ for id_ in ids_candidatos_exclusao if id_ not in ids_produtos_protegidos]
    qtd_removiveis = len(ids_final_delete)
    exige_confirmacao = (qtd_removiveis / total_atual) > 0.5

    return {
        'total_atual': total_atual,
        'ids_final_delete': ids_final_delete,
        'qtd_removiveis': qtd_removiveis,
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
    2. Atualiza/Insere produtos novos (Upsert).
    3. Remove produtos antigos que NÃO estão no arquivo, EXCETO se estiverem em cotações APROVADA/CANCELADA.
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
                f"Operação bloqueada: {impacto['qtd_removiveis']} de {impacto['total_atual']} produtos ativos seriam removidos. "
                "Marque a caixa de confirmação para continuar.",
                "error",
            )

        df = df.copy()
        df['representante_id'] = representante_id
        df['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # ---------------------------------------------------------
        # 1. UPSERT (Atualiza a base com a tabela nova)
        # ---------------------------------------------------------
        colunas_validas = {
            'representante_id', 'codigo', 'produto', 'unidade',
            'preco_retira', 'preco_entrega',
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km',
            'updated_at'
        }
        df = df[[c for c in df.columns if c in colunas_validas]].copy()
        records = df.to_dict('records')
        
        for r in records:
            for k, v in r.items():
                if pd.isna(v): r[k] = None
                
        batch_size = 100
        progresso = st.progress(0, text="Atualizando catálogo...")
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table(tabela).upsert(batch, on_conflict='representante_id, codigo').execute()
            progresso.progress(min((i+batch_size)/len(records), 0.8))
            
        # ---------------------------------------------------------
        # 2. LIMPEZA (Substituição Inteligente)
        # ---------------------------------------------------------
        ids_final_delete = impacto['ids_final_delete']
        qtd_preservados = impacto['qtd_preservados']
        qtd_removidos = 0
        
        if ids_final_delete:
            progresso.progress(0.85, text="Removendo itens fora de linha...")
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
            msg += f" 🛡️ {qtd_preservados} antigos mantidos por histórico."

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
    Atualiza os preços dos itens em cotações PENDENTES com base na nova tabela.
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
        
        prods_resp = supabase.table('produtos').select('*').eq('representante_id', representante_id).execute()
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
    st.write(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
    st.dataframe(df.head())






