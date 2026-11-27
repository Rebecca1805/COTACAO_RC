# Gabarito Oficial de Testes · RC Online (BE-3)

Referência extraída das regras ativas de `app.py` e `produtos_manager.py` (Piloto V2.3).
Qualquer implementação futura no Supabase (Fase C) ou React (Fase D) deve produzir exatamente os resultados abaixo.

---

## Grupo 1 · Interpretação e Conversão de Preços (`interpretar_preco` / `limpar_dados`)

| Caso     | Entrada na planilha           | Valor convertido (`float`) | Válido? | Gera alerta com linha/coluna? | Observação                                          |
| :------- | :---------------------------- | :------------------------: | :-----: | :---------------------------: | :-------------------------------------------------- |
| **P-01** | `"1234,56"`                   |         `1234.56`          |   Sim   |              Não              | Padrão brasileiro sem separador de milhar           |
| **P-02** | `"1.234,56"`                  |         `1234.56`          |   Sim   |              Não              | Padrão brasileiro com ponto de milhar               |
| **P-03** | `"R$ 89,90"`                  |          `89.90`           |   Sim   |              Não              | Remove prefixo `R$` e espaços                       |
| **P-04** | `"  15,5  "`                  |          `15.50`           |   Sim   |              Não              | Remove espaços extras nas pontas                    |
| **P-05** | `"0"` ou `"0,00"`             |           `0.0`            |   Sim   |              Não              | Preço zerado numérico válido                        |
| **P-06** | `""` (célula vazia) ou `None` |           `0.0`            |   Sim   |              Não              | Célula vazia grava `0.0` sem falso alerta           |
| **P-07** | `"1234.56"` (ponto decimal)   |         `1234.56`          |   Sim   |              Não              | Aceito pelo parser Python (sem milhar)              |
| **P-08** | `"consultar"`                 |           `0.0`            | **Não** |            **Sim**            | Texto inválido grava `0.0` após avisar linha/coluna |
| **P-09** | `"-"`                         |           `0.0`            | **Não** |            **Sim**            | Traço isolado é sinalizado como inválido            |
| **P-10** | `"-25,00"`                    |           `0.0`            | **Não** |            **Sim**            | Valor negativo é rejeitado e sinalizado             |

---

## Grupo 2 · Faixas de Distância e Coluna de Preço do Cliente

Regra aplicada no cadastro manual, importação de clientes e seleção de preço na cotação:

| Caso     | Permissão `permite_retirada` | Escolha na cotação                   | Distância (`distancia_km`) | Coluna usada no banco | Rótulo exibido ao usuário   |
| :------- | :--------------------------: | :----------------------------------- | :------------------------: | :-------------------- | :-------------------------- |
| **F-01** |       `False` (padrão)       | Forçada para `Entrega`               |           `0 km`           | `preco_entrega`       | `Entrega (0 a 99 km)`       |
| **F-02** |           `False`            | Forçada para `Entrega`               |          `99 km`           | `preco_entrega`       | `Entrega (0 a 99 km)`       |
| **F-03** |           `False`            | Forçada para `Entrega`               |          `100 km`          | `preco_100a199km`     | `100 a 199 km`              |
| **F-04** |           `False`            | Forçada para `Entrega`               |          `199 km`          | `preco_100a199km`     | `100 a 199 km`              |
| **F-05** |           `False`            | Forçada para `Entrega`               |          `200 km`          | `preco_200a299km`     | `200 a 299 km`              |
| **F-06** |           `False`            | Forçada para `Entrega`               |          `299 km`          | `preco_200a299km`     | `200 a 299 km`              |
| **F-07** |           `False`            | Forçada para `Entrega`               |          `300 km`          | `preco_300a399km`     | `300 a 399 km`              |
| **F-08** |           `False`            | Forçada para `Entrega`               |          `399 km`          | `preco_300a399km`     | `300 a 399 km`              |
| **F-09** |           `False`            | Forçada para `Entrega`               |          `400 km`          | `preco_acima400km`    | `400 a 500 km`              |
| **F-10** |           `False`            | Forçada para `Entrega`               |          `500 km`          | `preco_acima400km`    | `400 a 500 km`              |
| **F-11** |           `False`            | Forçada para `Entrega`               |          `501 km`          | `preco_acima500km`    | `501 a 600 km`              |
| **F-12** |           `False`            | Forçada para `Entrega`               |          `600 km`          | `preco_acima500km`    | `501 a 600 km`              |
| **F-13** |           `False`            | Forçada para `Entrega`               |          `601 km`          | `preco_acima600km`    | `Acima de 600 km`           |
| **F-14** |            `True`            | `Retirada no centro de distribuição` |          `350 km`          | `preco_retira`        | `Retira` (ignora distância) |
| **F-15** |            `True`            | `Entrega`                            |          `350 km`          | `preco_300a399km`     | `300 a 399 km`              |

---

## Grupo 3 · Totais, Descontos por Item e Desconto Extra na Cotação

Fórmulas oficiais:

- `subtotal_item = (preco_unitario * quantidade) * (1 - desconto_item / 100)`
- `total_bruto_real = soma(preco_unitario * quantidade)`
- `total_original = soma(subtotal_item)` _(total após descontos individuais)_
- `total_final = total_original * (1 - desconto_geral / 100)`

| Caso     | Cenário de entrada                                                                                                               | `total_bruto_real` | `total_desc_itens` | `total_original` | `total_desc_extra` |        `total_final`         |
| :------- | :------------------------------------------------------------------------------------------------------------------------------- | :----------------: | :----------------: | :--------------: | :----------------: | :--------------------------: |
| **T-01** | 1 item: Qtd `3` × R$ `50,00` \| Desc. item `0%` \| Desc. geral `0%`                                                              |    `R$ 150,00`     |     `R$ 0,00`      |   `R$ 150,00`    |     `R$ 0,00`      |       **`R$ 150,00`**        |
| **T-02** | 1 item: Qtd `4` × R$ `25,00` \| Desc. item `10%` \| Desc. geral `0%`                                                             |    `R$ 100,00`     |     `R$ 10,00`     |    `R$ 90,00`    |     `R$ 0,00`      |        **`R$ 90,00`**        |
| **T-03** | 1 item: Qtd `4` × R$ `25,00` \| Desc. item `0%` \| Desc. geral `5%`                                                              |    `R$ 100,00`     |     `R$ 0,00`      |   `R$ 100,00`    |     `R$ 5,00`      |        **`R$ 95,00`**        |
| **T-04** | 1 item: Qtd `4` × R$ `25,00` \| Desc. item `10%` \| Desc. geral `5%`                                                             |    `R$ 100,00`     |     `R$ 10,00`     |    `R$ 90,00`    |     `R$ 4,50`      |        **`R$ 85,50`**        |
| **T-05** | Item A: Qtd `2` × R$ `120,00` (desc. `5%` = `228,00`) + Item B: Qtd `5` × R$ `18,50` (desc. `0%` = `92,50`) \| Desc. geral `10%` |    `R$ 332,50`     |     `R$ 12,00`     |   `R$ 320,50`    |     `R$ 32,05`     |       **`R$ 288,45`**        |
| **T-06** | Cotação `PENDENTE` com Qtd `2` × R$ `40,00` (desc. item `10%`, desc. geral `5%`). Nova tabela sobe item para R$ `50,00`          |    `R$ 100,00`     |     `R$ 10,00`     |    `R$ 90,00`    |     `R$ 4,50`      |        **`R$ 85,50`**        |
| **T-07** | Cotação `APROVADA` com Qtd `2` × R$ `40,00`. Nova tabela sobe item para R$ `50,00`                                               |     `R$ 80,00`     |     `R$ 0,00`      |    `R$ 80,00`    |     `R$ 0,00`      | **`R$ 80,00`** _(congelada)_ |

---

## Grupo 4 · Regras de Sincronização, Limpeza e Visibilidade

| Caso     | Cenário / Entrada                                                                                                                    | Resultado esperado                                                                                          |
| :------- | :----------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------- |
| **R-01** | Arquivo de produtos tem duas linhas com o mesmo `codigo` (`"ABC-1"` com R$ `10,00` na linha 2 e `"ABC-1"` com R$ `12,00` na linha 8) | Mantém apenas a **última ocorrência** (`R$ 12,00`) via `drop_duplicates(..., keep='last')`                  |
| **R-02** | Planilha tem colunas `Entrega` e `Entrega_1`                                                                                         | `Entrega` vira `preco_entrega`; `Entrega_1` vira `entrega_1` (não sobrescreve a primeira)                   |
| **R-03** | Nova tabela remove 6 de 10 produtos ativos (`60%` de redução)                                                                        | Bloqueia sincronização (`exige_confirmacao = True`) até marcar o checkbox de confirmação                    |
| **R-04** | Produto `"XYZ-9"` sai da nova tabela, mas está em cotação `APROVADA` ou `CANCELADA`                                                  | Não apaga do banco: marca `ativo = False` (some da busca ativa e preserva o PDF histórico)                  |
| **R-05** | Produto `"XYZ-9"` sai da nova tabela e **não** está em cotação aprovada/cancelada                                                    | Remove do banco (`DELETE`) e limpa eventual vínculo em cotações `PENDENTE`                                  |
| **R-06** | Cliente tem `visualiza_preco = False` e cotação está `PENDENTE`                                                                      | Tela e PDF ocultam preços unitários/totais e exibem aviso de valores a informar                             |
| **R-07** | Cliente tem `visualiza_preco = False`, mas representante muda cotação para `APROVADA`                                                | Tela e PDF liberam os valores finais daquela cotação aprovada, mantendo a observação de preços referenciais |
