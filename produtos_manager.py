"""
Módulo para gerenciar leitura, validação e sincronização de produtos
com Supabase.
ATUALIZADO:
- Limpeza rigorosa (substituição de tabela).
- Preservação apenas de histórico consolidado (Aprovadas/Canceladas).
- Recálculo automático de cotações PENDENTES.
"""

import pandas as pd
import numpy as np
import re
from typing import Optional, Tuple, List
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
            # Tenta diferentes configurações de CSV
            tentativas = [
                {'sep': ',', 'encoding': 'utf-8', 'decimal': '.'},
                {'sep': ',', 'encoding': 'latin1', 'decimal': ','},
                {'sep': ';', 'encoding': 'utf-8', 'decimal': ','},
                {'sep': ';', 'encoding': 'latin1', 'decimal': ','},
            ]
            for tent in tentativas:
                try:
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, **tent)
                    if len(df.columns) > 1: return df
                except: continue
            raise ValueError("Não foi possível ler o CSV.")
            
        elif nome_arquivo.endswith(('.xls', '.xlsx')):
            return pd.read_excel(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
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
    # Remove linhas vazias
    df = df.dropna(how='all')
    
    # Garante código como string e remove vazios
    if 'codigo' in df.columns:
        df['codigo'] = df['codigo'].astype(str).str.strip()
        df = df[df['codigo'] != '']
        # Remove duplicatas de código no arquivo (mantém o último ou primeiro)
        df = df.drop_duplicates(subset=['codigo'], keep='last')

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
    except: return 0.0

def processar_arquivo_produtos(arquivo):
    df = ler_arquivo(arquivo)
    if df is None: return None
    
    df = normalizar_colunas(df)
    valido, msgs = validar_dados(df)
    
    if not valido:
        for m in msgs: st.error(m)
        return None
        
    return limpar_dados(df)

# =====================================================================
# SINCRONIZAÇÃO E RECÁLCULO (LÓGICA NOVA)
# =====================================================================

def sincronizar_produtos_supabase(supabase, df, tabela='produtos', limpar_antes=False, representante_id=None):
    """
    1. Atualiza/Insere produtos novos (Upsert).
    2. Remove produtos antigos que NÃO estão no arquivo, EXCETO se estiverem em cotações APROVADA/CANCELADA.
    3. Chama a função para atualizar preços das cotações PENDENTES.
    """
    try:
        if not representante_id: return False, "ID do representante não fornecido."
        
        df['representante_id'] = representante_id
        df['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # ---------------------------------------------------------
        # 1. UPSERT (Atualiza a base com a tabela nova)
        # ---------------------------------------------------------
        # Mantém apenas colunas que existem na tabela produtos
        colunas_validas = {
            'representante_id', 'codigo', 'produto', 'unidade',
            'preco_retira', 'preco_entrega',
            'preco_100a199km', 'preco_200a299km', 'preco_300a399km',
            'preco_acima400km', 'preco_acima500km', 'preco_acima600km',
            'updated_at'
        }
        df = df[[c for c in df.columns if c in colunas_validas]].copy()
        records = df.to_dict('records')
        
        # Trata valores NaN para None (JSON null)
        for r in records:
            for k, v in r.items():
                if pd.isna(v): r[k] = None
                
        # Envia em lotes
        batch_size = 100
        progresso = st.progress(0, text="Atualizando catálogo...")
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table(tabela).upsert(batch, on_conflict='representante_id, codigo').execute()
            progresso.progress(min((i+batch_size)/len(records), 0.8))
            
        # ---------------------------------------------------------
        # 2. LIMPEZA (Substituição Inteligente)
        # ---------------------------------------------------------
        # Queremos apagar tudo que NÃO está no arquivo novo,
        # MAS preservar o que é usado em histórico (Aprovada/Cancelada).
        
        codigos_novos = set(df['codigo'].astype(str).tolist())
        
        # Busca todos os produtos do banco
        all_prods = supabase.table(tabela).select('id, codigo').eq('representante_id', representante_id).execute().data
        
        # Identifica quem sumiu do arquivo
        ids_candidatos_exclusao = [p['id'] for p in all_prods if str(p['codigo']) not in codigos_novos]
        
        qtd_removidos = 0
        qtd_preservados = 0
        
        if ids_candidatos_exclusao:
            progresso.progress(0.85, text="Verificando integridade do histórico...")
            
            # Verifica quais desses IDs são usados em cotações "protegidas" (Aprovada/Cancelada)
            # Para isso, precisamos fazer um join ou duas queries. Vamos por queries.
            
            # Passo A: Busca IDs de cotações que NÃO são pendentes
            cot_protegidas = supabase.table('cotacoes')\
                .select('id')\
                .neq('status', 'PENDENTE')\
                .eq('representante_id', representante_id)\
                .execute().data
            
            ids_cot_protegidas = [c['id'] for c in cot_protegidas]
            
            ids_produtos_protegidos = set()
            
            if ids_cot_protegidas:
                # Passo B: Busca itens dessas cotações que contêm os produtos candidatos
                # Fazemos em lotes para não estourar a URL
                for i in range(0, len(ids_candidatos_exclusao), 100):
                    lote_prod = ids_candidatos_exclusao[i:i+100]
                    
                    # Se o produto está num item de cotação protegida
                    resp = supabase.table('cotacao_itens')\
                        .select('produto_id')\
                        .in_('produto_id', lote_prod)\
                        .in_('cotacao_id', ids_cot_protegidas)\
                        .execute()
                    
                    for item in resp.data:
                        ids_produtos_protegidos.add(item['produto_id'])
            
            # Passo C: Define quem roda (Quem sumiu do arquivo E NÃO é protegido)
            # Obs: Se o produto estava só em PENDENTE, ele será apagado (e a cotação pendente perde o item, o que é correto)
            ids_final_delete = [id_ for id_ in ids_candidatos_exclusao if id_ not in ids_produtos_protegidos]
            qtd_preservados = len(ids_produtos_protegidos)
            
            # Passo D: Deleta
            if ids_final_delete:
                # 1) Buscar cotações pendentes do representante
                cot_pend = (
                    supabase.table('cotacoes')
                    .select('id')
                    .eq('representante_id', representante_id)
                    .eq('status', 'PENDENTE')
                    .execute()
                    .data
                )
                ids_cot_pend = [c['id'] for c in cot_pend] if cot_pend else []

                # 2) Antes de deletar produtos, deletar itens de cotações PENDENTES que apontam pra eles
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

                # 3) Agora sim, deletar os produtos do catálogo (em lotes)
                for i in range(0, len(ids_final_delete), 100):
                    lote_del = ids_final_delete[i:i+100]
                    supabase.table(tabela).delete().in_('id', lote_del).execute()

                qtd_removidos = len(ids_final_delete)


        # ---------------------------------------------------------
        # 3. RECÁLCULO DE COTAÇÕES PENDENTES
        # ---------------------------------------------------------
        progresso.progress(0.9, text="Atualizando preços das cotações pendentes...")
        qtd_cotacoes_atualizadas = recalcular_cotacoes_pendentes(supabase, representante_id)
        
        progresso.empty()
        
        msg = f"✅ Sucesso! {len(records)} produtos ativos."
        if qtd_removidos > 0: msg += f" 🗑️ {qtd_removidos} fora de linha removidos."
        if qtd_preservados > 0: msg += f" 🛡️ {qtd_preservados} antigos mantidos por histórico."
        if qtd_cotacoes_atualizadas > 0: msg += f" 🔄 {qtd_cotacoes_atualizadas} cotações pendentes atualizadas."
        
        return True, msg

    except Exception as e:
        return False, f"Erro crítico: {e}"


def recalcular_cotacoes_pendentes(supabase, representante_id):
    """
    Atualiza os preços dos itens em cotações PENDENTES com base na nova tabela.
    Respeita a regra: Retira vs Entrega (Cliente).
    """
    try:
        # 1. Buscar cotações pendentes + dados do cliente (para saber a coluna de preço)
        # O Supabase permite select com join: cotacoes(..., clientes(coluna_preco))
        resp = supabase.table('cotacoes')\
            .select('id, forma_recebimento, clientes(coluna_preco)')\
            .eq('representante_id', representante_id)\
            .eq('status', 'PENDENTE')\
            .execute()
        
        cotacoes_pendentes = resp.data
        if not cotacoes_pendentes:
            return 0
        
        # 2. Carregar TODOS os produtos atuais do representante (para consulta rápida de preço)
        # Criamos um dicionário {codigo: {dados_do_produto}}
        prods_resp = supabase.table('produtos').select('*').eq('representante_id', representante_id).execute()
        mapa_produtos = {p['codigo']: p for p in prods_resp.data} # Mapeia pelo código
        
        count_atualizadas = 0
        
        for cot in cotacoes_pendentes:
            cot_id = cot['id']
            forma_recebimento = cot.get('forma_recebimento')
            
            # Determina a coluna de preço a usar
            cliente_data = cot.get('clientes') or {}
            coluna_cliente = cliente_data.get('coluna_preco') or 'preco_entrega'
            
            if forma_recebimento == 'Retirada no centro de distribuição':
                coluna_preco_target = 'preco_retira'
            else:
                coluna_preco_target = coluna_cliente
            
            # 3. Buscar itens da cotação
            itens_resp = supabase.table('cotacao_itens').select('*').eq('cotacao_id', cot_id).execute()
            itens = itens_resp.data
            
            total_original_novo = 0.0
            teve_alteracao = False
            
            for item in itens:
                cod_prod = item['codigo']
                
                # Verifica se o produto ainda existe na tabela nova
                if cod_prod in mapa_produtos:
                    prod_novo = mapa_produtos[cod_prod]
                    
                    # Pega o novo preço base
                    novo_preco_base = float(prod_novo.get(coluna_preco_target) or 0.0)
                    
                    # Se o preço mudou, atualiza
                    # Nota: Mantemos o desconto_percentual que já estava no item
                    preco_antigo = float(item.get('preco_unitario') or 0.0)
                    
                    # Atualizamos sempre para garantir, ou checamos if novo_preco_base != preco_antigo
                    # Vamos atualizar sempre para garantir sincronia
                    
                    qtd = float(item['quantidade'])
                    desconto = float(item.get('desconto_percentual') or 0.0)
                    
                    novo_subtotal = (novo_preco_base * qtd) * (1 - desconto/100)
                    
                    # Atualiza o item no banco
                    supabase.table('cotacao_itens').update({
                        'preco_unitario': novo_preco_base,
                        'subtotal': novo_subtotal,
                        # Opcional: atualizar nome/unidade se mudou
                        'produto': prod_novo.get('produto'),
                        'unidade': prod_novo.get('unidade')
                    }).eq('id', item['id']).execute()
                    
                    total_original_novo += novo_subtotal
                    teve_alteracao = True
                else:
                    # PRODUTO NÃO EXISTE MAIS?
                    # Como é cotação PENDENTE e estamos "substituindo" a tabela, 
                    # tecnicamente deveríamos remover o item ou alertar.
                    # Por segurança do código, mantemos o valor antigo no somatório ou removemos.
                    # Opção escolhida: Manter como está (item órfão) para não reduzir o valor bruscamente sem aviso,
                    # mas idealmente o representante deve revisar.
                    total_original_novo += float(item['subtotal'])
            
            # 4. Atualizar o total da cotação
            if teve_alteracao:
                # Recalcula total final com desconto geral da cotação
                # Precisamos pegar o desconto geral atual da cotação. 
                # (Não veio no select inicial, mas podemos pegar ou assumir que o update lida com isso)
                # Vamos fazer um fetch rápido para garantir
                cot_full = supabase.table('cotacoes').select('desconto_geral_percentual').eq('id', cot_id).single().execute()
                desc_geral = float(cot_full.data.get('desconto_geral_percentual') or 0.0)
                
                novo_total_final = total_original_novo * (1 - desc_geral/100)
                
                supabase.table('cotacoes').update({
                    'total_original': total_original_novo,
                    'total_final': novo_total_final
                }).eq('id', cot_id).execute()
                
                count_atualizadas += 1
                
        return count_atualizadas

    except Exception as e:
        print(f"Erro ao recalcular pendentes: {e}")
        return 0

def exibir_preview_dados(df: pd.DataFrame):
    st.write(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
    st.dataframe(df.head())






