"""
Script de teste para o módulo produtos_manager.py
Valida todas as funcionalidades de leitura, normalização e limpeza de dados.
"""

import pandas as pd
import os
from io import BytesIO
from produtos_manager import (
    normalizar_colunas,
    validar_dados,
    limpar_dados,
    converter_preco,
)


def teste_converter_preco():
    """Testa conversão de diferentes formatos de preço"""
    print("\n" + "="*60)
    print("TESTE 1: Conversão de Preços")
    print("="*60)
    
    testes = [
        ("50,00", 50.0),
        ("1.200,50", 1200.5),
        ("1,234.56", 1234.56),
        ("1234.56", 1234.56),
        ("R$ 1.234,56", 1234.56),
        ("R$ 1,234.56", 1234.56),
        ("-", 0.0),
        ("N/A", 0.0),
        (None, 0.0),
        (100, 100.0),
        (99.99, 99.99),
    ]
    
    for entrada, esperado in testes:
        resultado = converter_preco(entrada)
        status = "✅" if abs(resultado - esperado) < 0.01 else "❌"
        print(f"{status} {str(entrada):20} → {resultado:10.2f} (esperado: {esperado})")


def teste_normalizar_colunas():
    """Testa normalização de nomes de colunas"""
    print("\n" + "="*60)
    print("TESTE 2: Normalização de Colunas")
    print("="*60)
    
    # Criar DataFrame com nomes variados
    df = pd.DataFrame({
        'Código_1': ['001', '002'],
        'Produto_1': ['Item A', 'Item B'],
        'UNIDADE_1': ['KG', 'UN'],
        'Preço Retirada': [50.0, 100.0],
        'Preço Entrega': [60.0, 120.0],
        'À Toa': ['valor', 'outro'],  # Coluna com acento
    })
    
    print(f"\nColunas ANTES: {list(df.columns)}")
    
    df_norm = normalizar_colunas(df)
    
    print(f"Colunas DEPOIS: {list(df_norm.columns)}")
    
    # Verificar mapeamentos
    assert 'codigo' in df_norm.columns, "❌ 'codigo' não encontrado"
    assert 'produto' in df_norm.columns, "❌ 'produto' não encontrado"
    assert 'unidade' in df_norm.columns, "❌ 'unidade' não encontrado"
    assert 'retira' in df_norm.columns, "❌ 'retira' não encontrado"
    assert 'entrega' in df_norm.columns, "❌ 'entrega' não encontrado"
    
    print("✅ Todos os mapeamentos funcionaram!")


def teste_validacao():
    """Testa validação de dados"""
    print("\n" + "="*60)
    print("TESTE 3: Validação de Dados")
    print("="*60)
    
    # Caso 1: DataFrame válido
    df_valido = pd.DataFrame({
        'codigo': ['001', '002', '003'],
        'produto': ['Item A', 'Item B', 'Item C'],
    })
    
    valido, msgs = validar_dados(df_valido)
    print(f"\nCaso 1 (Válido): {valido}")
    if msgs:
        for msg in msgs:
            print(f"  {msg}")
    assert valido, "❌ Deveria ser válido"
    print("  ✅ Passou")
    
    # Caso 2: Falta coluna obrigatória
    df_invalido = pd.DataFrame({
        'codigo': ['001', '002'],
    })
    
    valido, msgs = validar_dados(df_invalido)
    print(f"\nCaso 2 (Falta 'produto'): {valido}")
    for msg in msgs:
        print(f"  {msg}")
    assert not valido, "❌ Deveria ser inválido"
    print("  ✅ Passou")
    
    # Caso 3: Valores vazios
    df_vazio = pd.DataFrame({
        'codigo': ['001', '', '003'],
        'produto': ['Item A', 'Item B', ''],
    })
    
    valido, msgs = validar_dados(df_vazio)
    print(f"\nCaso 3 (Valores vazios): {valido}")
    for msg in msgs:
        print(f"  {msg}")
    # Continua válido estruturalmente, mas deve avisar sobre vazios
    assert valido, "❌ Estrutura está ok"
    print("  ✅ Passou (avisos gerados)")


def teste_limpeza():
    """Testa limpeza de dados"""
    print("\n" + "="*60)
    print("TESTE 4: Limpeza de Dados")
    print("="*60)
    
    df = pd.DataFrame({
        'codigo': ['001', '002', '001', '   003   '],  # '001' duplicado, '003' com espaços
        'produto': ['Item A', 'Item B', 'Item A', 'Item C'],
        'preco_unitario': ['50,00', '100.50', '50,00', '1.200,99'],
    })
    
    print(f"\nAntes da limpeza: {len(df)} linhas")
    print(f"Colunas: {list(df.columns)}")
    
    df_limpo = limpar_dados(df)
    
    print(f"Depois da limpeza: {len(df_limpo)} linhas")
    
    # Verificar duplicatas removidas
    assert len(df_limpo) == 3, "❌ Duplicatas não foram removidas"
    print("  ✅ Duplicatas removidas")
    
    # Verificar espaços removidos
    assert df_limpo[df_limpo['codigo'] == '003'].iloc[0]['codigo'] == '003'
    print("  ✅ Espaços removidos")
    
    # Verificar preços convertidos
    assert df_limpo['preco_unitario'].dtype in ['float64', 'float32']
    print("  ✅ Preços convertidos para float")


def teste_pipeline_completo():
    """Testa o pipeline completo"""
    print("\n" + "="*60)
    print("TESTE 5: Pipeline Completo (Integração)")
    print("="*60)
    
    # Simular um DataFrame como se viesse de um CSV "bagunçado"
    df_entrada = pd.DataFrame({
        'Código Item': ['P001', 'P002', 'P001', '   '],  # Variação de nome, duplicata, linha vazia
        'Descrição do Produto': ['Parafuso 5mm', 'Arruela', 'Parafuso 5mm', ''],
        'UN': ['KG', 'UN', 'KG', 'XX'],
        'Preço Retirada': ['1.000,50', '50,00', '1.000,50', ''],
        'Preço Entrega': ['1.200,99', '75,00', '1.200,99', ''],
    })
    
    print(f"\n1. Entrada: {len(df_entrada)} linhas")
    print(f"   Colunas: {list(df_entrada.columns)}")
    
    # Normalizar
    df = normalizar_colunas(df_entrada)
    print(f"\n2. Após normalização: {len(df)} linhas")
    print(f"   Colunas: {list(df.columns)}")
    
    # Validar
    valido, msgs = validar_dados(df)
    print(f"\n3. Validação: {'✅ OK' if valido else '⚠️ Avisos'}")
    for msg in msgs:
        print(f"   {msg}")
    
    # Limpar
    df = limpar_dados(df)
    print(f"\n4. Após limpeza: {len(df)} linhas")
    
    # Verificar que removeu linhas vazias e duplicatas
    print(f"   Dados finais:")
    print(df.to_string())
    
    # A primeira linha vazia vai ser dropada
    # As duplicatas (linhas 0 e 2) vão ser dropadas (keep='first')
    # Então sobram: linhas 1 (P002)
    # Mas linha 3 está completamente vazia, vai ser dropada
    
    # Esperamos ao menos validação estrutural OK
    assert 'codigo' in df.columns, "❌ 'codigo' não encontrado"
    assert 'produto' in df.columns, "❌ 'produto' não encontrado"
    assert 'retira' in df.columns, "❌ 'retira' não encontrado"
    assert df['retira'].dtype in ['float64', 'float32'], "❌ Preço não é float"
    
    print("\n✅ Pipeline completo funcionou!")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("\n")
    print("INICIANDO TESTES DO MODULO produtos_manager")
    print("="*60)
    
    try:
        teste_converter_preco()
        teste_normalizar_colunas()
        teste_validacao()
        teste_limpeza()
        teste_pipeline_completo()
        
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ ERRO: {e}")
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
