import os
import app

cotacoes = app.load_cotacoes()
if cotacoes.empty:
    print('Nenhuma cotação encontrada. Crie uma cotação via UI antes de gerar o PDF de teste.')
    raise SystemExit(0)

last = cotacoes.iloc[-1]
qt_id = last['id']
itens = app.load_itens_cotacao()
itens = itens[itens['id_cotacao'] == qt_id]
if itens.empty:
    print(f'Nenhum item encontrado para a cotacao {qt_id}.')
    raise SystemExit(0)

pdf_bytes = app.gerar_pdf_cotacao(last, itens)
out_path = os.path.join('storage', f'cotacao_{qt_id}.pdf')
with open(out_path, 'wb') as f:
    f.write(pdf_bytes)
print('PDF gerado em:', out_path)
