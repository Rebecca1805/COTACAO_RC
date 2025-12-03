import os
import app

# Gera uma cotação de teste usando primeiro cliente 'Loureiro' ou primeiro registro
clientes = app.load_clientes()
if clientes.empty:
    print('Nenhum cliente cadastrado. Pare o script e cadastre clientes.')
    raise SystemExit(1)

mask = clientes['NOME'].str.contains('Loureiro', case=False, na=False)
if mask.any():
    cliente_row = clientes[mask].iloc[0]
else:
    cliente_row = clientes.iloc[0]

# Seleciona 1 produto de exemplo
tabela = app.load_tabela_geral()
if tabela.empty:
    print('Tabela de produtos vazia. Pare e verifique o arquivo.')
    raise SystemExit(1)

produto = tabela.iloc[0]
# calcular preços
preco_retira = app.get_preco_retira(produto)
preco_entrega = app.get_preco_entrega(cliente_row, produto)

# definir entrega = True (testar entrega)
entrega = True
preco_final = preco_entrega if entrega and preco_entrega is not None else preco_retira
if preco_final is None:
    preco_final = preco_retira if preco_retira is not None else 0.0

qtd = 2
subtotal_retira = (preco_retira if preco_retira is not None else 0.0) * qtd
subtotal_final = preco_final * qtd

itens = [
    {
        'codigo': str(produto.get('Codigo_1', produto.get('Codigo', ''))),
        'produto': produto.get('Produto_1', produto.get('Produto', '')),
        'unidade': produto.get('Unidade_1', produto.get('Unidade', '')),
        'quantidade': qtd,
        'preco_retira': preco_retira if preco_retira is not None else 0.0,
        'preco_final': preco_final,
        'subtotal_retira': subtotal_retira,
        'subtotal_final': subtotal_final,
    }
]

print('Cliente usado:', cliente_row['NOME'])
print('Produto usado:', produto.get('Produto_1', produto.get('Produto', '')))

# Salva cotação
cot_id = app.salvar_cotacao(cliente_row, itens, 'Entrega no endereço')
if not cot_id:
    print('Falha ao salvar cotação')
    raise SystemExit(1)

print('Cotação criada ID:', cot_id)

cotacoes = app.load_cotacoes()
cot_row = cotacoes[cotacoes['id'] == cot_id].iloc[0]

itens_df = app.load_itens_cotacao()
itens_df = itens_df[itens_df['id_cotacao'] == cot_id]

pdf_bytes = app.gerar_pdf_cotacao(cot_row, itens_df)

out_path = os.path.join('storage', f'cotacao_{cot_id}.pdf')
with open(out_path, 'wb') as f:
    f.write(pdf_bytes)

print('PDF gerado em:', out_path)
