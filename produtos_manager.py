"""
Módulo para gerenciar leitura, validação e sincronização de produtos
com Supabase. Suporta CSV, XLS e XLSX com normalização de colunas.
"""

import pandas as pd
import numpy as np
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import streamlit as st


# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

# Mapa de variações de nomes de colunas para padrão normalizado
MAPA_COLUNAS = {
    # Código
    'codigo_1': 'codigo',
    'codigo_item': 'codigo',
    'codigoitem': 'codigo',
    'code': 'codigo',
    'cod': 'codigo',
    'item': 'codigo',
    'sku': 'codigo',
    'product_code': 'codigo',
    'productcode': 'codigo',
    
    
    # Produto/Nome
    'produto_1': 'produto',
    'nome': 'produto',
    'product': 'produto',
    'descricao': 'produto',
    'descricao_do_produto': 'produto',
    'descricaodoproduto': 'produto',
    'description': 'produto',
    'item_name': 'produto',
    'nome_do_produto': 'produto',
    'nomedoproduto': 'produto',
    
    # Unidade
    'unidade_1': 'unidade',
    'unit': 'unidade',
    'un': 'unidade',
    'measurement': 'unidade',
    
    # Preços - Retirada
    'preco_retira_1': 'preco_retira',
    'preco_retirada': 'preco_retira',
    'precoretirada': 'preco_retira',
    'price_pickup': 'preco_retira',
    'pickup_price': 'preco_retira',
    'retirada': 'preco_retira',
    'varejo': 'preco_retira',
    'preco_varejo': 'preco_retira',
    'preco_unitario_retira': 'preco_retira',
    'precounitarioretira': 'preco_retira',
    'retira': 'preco_retira',
    'balcao': 'preco_retira',
    'loja': 'preco_retira',
    
    # Preços - Entrega Geral (fallback para preco_entrega)
    'preco_entrega_1': 'preco_entrega',
    'preco_entrega': 'preco_entrega',
    'precoentrega': 'preco_entrega',
    'preco_delivery': 'preco_entrega',
    'precodelivery': 'preco_entrega',
    'price_delivery': 'preco_entrega',
    'delivery_price': 'preco_entrega',
    'atacado': 'preco_entrega',
    'preco_atacado': 'preco_entrega',
    'entrega': 'preco_entrega', 
    'frete': 'preco_entrega',
    'transporte': 'preco_entrega',
    
    # Preços por Distância (100-199km)
    'preco_100a199km': 'preco_100a199km',
    'preco100a199km': 'preco_100a199km',
    'preco_100_199': 'preco_100a199km',
    'price_100_199': 'preco_100a199km',
    
    # Preços por Distância (200-299km)
    'preco_200a299km': 'preco_200a299km',
    'preco200a299km': 'preco_200a299km',
    'preco_200_299': 'preco_200a299km',
    'price_200_299': 'preco_200a299km',
    
    # Preços por Distância (300-399km)
    'preco_300a399km': 'preco_300a399km',
    'preco300a399km': 'preco_300a399km',
    'preco_300_399': 'preco_300a399km',
    'price_300_399': 'preco_300a399km',
    
    # Preços por Distância (acima 400km)
    'preco_acima400km': 'preco_acima400km',
    'precoac400km': 'preco_acima400km',
    'preco_400': 'preco_acima400km',
    'price_400': 'preco_acima400km',
    
    # Preços por Distância (acima 500km)
    'preco_acima500km': 'preco_acima500km',
    'precoac500km': 'preco_acima500km',
    'preco_500': 'preco_acima500km',
    'price_500': 'preco_acima500km',
    
    # Preços por Distância (acima 600km)
    'preco_acima600km': 'preco_acima600km',
    'precoac600km': 'preco_acima600km',
    'preco_600': 'preco_acima600km',
    'price_600': 'preco_acima600km',
    
    # Variações de preço geral (fallback)
    'preco': 'preco_padrao',
    'price': 'preco_padrao',
    'valor': 'preco_padrao',
}

# Colunas obrigatórias mínimas
COLUNAS_OBRIGATORIAS = ['codigo', 'produto']

# Colunas altamente recomendadas
COLUNAS_RECOMENDADAS = ['codigo', 'produto', 'unidade', 'retira', 'entrega']

# Extensões suportadas
EXTENSOES_SUPORTADAS = ['.csv', '.xls', '.xlsx']


# =====================================================================
# FUNÇÕES DE LEITURA E PARSING
# =====================================================================

def ler_arquivo(arquivo) -> Optional[pd.DataFrame]:
    """
    Lê arquivo CSV ou Excel com múltiplas estratégias de encoding.
    Retorna DataFrame ou None se falhar.
    """
    try:
        nome_arquivo = arquivo.name.lower()
        
        if nome_arquivo.endswith('.csv'):
            # Tenta diferentes combinações de separador e encoding
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
                    arquivo.seek(0)  # Volta ao início do arquivo
                    df = pd.read_csv(arquivo, **tentativa)
                    if not df.empty and len(df.columns) > 1:
                        return df
                except Exception as e:
                    erro_detalhado = str(e)
                    continue
            
            if df is None:
                raise ValueError(
                    f"Não foi possível ler o CSV. "
                    f"Verifique separadores (vírgula, ponto-e-vírgula ou tab) "
                    f"e encoding (UTF-8 ou Latin1). Erro: {erro_detalhado}"
                )
                
        elif nome_arquivo.endswith(('.xls', '.xlsx')):
            # Para Excel, tenta ler a primeira aba
            tentativas_excel = [
                {'sheet_name': 0},
                {'sheet_name': 'produtos'},
                {'sheet_name': 'Produtos'},
                {'sheet_name': 'Sheet1'},
            ]
            
            for tentativa in tentativas_excel:
                try:
                    arquivo.seek(0)
                    df = pd.read_excel(arquivo, **tentativa)
                    if not df.empty:
                        return df
                except Exception:
                    continue
            
            raise ValueError(
                "Não foi possível ler o arquivo Excel. "
                "Verifique se tem dados na primeira aba ou em abas nomeadas 'produtos'."
            )
        else:
            raise ValueError(
                f"Formato não suportado: {Path(nome_arquivo).suffix}. "
                f"Use CSV, XLS ou XLSX."
            )
            
    except Exception as e:
        raise Exception(f"Erro ao ler arquivo: {str(e)}")


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nomes de colunas:
    1. Remove espaços, converte para minúsculas
    2. Remove caracteres especiais
    3. Aplica mapa de correção
    4. Retorna DataFrame com colunas padronizadas
    """
    # Função auxiliar para limpar nome de coluna
    def limpar_coluna(col: str) -> str:
        """Remove espaços, caracteres especiais e converte para minúscula"""
        col = str(col).strip().lower()
        # Remove acentos
        col = re.sub(r'[àáâãäå]', 'a', col)
        col = re.sub(r'[èéêë]', 'e', col)
        col = re.sub(r'[ìíîï]', 'i', col)
        col = re.sub(r'[òóôõö]', 'o', col)
        col = re.sub(r'[ùúûü]', 'u', col)
        col = re.sub(r'[ç]', 'c', col)
        # Remove caracteres especiais mas mantém underscore
        col = re.sub(r'[^a-z0-9_]', '', col)
        # Remove underscores múltiplos
        col = re.sub(r'_+', '_', col)
        # Remove underscores nas pontas
        col = col.strip('_')
        return col
    
    # Limpa todos os nomes de colunas
    df.columns = [limpar_coluna(col) for col in df.columns]
    
    # Aplica o mapa de correção
    df = df.rename(columns=MAPA_COLUNAS)
    
    return df


def validar_dados(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Valida se DataFrame tem estrutura mínima aceitável.
    Retorna (válido: bool, mensagens: List[str])
    """
    mensagens = []
    
    # Verifica colunas obrigatórias
    faltando = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if faltando:
        mensagens.append(
            f"❌ Colunas obrigatórias faltando: {', '.join(faltando)}"
        )
    
    # Verifica se tem linhas
    if df.empty:
        mensagens.append("❌ Arquivo vazio ou sem dados.")
    
    # Valida tipos de dados
    validacoes_tipo = {
        'codigo': lambda x: str(x).strip() != '',
        'produto': lambda x: str(x).strip() != '',
    }
    
    for coluna, validador in validacoes_tipo.items():
        if coluna in df.columns:
            linhas_invalidas = df[~df[coluna].apply(validador)].index.tolist()
            if linhas_invalidas:
                mensagens.append(
                    f"⚠️ {len(linhas_invalidas)} linhas com {coluna} vazio(s)"
                )
    
    # Aviso de colunas faltando (não-obrigatórias mas recomendadas)
    faltando_recomendadas = [
        col for col in COLUNAS_RECOMENDADAS 
        if col not in df.columns and col not in COLUNAS_OBRIGATORIAS
    ]
    if faltando_recomendadas:
        mensagens.append(
            f"⚠️ Colunas recomendadas faltando: {', '.join(faltando_recomendadas)}"
        )
    
    valido = len([m for m in mensagens if m.startswith('❌')]) == 0
    
    return valido, mensagens


def limpar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa dados: remove linhas vazias, normaliza preços e garante unicidade do código.
    """
    # Remove linhas completamente vazias
    df = df.dropna(how='all')
    
    # Reseta índice
    df = df.reset_index(drop=True)
    
    # --- CORREÇÃO PRINCIPAL AQUI ---
    # Normaliza a coluna 'codigo' para garantir que '7726' (int) e '7726' (str) sejam iguais
    if 'codigo' in df.columns:
        # Converte para string e remove espaços extras
        df['codigo'] = df['codigo'].apply(lambda x: str(x).strip() if pd.notna(x) else "")
        # Remove códigos vazios que possam ter restado
        df = df[df['codigo'] != ""]
        
        tamanho_antes = len(df)
        # Agora o drop_duplicates vai funcionar independente da formatação no Excel
        df = df.drop_duplicates(subset=['codigo'], keep='first')
        
        if len(df) < tamanho_antes:
            st.warning(f"⚠️ {tamanho_antes - len(df)} linhas com códigos duplicados foram removidas.")

    # Remove espaços em branco das outras células de texto
    for col in df.select_dtypes(include=['object']).columns:
        if col != 'codigo': # Já tratamos o código acima
            df[col] = df[col].apply(
                lambda x: str(x).strip() if pd.notna(x) else x
            )
    
    # Limpa colunas de preço
    colunas_preco = ['retira', 'entrega', 'preco_padrao', 'preco_unitario']
    for col in df.columns:
        if any(preco in col.lower() for preco in ['preco', 'retira', 'entrega', 'price', 'value']):
            df[col] = df[col].apply(converter_preco)
    
    return df

def converter_preco(valor) -> float:
    """
    Converte valor para float, tratando múltiplos formatos:
    - "1.234,56" (brasileiro) -> 1234.56
    - "1,234.56" (americano) -> 1234.56
    - "1234.56" (padrão) -> 1234.56
    - "R$ 1.000,00" -> 1000.00
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)
    
    texto = str(valor).strip()
    
    # Remove R$, espaços
    texto = texto.replace('R$', '').replace(' ', '').strip()
    
    if not texto or texto == '-' or texto.lower() == 'n/a':
        return 0.0
    
    # Detecta se é formato brasileiro ou americano
    # Se tiver ponto E vírgula: deve ser brasileiro (1.000,00)
    if ',' in texto and '.' in texto:
        if texto.rindex(',') > texto.rindex('.'):
            # Brasileiro: 1.000,00
            texto = texto.replace('.', '').replace(',', '.')
        else:
            # Americano: 1,000.00
            texto = texto.replace(',', '')
    elif ',' in texto:
        # Só tem vírgula, assume brasileiro
        texto = texto.replace(',', '.')
    
    try:
        return float(texto)
    except ValueError:
        return 0.0


def processar_arquivo_produtos(arquivo) -> Optional[pd.DataFrame]:
    """
    Pipeline completo: ler -> normalizar -> validar -> limpar
    Retorna DataFrame pronto para Supabase ou None se falhar.
    """
    try:
        # 1. Ler arquivo
        df = ler_arquivo(arquivo)
        
        # 2. Normalizar colunas
        df = normalizar_colunas(df)
        
        # 3. Validar
        valido, mensagens = validar_dados(df)
        for msg in mensagens:
            if msg.startswith('❌'):
                st.error(msg)
            else:
                st.warning(msg)
        
        if not valido:
            return None
        
        # 4. Limpar
        df = limpar_dados(df)
        
        # 5. Adicionar timestamp se não tiver
        if 'updated_at' not in df.columns:
            df['updated_at'] = pd.Timestamp.now().isoformat()
        
        st.success(f"✅ Arquivo processado com sucesso! {len(df)} produtos carregados.")
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo: {str(e)}")
        return None


# =====================================================================
# FUNÇÕES DE SINCRONIZAÇÃO COM SUPABASE
# =====================================================================

def sincronizar_produtos_supabase(
    supabase_client,
    df: pd.DataFrame,
    tabela: str = 'produtos',
    limpar_antes: bool = True,
    representante_id: str = None
) -> Tuple[bool, str]:
    """
    Sincroniza produtos com Supabase:
    1. (Opcional) Limpa tabela antiga
    2. Insere novos produtos com múltiplos preços por distância
    3. Retorna (sucesso: bool, mensagem: str)
    """
    try:
        # 1. Limpar dados antigos (opcional)
        if limpar_antes:
            try:
                if representante_id:
                    # Limpa só os produtos deste representante
                    supabase_client.table(tabela).delete().eq(
                        'representante_id', representante_id
                    ).execute()
                    st.info(f"🗑️ Produtos anteriores do representante deletados")
                else:
                    # Limpa tudo (cuidado!)
                    supabase_client.table(tabela).delete().neq(
                        'id', 'non-existent'
                    ).execute()
                    st.info("🗑️ Tabela de produtos limpa")
            except Exception as e:
                st.warning(f"⚠️ Não foi possível limpar tabela anterior: {e}")
        
        # 2. Preparar dados para inserção
        records = []
        colunas_preco_distancia = [
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km'
        ]

        # --- PROTEÇÃO: LISTA DE COLUNAS PERMITIDAS NO BANCO ---
        # Isso evita o erro PGRST204 se o Excel tiver colunas extras
        colunas_permitidas = [
            'representante_id', 'codigo', 'produto', 'unidade',
            'preco_retira', 'preco_entrega', 
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km',
            'created_at', 'updated_at'
        ]
        
        for idx, row in df.iterrows():
            record = {
                'codigo': str(row.get('codigo', '')).strip(),
                'produto': str(row.get('produto', '')).strip(),
                'unidade': str(row.get('unidade', 'UN')).strip() or 'UN',
                'preco_retira': float(row.get('preco_retira', 0)) or 0.0,
                'preco_entrega': float(row.get('preco_entrega', 0)) or 0.0,
                'updated_at': row.get('updated_at', pd.Timestamp.now().isoformat()),
            }
            
            # Adiciona preços por distância se existirem
            for col_dist in colunas_preco_distancia:
                if col_dist in df.columns:
                    valor = row.get(col_dist, 0)
                    record[col_dist] = float(valor) if pd.notna(valor) else 0.0
            
            # Adiciona representante se fornecido
            if representante_id:
                record['representante_id'] = representante_id
            
            # Adiciona outras colunas APENAS SE existirem no banco
            for col in df.columns:
                if col not in record and col in colunas_permitidas:
                    try:
                        val = row[col]
                        # Converte NaN para None (null no SQL)
                        if pd.isna(val):
                            val = None
                        record[col] = val
                    except:
                        pass
            
            records.append(record)
        
        # 3. Inserir em lotes (melhor performance)
        tamanho_lote = 100
        total_inseridos = 0
        
        for i in range(0, len(records), tamanho_lote):
            lote = records[i:i+tamanho_lote]
            try:
                resultado = supabase_client.table(tabela).insert(lote).execute()
                total_inseridos += len(lote)
            except Exception as e:
                # Mostra o erro exato mas não trava tudo imediatamente, tenta mostrar log
                erro_msg = str(e)
                st.error(f"❌ Erro ao inserir lote {i//tamanho_lote + 1}: {erro_msg}")
                print(f"DEBUG ERRO LOTE: {lote[0] if lote else 'Vazio'}") # Ajuda a debugar
                return False, f"Falha ao inserir produtos: {erro_msg}"
        
        mensagem = f"✅ {total_inseridos} produtos sincronizados com sucesso!"
        return True, mensagem
        
    except Exception as e:
        return False, f"❌ Erro na sincronização: {str(e)}"


# =====================================================================
# FUNÇÕES AUXILIARES DE VISUALIZAÇÃO
# =====================================================================

def exibir_preview_dados(df: pd.DataFrame, max_linhas: int = 5):
    """Exibe preview dos dados carregados"""
    st.subheader("📋 Preview dos Dados")
    
    with st.expander("Ver estrutura dos dados", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Linhas", len(df))
        with col2:
            st.metric("Total de Colunas", len(df.columns))
        with col3:
            st.metric("Tamanho (MB)", f"{df.memory_usage(deep=True).sum() / 1024**2:.2f}")
        
        st.write("**Colunas encontradas:**")
        cols_info = []
        for col in df.columns:
            dtype = df[col].dtype
            nulos = df[col].isna().sum()
            cols_info.append(f"- `{col}` ({dtype}) - {nulos} nulos")
        st.write('\n'.join(cols_info))
    
    st.write("**Primeiras linhas:**")
    st.dataframe(df.head(max_linhas), use_container_width=True)


