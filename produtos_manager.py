"""
Módulo para gerenciar leitura, validação e sincronização de produtos
com Supabase. Suporta CSV, XLS e XLSX com normalização de colunas.
ATUALIZADO: Com proteção contra duplicatas e uso de UPSERT para corrigir erros 23502 e 23505.
"""

import pandas as pd
import numpy as np
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import streamlit as st
from datetime import datetime, timezone

# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

MAPA_COLUNAS = {
    # Código
    'codigo_1': 'codigo', 'codigo_item': 'codigo', 'codigoitem': 'codigo',
    'code': 'codigo', 'cod': 'codigo', 'item': 'codigo', 'sku': 'codigo',
    'product_code': 'codigo', 'productcode': 'codigo',
    
    # Produto/Nome
    'produto_1': 'produto', 'nome': 'produto', 'product': 'produto',
    'descricao': 'produto', 'descricao_do_produto': 'produto',
    'descricaodoproduto': 'produto', 'description': 'produto',
    'item_name': 'produto', 'nome_do_produto': 'produto', 'nomedoproduto': 'produto',
    
    # Unidade
    'unidade_1': 'unidade', 'unit': 'unidade', 'un': 'unidade', 'measurement': 'unidade',
    
    # Preços - Retirada
    'preco_retira_1': 'preco_retira', 'preco_retirada': 'preco_retira',
    'precoretirada': 'preco_retira', 'price_pickup': 'preco_retira',
    'pickup_price': 'preco_retira', 'retirada': 'preco_retira',
    'varejo': 'preco_retira', 'preco_varejo': 'preco_retira',
    'preco_unitario_retira': 'preco_retira', 'precounitarioretira': 'preco_retira',
    'retira': 'preco_retira', 'balcao': 'preco_retira', 'loja': 'preco_retira',
    
    # Preços - Entrega Geral
    'preco_entrega_1': 'preco_entrega', 'preco_entrega': 'preco_entrega',
    'precoentrega': 'preco_entrega', 'preco_delivery': 'preco_entrega',
    'precodelivery': 'preco_entrega', 'price_delivery': 'preco_entrega',
    'delivery_price': 'preco_entrega', 'atacado': 'preco_entrega',
    'preco_atacado': 'preco_entrega', 'entrega': 'preco_entrega', 
    'frete': 'preco_entrega', 'transporte': 'preco_entrega',
    
    # Preços por Distância
    'preco_100a199km': 'preco_100a199km', 'preco100a199km': 'preco_100a199km',
    'preco_100_199': 'preco_100a199km', 'price_100_199': 'preco_100a199km',
    
    'preco_200a299km': 'preco_200a299km', 'preco200a299km': 'preco_200a299km',
    'preco_200_299': 'preco_200a299km', 'price_200_299': 'preco_200a299km',
    
    'preco_300a399km': 'preco_300a399km', 'preco300a399km': 'preco_300a399km',
    'preco_300_399': 'preco_300a399km', 'price_300_399': 'preco_300a399km',
    
    'preco_acima400km': 'preco_acima400km', 'precoac400km': 'preco_acima400km',
    'preco_400': 'preco_acima400km', 'price_400': 'preco_acima400km',
    
    'preco_acima500km': 'preco_acima500km', 'precoac500km': 'preco_acima500km',
    'preco_500': 'preco_acima500km', 'price_500': 'preco_acima500km',
    
    'preco_acima600km': 'preco_acima600km', 'precoac600km': 'preco_acima600km',
    'preco_600': 'preco_acima600km', 'price_600': 'preco_acima600km',
    
    # Variações de preço geral (fallback)
    'preco': 'preco_padrao', 'price': 'preco_padrao', 'valor': 'preco_padrao',
}

COLUNAS_OBRIGATORIAS = ['codigo', 'produto']
COLUNAS_RECOMENDADAS = ['codigo', 'produto', 'unidade', 'retira', 'entrega']
EXTENSOES_SUPORTADAS = ['.csv', '.xls', '.xlsx']


# =====================================================================
# FUNÇÕES DE LEITURA E PARSING
# =====================================================================

def ler_arquivo(arquivo) -> Optional[pd.DataFrame]:
    """Lê arquivo CSV ou Excel com múltiplas estratégias."""
    try:
        nome_arquivo = arquivo.name.lower()
        if nome_arquivo.endswith('.csv'):
            tentativas = [
                {'sep': ',', 'encoding': 'utf-8', 'decimal': '.'},
                {'sep': ',', 'encoding': 'latin1', 'decimal': ','},
                {'sep': ';', 'encoding': 'utf-8', 'decimal': ','},
                {'sep': ';', 'encoding': 'latin1', 'decimal': ','},
                {'sep': '\t', 'encoding': 'utf-8', 'decimal': '.'},
            ]
            df = None
            erro_detalhado = None
            for tentativa in tentativas:
                try:
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, **tentativa)
                    if not df.empty and len(df.columns) > 1:
                        return df
                except Exception as e:
                    erro_detalhado = str(e)
                    continue
            if df is None:
                raise ValueError(f"Erro ao ler CSV. Detalhe: {erro_detalhado}")
        elif nome_arquivo.endswith(('.xls', '.xlsx')):
            tentativas_excel = [
                {'sheet_name': 0}, {'sheet_name': 'produtos'}, 
                {'sheet_name': 'Produtos'}, {'sheet_name': 'Sheet1'}
            ]
            for tentativa in tentativas_excel:
                try:
                    arquivo.seek(0)
                    df = pd.read_excel(arquivo, **tentativa)
                    if not df.empty:
                        return df
                except Exception:
                    continue
            raise ValueError("Erro ao ler Excel.")
        else:
            raise ValueError(f"Formato {Path(nome_arquivo).suffix} não suportado.")
    except Exception as e:
        raise Exception(f"Erro na leitura: {str(e)}")


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes das colunas."""
    def limpar_coluna(col: str) -> str:
        col = str(col).strip().lower()
        col = re.sub(r'[àáâãäå]', 'a', col)
        col = re.sub(r'[èéêë]', 'e', col)
        col = re.sub(r'[ìíîï]', 'i', col)
        col = re.sub(r'[òóôõö]', 'o', col)
        col = re.sub(r'[ùúûü]', 'u', col)
        col = re.sub(r'[ç]', 'c', col)
        col = re.sub(r'[^a-z0-9_]', '', col)
        col = re.sub(r'_+', '_', col)
        return col.strip('_')
    
    df.columns = [limpar_coluna(col) for col in df.columns]
    df = df.rename(columns=MAPA_COLUNAS)
    return df


def validar_dados(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Valida estrutura mínima."""
    mensagens = []
    faltando = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if faltando:
        mensagens.append(f"❌ Colunas obrigatórias faltando: {', '.join(faltando)}")
    if df.empty:
        mensagens.append("❌ Arquivo vazio.")
    
    validacoes = {'codigo': lambda x: str(x).strip() != '', 'produto': lambda x: str(x).strip() != ''}
    for col, val in validacoes.items():
        if col in df.columns:
            if not df[df[col].apply(val)].shape[0] == df.shape[0]:
                mensagens.append(f"⚠️ Existem linhas com {col} vazio.")
                
    return len([m for m in mensagens if m.startswith('❌')]) == 0, mensagens


def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa dados e garante UNICIDADE DO CÓDIGO para evitar erros de banco.
    """
    df = df.dropna(how='all').reset_index(drop=True)
    
    # 1. FORÇA O CÓDIGO PARA STRING AGORA (Vital para evitar duplicatas mistas)
    if 'codigo' in df.columns:
        # Converte tudo para string e remove espaços
        df['codigo'] = df['codigo'].apply(lambda x: str(x).strip() if pd.notna(x) else "")
        # Remove vazios
        df = df[df['codigo'] != ""]
        
        # Remove duplicatas exatas de código
        tamanho_antes = len(df)
        df = df.drop_duplicates(subset=['codigo'], keep='first')
        
        if len(df) < tamanho_antes:
            st.warning(f"⚠️ {tamanho_antes - len(df)} códigos duplicados foram removidos da planilha.")

    # 2. Limpa textos gerais
    for col in df.select_dtypes(include=['object']).columns:
        if col != 'codigo': 
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else x)
    
    # 3. Limpa preços
    for col in df.columns:
        if any(p in col.lower() for p in ['preco', 'retira', 'entrega', 'price', 'value']):
            df[col] = df[col].apply(converter_preco)
            
    return df


def converter_preco(valor) -> float:
    """Converte strings financeiras para float."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('R$', '').replace(' ', '').strip()
    if not texto or texto in ['-', 'n/a']: return 0.0
    
    if ',' in texto and '.' in texto:
        if texto.rindex(',') > texto.rindex('.'): texto = texto.replace('.', '').replace(',', '.') # BR
        else: texto = texto.replace(',', '') # US
    elif ',' in texto: texto = texto.replace(',', '.') # BR simples
    
    try: return float(texto)
    except: return 0.0


def processar_arquivo_produtos(arquivo) -> Optional[pd.DataFrame]:
    """Pipeline completo de processamento."""
    try:
        df = ler_arquivo(arquivo)
        df = normalizar_colunas(df)
        valido, msgs = validar_dados(df)
        for msg in msgs:
            if msg.startswith('❌'): st.error(msg)
            else: st.warning(msg)
        
        if not valido: return None
        
        df = limpar_dados(df)
        
        if 'updated_at' not in df.columns:
            df['updated_at'] = datetime.now(timezone.utc).isoformat()
            
        st.success(f"✅ Arquivo processado: {len(df)} produtos prontos.")
        return df
    except Exception as e:
        st.error(f"❌ Erro ao processar: {str(e)}")
        return None


# =====================================================================
# FUNÇÕES DE SINCRONIZAÇÃO COM SUPABASE (CORRIGIDA)
# =====================================================================

def sincronizar_produtos_supabase(
    supabase_client,
    df: pd.DataFrame,
    tabela: str = 'produtos',
    limpar_antes: bool = False, # Mudado padrão para False para segurança
    representante_id: str = None
) -> Tuple[bool, str]:
    """
    Sincroniza produtos usando UPSERT (Atualização inteligente).
    Resolve erros de chave duplicada e violação de chave estrangeira.
    """
    try:
        # ATENÇÃO: Ignoramos 'limpar_antes' aqui propositalmente para evitar 
        # o erro de chave estrangeira (FK Constraint) se houver cotações ativas.
        # Em vez de apagar, vamos apenas atualizar (Upsert).
        
        # Garante ID do representante
        if representante_id:
            df['representante_id'] = representante_id
        
        # Atualiza timestamp
        df['updated_at'] = datetime.now(timezone.utc).isoformat()

        # Prepara colunas permitidas (Evita erro se Excel tiver sujeira)
        colunas_db = [
            'representante_id', 'codigo', 'produto', 'unidade',
            'preco_retira', 'preco_entrega', 
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km',
            'updated_at'
        ]
        
        # Converte para lista de dicionários limpos
        records = []
        for _, row in df.iterrows():
            item = {}
            for col in colunas_db:
                if col in df.columns:
                    val = row[col]
                    # Trata NaN/NaT
                    if pd.isna(val) or val == "":
                        val = None
                    item[col] = val
            records.append(item)
            
        if not records:
            return True, "Nenhum dado para importar."

        # Processamento em Lotes com UPSERT
        TAMANHO_LOTE = 100
        sucesso = 0
        barra = st.progress(0)
        
        for i in range(0, len(records), TAMANHO_LOTE):
            lote = records[i:i+TAMANHO_LOTE]
            try:
                # --- A MÁGICA: UPSERT ---
                # on_conflict='representante_id, codigo' diz ao banco:
                # "Se essa combinação já existir, atualize os outros campos. Se não, crie novo."
                supabase_client.table(tabela).upsert(
                    lote, 
                    on_conflict='representante_id, codigo'
                ).execute()
                
                sucesso += len(lote)
            except Exception as e:
                erro_msg = str(e)
                # print(f"Erro Lote {i}: {erro_msg}")
                st.error(f"Erro no lote {i//TAMANHO_LOTE + 1}: {erro_msg}")
                # Continua tentando os próximos lotes
            
            barra.progress(min((i + TAMANHO_LOTE) / len(records), 1.0))
            
        return True, f"✅ Sincronização concluída! {sucesso} produtos atualizados/criados."

    except Exception as e:
        return False, f"❌ Erro crítico na sincronização: {str(e)}"


def exibir_preview_dados(df: pd.DataFrame, max_linhas: int = 5):
    """Exibe preview dos dados carregados"""
    st.subheader("📋 Preview dos Dados")
    with st.expander("Ver estrutura", expanded=False):
        col1, col2 = st.columns(2)
        col1.metric("Linhas", len(df))
        col2.metric("Colunas", len(df.columns))
    st.dataframe(df.head(max_linhas), use_container_width=True)




