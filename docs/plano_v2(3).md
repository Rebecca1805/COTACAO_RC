# Plano de evolução V2 · RC Online

Nov 26, 2026 · @Rebecca

Versão 2.2.3, atualizada em 26/11/2026: o 1º cliente entra em piloto pago no Streamlit (hospedagem gratuita) enquanto construímos o backend definitivo no Supabase e as telas em React (React + VS Code no Cloudflare Pages), sem cartão de crédito.

**Posição atual:** Fase A concluída; na Fase B, segurança (SEG-1 a SEG-7 e SEG-12), mapeamento (BE-1), ajustes do piloto (BE-2), gabarito de testes (BE-3) e definição de CEP/distância (BE-4) concluídos. Próximo: INF-8 (Projeto Supabase de produção).
Atualize esta linha a cada item concluído.

## Como retomar em uma nova conversa

Cada conversa trabalha **um item** do plano. Para começar uma:

1. Diga qual é o item (por exemplo, BE-2) e cole este plano, ou só o trecho do item e a seção de decisões.
2. Anexe somente o que o item pede: o schema SQL (itens BD), o `app.py` ou o módulo citado (itens BE e SEG).
3. Nunca envie chaves, senhas ou o `secrets.toml`; troque por XXXX.
4. Ao terminar, marque o item aqui e atualize a Posição atual.

Resumo para colar no início de qualquer conversa nova:

> App de cotações para representantes comerciais (Python, Streamlit e Supabase; cerca de 3.000 linhas em app.py e produtos_manager.py), que será vendido como microSaaS para até cerca de 50 clientes. Sou consultora, sem formação em programação, e trabalho com vibe coding: preciso ir devagar, passo a passo, um item por vez, código completo com explicação e roteiro de teste. Não tenho cartão de crédito: só uso serviços gratuitos ou pagos por Pix ou boleto. Estratégia atual: colocar o 1º cliente piloto no Streamlit (Streamlit Community Cloud + Supabase gratuito) para validar e faturar, enquanto migro as regras para o Supabase e desenvolvo o front-end React padrão (Vite + Tailwind + shadcn/ui no VS Code) para hospedar no Cloudflare Pages.
> Não peça nunca para substituir o arquivo app.py todo, vamos sempre trabalhar em blocos explicados e ao final de todo o processo, lembre-se de me guiar para o commit final no terminal do VS Code.

## Decisões já tomadas

| Tema                    | Decisão                                                                                                                                                                                                                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prazo e Piloto          | Entregar o 1º cliente em piloto no Streamlit (Streamlit Community Cloud gratuito) para faturar rápido, enquanto construímos o React definitivo                                                                                                                                                                              |
| Estrutura               | Empresa (fornecedor) tem 1 ou mais tabelas de preço; representante atende 1 ou mais empresas; uma empresa pode ter vários representantes                                                                                                                                                                                    |
| Isolamento              | Cliente e prospect pertencem a um único representante; nenhum outro representante os vê; o CNPJ não pode repetir entre representantes                                                                                                                                                                                       |
| Página do representante | Cliente ou prospect que entra por ela vê as empresas daquele representante e pede cotação a uma delas                                                                                                                                                                                                                       |
| Prospect                | Autocadastro com nome, CNPJ, CEP e telefone; escolhe os produtos para orçamento; só vê preço se o representante liberar                                                                                                                                                                                                     |
| Cliente                 | Cadastra-se e faz login (como hoje no piloto; via Supabase Auth no React); o representante valida o cadastro                                                                                                                                                                                                                |
| Representante           | Vê as solicitações de clientes e prospects, libera ou oculta preços e valida cadastros                                                                                                                                                                                                                                      |
| Administradora          | Você: libera novos representantes e faz a manutenção; sem cadastro público                                                                                                                                                                                                                                                  |
| Retirada                | Desabilitada por padrão; o representante liga por cliente (obrigatório já no piloto Streamlit)                                                                                                                                                                                                                              |
| Uploads                 | CSV, XLS e XLSX, para tabela de produtos e para clientes                                                                                                                                                                                                                                                                    |
| Tabela de preços        | Pode manter itens e mudar preços, incluir itens novos ou excluir itens do catálogo ativo sem quebrar cotações antigas; itens descontinuados não aparecem na busca                                                                                                                                                           |
| Aviso comercial         | Cotações e PDFs exibem observação informando que os preços são referenciais e sujeitos a alteração até o fechamento/aprovação do pedido                                                                                                                                                                                     |
| Distância               | Faixas por km (`0 a 99 km` usa `Entrega_1` / `preco_entrega`; demais faixas até `Acima de 600 km`); no React o cliente digita o CEP e a distância é calculada a partir da origem cadastrada na empresa, com ajuste manual pelo representante (o valor digitado prevalece); alguns fornecedores terão preço único (ver BE-4) |
| Infraestrutura          | Piloto em Streamlit Community Cloud; definitivo em React (Cloudflare Pages) e Supabase gratuito, sem cartão de crédito; VPS com n8n só na Fase F                                                                                                                                                                            |
| Ferramentas de IA       | Claude/Gemini para arquitetura, SQL e lógica; Gerar o esqueleto visual React em ferramenta gratuita via GitHub; VS Code + Copilot Free para ajustes finais sem limite de créditos                                                                                                                                           |
| Banco                   | Evolução aditiva: durante o piloto, nenhuma mudança da Fase C pode quebrar as colunas usadas pelo Streamlit                                                                                                                                                                                                                 |

## Premissas V2.3

| Tema                   | Premissa                                                                                                                                                               |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Produto                | Será vendido como microSaaS, para até cerca de 50 clientes; precisa parecer profissional do começo ao fim. Acima disso, você contrata ajuda para ampliar a arquitetura |
| Pagamento              | Sem cartão de crédito: só serviços gratuitos ou pagos por Pix ou boleto. Railway, Supabase Pro e Vercel Pro ficam fora do plano inicial                                |
| Telas                  | Streamlit atende apenas o cliente piloto; o produto comercial escalável é em React                                                                                     |
| Forma de trabalho      | Vibe coding: passo a passo, um item por vez, sempre com teste                                                                                                          |
| Automação              | Depois da ferramenta pronta, uma VPS (por exemplo, Hostinger) com n8n para automações e para o WhatsApp dos clientes                                                   |
| Senha do representante | Troca obrigatória no primeiro acesso (ou opção de alteração imediata no piloto)                                                                                        |
| PDFs                   | Leves, gerados na hora e sem ocupar o banco; incluem aviso de que os preços são referenciais até o fechamento do pedido                                                |

## Decisões em aberto

| ID  | Pergunta                                                                                                       | Minha recomendação                                                                                                                                                                                                                                                                                                | Trava  |
| --- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| O1  | Como a distância é calculada hoje a partir do CEP (serviço usado, origem fixa)? Qual a origem de cada empresa? | Resolvido: hoje não há consulta de CEP, o representante digita a distância em km. No definitivo: CEP vira coordenada (BrasilAPI; se faltar, centro da cidade pelo IBGE), distância por Haversine × 1,25 arredondada para cima, origem guardada na empresa, e o valor digitado pelo representante sempre prevalece | BE-4   |
| O2  | Login único para todos os perfis com Supabase Auth                                                             | Resolvido: Supabase Auth na Fase C (piloto Streamlit mantém login atual)                                                                                                                                                                                                                                          | Fase C |
| O3  | Como o cliente se identifica no React: CNPJ, e-mail ou telefone?                                               | E-mail como login no Supabase Auth, com o CNPJ validado no cadastro                                                                                                                                                                                                                                               | SEG-8  |
| O4  | Como representar preço único?                                                                                  | Campo tipo_preco na tabela de preços: FAIXA ou UNICO                                                                                                                                                                                                                                                              | BD-4   |
| O5  | Cliente novo vê preço por padrão?                                                                              | Não, até o representante liberar (vale para prospect e cliente)                                                                                                                                                                                                                                                   | BE-5   |
| O6  | Prospect digita um CNPJ já cadastrado em outro representante                                                   | Mensagem neutra, sem revelar de quem é: não foi possível concluir, fale com seu representante                                                                                                                                                                                                                     | BE-5   |
| O7  | Item descontinuado em cotação pendente                                                                         | Sinalizar o item e avisar o representante, em vez de remover em silêncio                                                                                                                                                                                                                                          | BE-6   |
| O9  | Domínio: subdomínio ou iframe nos sites dos clientes?                                                          | Subdomínio; iframe só depois de testar login e cookies                                                                                                                                                                                                                                                            | Fase E |
| O10 | Arquitetura sem cartão de crédito                                                                              | Resolvido: React no Cloudflare Pages + Supabase gratuito                                                                                                                                                                                                                                                          | Fase C |
| O11 | Algum banco seu emite cartão virtual ou pré-pago internacional?                                                | Verificar. Se existir, o plano ganha opções (como Supabase Pro), mas não dependemos disso                                                                                                                                                                                                                         | Fase E |
| O12 | Primeiro cliente usa o Streamlit como piloto?                                                                  | Resolvido: Sim, no Streamlit Community Cloud com o banco de Produção                                                                                                                                                                                                                                              | INF-6  |
| O13 | Backup no plano gratuito                                                                                       | Exportação semanal manual desde a entrada do piloto (BKP-1) e automática pelo n8n na Fase F                                                                                                                                                                                                                       | INF-6  |
| O14 | Serviço de e-mail para convites e redefinições de senha                                                        | SMTP próprio (ex: Brevo/Resend gratuito) com o domínio; o e-mail padrão do Supabase é só para testes                                                                                                                                                                                                              | Fase C |
| O15 | WhatsApp: API oficial ou solução não oficial?                                                                  | Decidir só na Fase F, depois de pesquisar custos e termos                                                                                                                                                                                                                                                         | Fase F |

## Arquitetura-alvo

- **Etapa Piloto (Fase B):** Navegador → Streamlit Community Cloud (gratuito) → Supabase Produção (gratuito).
- **Etapa Definitiva (Fases C e D):** Navegador (React no Cloudflare Pages) → Supabase gratuito (Auth, banco com RLS, funções SQL e Edge Functions). O PDF é gerado no navegador. Depois, o n8n na VPS conversa com o Supabase para automações e WhatsApp.

Regra de migração: primeiro acrescentamos tabelas, colunas e funções; depois viramos para o React; e só no fim removemos o que sobrou do Streamlit. Nunca o contrário.

## Fases e portões

| Fase                           | Objetivo                                                                                        | Pronto quando                                                         | Custo               |
| ------------------------------ | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------- |
| A · Fundação                   | Base segura: GitHub, backup, banco novo                                                         | O app atual roda sem erro no banco novo                               | Concluída · R$ 0    |
| B · Segurança, Regras e Piloto | Blindar o Streamlit, corrigir cálculo de preço, mapear regras e colocar 1º cliente piloto no ar | Piloto rodando em produção e regras documentadas com gabarito         | R$ 0                |
| C · Backend no Supabase        | Login único, regras de acesso (RLS), cotação, importação, distância e e-mail dentro do Supabase | Resultados batem com o gabarito e o Streamlit piloto continua intacto | R$ 0                |
| D · React profissional         | Telas dos 4 perfis (Lovable + VS Code), identidade visual e PDF no navegador                    | O roteiro de aceitação passa inteiro no React                         | R$ 0                |
| E · Virada e Produção          | Domínio, migração de usuários para Auth, monitoramento e desligamento do Streamlit              | Todos os clientes usam o React sem suporte diário                     | Domínio             |
| F · Automação                  | VPS com n8n e WhatsApp                                                                          | Primeira automação em produção                                        | VPS (Pix ou boleto) |

## Fase A · Fundação (Concluída)

- [x] **INF-1 · Backup dos dados de teste.**
- [x] **INF-2 · Branch dev no GitHub.**
- [x] **INF-3 · Segredos fora do GitHub.**
- [x] **INF-4 · Procurar chaves no histórico.**
- [x] **INF-5 · Trocar as chaves, se necessário.**
- [x] **BD-1 · Guardar o schema atual no repositório (`banco/000_schema_atual.sql`).**
- [x] **BD-2 · Migração 001, aditiva.**
- [x] **BD-3 · Migração 002: empresas e vínculos.**
- [x] **BD-4 · Preço único.**
- [x] **BD-5 · CNPJ único entre representantes.**
- [x] **SEG-0 · RLS ligado, sem políticas.**

## Fase B · Segurança, Regras e Piloto no Streamlit

### Segurança (Obrigatória para o piloto)

- [x] **SEG-1 · Fechar o sequestro de conta.**
- [x] **SEG-2 · Eliminar senhas padrão.**
- [x] **SEG-3 · Cadastro de representante só por você.**
- [x] **SEG-4 · Limite de tentativas (`banco/006_tentativas_login.sql`).**
- [x] **SEG-5 · Isolamento por representante.**
- [x] **SEG-6 · Erros sem detalhe técnico.** Mensagem amigável na tela e registro em log no terminal; trocar os `except:` genéricos. Teste: um erro forçado não mostra texto técnico ao usuário.
- [x] **SEG-6B · Revisar `produtos_manager.py` (logs e erros amigáveis).** Trocar `st.error(f"...{e}")`, `Erro crítico: {e}` e `print(...)` por mensagens amigáveis e registro no `logger` (`rc_online`). Teste: falha forçada no upload de produtos não exibe erro técnico na tela.
- [x] **SEG-7 · HTML injetado.** Revisar os pontos de `unsafe_allow_html` e escapar o que vem de texto digitado. Teste: cliente com nome contendo `<b>` aparece como texto.
- [x] **SEG-12 · Troca de senha no primeiro acesso do representante.** A administradora cria o representante com senha provisória (ou convite) e o banco guarda a marca de senha a trocar; o app só libera as telas depois da troca. Teste: um representante novo só entra no painel depois de definir a senha própria, e a provisória deixa de funcionar.

### Regras do Python e Preparação do Piloto

- [x] **BE-1 · Mapear as regras do app.** Lista em português de tudo o que o Python ativo decide (`app.py` + `produtos_manager.py`): conversão de preço, faixas de distância (`0 a 99 km` -> `Entrega_1` / `preco_entrega`), totais e descontos, sincronização de produtos, importação de clientes, ID da cotação e conteúdo do PDF (listando funções mortas à parte para limpeza futura). Teste: você lê e confirma que bate com o que o app faz.
- [x] **BE-2 · Corrigir as regras com erro no Python e ajustes do piloto.**
  1. Em `produtos_manager.py`: manter o padrão brasileiro `1234,56`, sinalizar textos inválidos (ex.: `"consultar"`, `"-"`) com linha/coluna antes de gravar `0.0` e garantir que produtos antigos preservados apenas por histórico não apareçam mais na busca ativa do catálogo.
  2. Em `app.py`: ativar a opção de **Retirada** por cliente (desabilitada por padrão; representante habilita/desabilita na Gestão de Clientes e cliente só vê a opção se liberada), alinhar os rótulos das faixas de 400 a 600 km e incluir no PDF e na cotação o aviso padrão de que os preços são referenciais até o fechamento do pedido.
     Teste: importação avisa valores inválidos, item descontinuado some da busca sem quebrar PDF antigo, retirada respeita a permissão do cliente e o aviso aparece no PDF.
- [x] **BE-3 · Gabarito de testes.** Arquivo com pelo menos 30 casos (entrada e resultado esperado) tirados do Python: preços (padrão `1234,56` e texto inválido), faixas (`0 a 99 km` até `> 600 km`), totais e descontos. Teste: arquivo salvo no repositório.
- [x] **BE-4 · CEP e distância (O1).** Decisão registrada:
  1. **Hoje (piloto Streamlit):** não existe consulta de CEP. O representante digita a distância (campo ou coluna `DISTANCIA` da planilha) e a faixa de preço é gravada no cadastro do cliente. Nada muda no piloto.
  2. **Origem:** cada empresa (fornecedor) guarda `cep_origem`, `latitude_origem` e `longitude_origem`. Se a consulta do CEP falhar ao salvar, a administradora digita latitude e longitude.
  3. **Preço único:** se a tabela for `UNICO` (BD-4), pula o cálculo de distância.
  4. **Cálculo (tabela `FAIXA`):** CEP do cliente vira coordenada pela BrasilAPI v2. Se não vier coordenada, usa o centro da cidade (código IBGE pelo ViaCEP e tabela de municípios do IBGE guardada no Supabase). A distância é Haversine × 1,25, **arredondada para cima** (99,2 km vira 100 km), e cai na mesma régua do gabarito do BE-3.
  5. **Ajuste manual:** o representante pode digitar ou corrigir a distância a qualquer momento, e o valor manual prevalece sobre o calculado.
  6. **Não localizado:** se o CEP for inválido ou a API estiver fora do ar, o cadastro fica com **distância pendente** (status próprio, diferente de `PENDENTE` da cotação), preço oculto e aviso para o representante preencher a distância.
  7. **Valores referenciais:** a simulação é referencial e só vale após o pedido fechado e aprovado, então a meta é acertar cerca de 80% dos casos e deixar o resto para o ajuste do representante.
     Teste: decisão registrada aqui.
- [x] **INF-8 · Projeto Supabase de produção.** Criar o 2º projeto gratuito no Supabase para Produção, aplicar os scripts SQL (`000` a `007`) e conferir que nada de produção aponta para o teste. Teste: os dois projetos aparecem no painel e estão isolados.
- [ ] **INF-6 · Publicar piloto no Streamlit Community Cloud.** Subir a branch `main` (atualizada com `dev`), configurar os `secrets` no painel do Streamlit Cloud e ativar a rotina semanal de backup manual (**BKP-1**) desde o dia 1 do piloto. Teste: o cliente piloto acessa pelo link HTTPS e faz uma cotação real.

**Pronto quando:** o 1º cliente piloto opera no Streamlit com segurança e as regras estão documentadas com gabarito.

## Fase C · Backend no Supabase (Aditivo, sem quebrar o piloto)

- [ ] **SEG-8 · Login único com Supabase Auth.** Preparar fluxo para representantes, clientes e administradora (O2/O3), mantendo compatibilidade com os dados do piloto. Teste: novo usuário criado no Auth entra e respeita status de validação.
- [ ] **SEG-9 · Regras de acesso por perfil (RLS).** Políticas por usuário logado (representante vê só os seus; cliente vê só os seus; prospect só envia; administradora vê tudo). Teste: consulta direta com token de um representante não devolve dados de outro.
- [ ] **BE-5 · Funções do banco (`RPC`) para as ações.** Criar cotação (confere empresa, tabela, retirada e preço visível; calcula faixa e totais), aprovar, cancelar, validar cadastro e liberar preço. Teste: resultados iguais ao gabarito do BE-3.
- [ ] **BE-6 · Importação de produtos e clientes.** Validação com linha/coluna do erro, resumo (novos, atualizados, desativados), execução transacional (tudo ou nada) e inativação sem apagar histórico (O7). Teste: arquivos com erro mostram mensagens claras.
- [ ] **BE-7 · Criação de representante pela administradora.** Edge Function com `service_role` guardada só no servidor: cria o acesso com senha provisória e marca de troca obrigatória no 1º acesso. Teste: só a administradora executa.
- [ ] **BE-8 · Cálculo de distância por CEP (O1).** Edge Function que aplica a decisão do BE-4: consulta o CEP, usa o centro da cidade quando faltar coordenada, calcula Haversine × 1,25 arredondado para cima e devolve a faixa de preço (uma única função das faixas, no lugar da regra duplicada no `app.py`). Na Fase C, guardar a distância e a faixa na ligação entre cliente e empresa, não só no cadastro do cliente (conferir o desenho do BD-3). **Calibração no piloto:** comparar cerca de 20 cidades reais do cliente com a distância que ele usa e ajustar o fator 1,25 se necessário.
      Teste: CEPs de teste caem na faixa certa, inclusive em 99, 100 e 500 km; CEP sem coordenada usa a cidade; CEP inexistente ou API fora do ar deixa a distância pendente sem bloquear; preço único não consulta CEP; valor digitado pelo representante prevalece.
- [ ] **SEG-13 · Proteção do formulário público.** Limite de envios e Cloudflare Turnstile (gratuito) no cadastro do prospect. Teste: 10 envios seguidos são bloqueados.
- [ ] **INF-9 · E-mail do sistema (O14).** SMTP próprio gratuito (ex: Brevo/Resend) com o domínio e modelos em português. Teste: e-mail chega na caixa de entrada.
- [ ] **BE-9 · Roteiro de testes SQL no repositório.** Scripts que validam todas as funções do banco antes de qualquer mudança. Teste: passa sem erro.

**Pronto quando:** os resultados batem com o gabarito do Python, o SEG-9 passa e o piloto no Streamlit continua operando normalmente.

## Fase D · React profissional

Para ser vendido, a tela precisa passar a imagem de um produto pronto, não de um protótipo.

- [ ] **PRO-1 · Identidade visual.** Nome, logo, cores, tipografia e tom de voz em português, num guia de 1 página. Teste: o guia está aprovado e é usado em todas as telas.
- [ ] **PRO-2 · Componentes e layout responsivo, mobile primeiro.** Uma biblioteca de componentes (por exemplo, Tailwind com shadcn/ui) para que todas as telas tenham o mesmo padrão. Teste: as telas ficam iguais e utilizáveis no celular e no computador.
- [ ] **FE-1 · Fluxos e telas por perfil.** Prospect, cliente, representante e administradora, desenhados no Google AI Studio ou no papel e validados com o cliente. Teste: o cliente aprova os fluxos antes de qualquer código final.
- [ ] **FE-2 · Projeto React ligado ao Supabase.** Só a chave pública no código; telas de carregamento, de erro e de lista vazia em todas as páginas. Teste: nenhuma tela fica em branco quando algo falha.
- [ ] **FE-3 · Telas do prospect.** Página do representante, escolha da empresa, formulário (nome, CNPJ, CEP e telefone), seleção de produtos e confirmação, com preço só se o representante liberar. Teste: um prospect de teste conclui um pedido de orçamento.
- [ ] **FE-4 · Telas do cliente.** Cadastro, login, escolha da empresa, catálogo com busca, carrinho, histórico e PDF; a retirada só aparece se estiver habilitada. Teste: um cliente de teste cota e baixa o PDF.
- [ ] **FE-5 · Telas do representante.** Solicitações, validação de cadastros, clientes com status (prospect ou cliente), liberação de preço e de retirada, uploads de produtos e clientes e troca de senha no primeiro acesso. Teste: o representante conclui um dia de trabalho sem usar o Streamlit.
- [ ] **FE-6 · Telas da administradora.** Representantes, empresas, vínculos e tabelas de preço. Teste: criar um representante e vinculá-lo a uma empresa.
- [ ] **PDF-1 · PDF gerado no navegador.** Com logo pequeno, dados da cotação e aviso de preços referenciais, e nunca salvo no banco. Teste: o arquivo abre bem e é leve (meta: abaixo de 300 KB com 30 itens).
- [ ] **PRO-3 · Acabamento.** Página 404, textos de erro amigáveis, acessibilidade básica, ícone e título da aba, e termos de uso e política de privacidade com aviso no cadastro. Teste: você percorre o app inteiro sem achar texto técnico, em inglês ou quebrado.
- [ ] **FE-7 · Ajustes de usabilidade com o cliente piloto.** Lista priorizada, um ajuste por vez (cliques para cotar, mensagens, busca). Teste: o piloto cota sem ajuda.
- [ ] **SEG-11 · Revisar o código gerado por IA.** Nenhuma chave de serviço no front, nenhuma regra de preço no navegador, nada de acesso sem as regras do banco. Teste: a busca por service_role no código do front não acha nada.
- [ ] **INF-10 · Publicar no Cloudflare Pages.** Ligado ao GitHub: a branch main publica o site e a dev gera uma versão de teste. Teste: cada envio de código atualiza o site.

**Pronto quando:** o roteiro de aceitação (prospect, cliente, representante e administradora) passa inteiro no React.

## Fase E · Virada e Produção

- [ ] **INF-11 · Domínio e DNS.** Registrar domínio (via Pix ou boleto) e apontar DNS para o Cloudflare; subdomínio por cliente (O9). Teste: app abre com HTTPS.
- [ ] **INF-12 · Migração dos usuários do piloto para o Supabase Auth.** Como o banco já é o de Produção, migrar os logins do piloto do Streamlit para o novo Auth e conferir contagens. Teste: piloto entra no React com seus dados históricos intactos.
- [ ] **BKP-1 · Backup semanal manual.** Exportar CSV de todas as tabelas toda semana e guardar em dois lugares (ativo desde o piloto). Teste: restauração em projeto de teste funciona.
- [ ] **BKP-2 · Controle do tamanho do banco.** Monitorar limite gratuito de 500 MB (alerta em 70%) e arquivar cotações com mais de 24 meses. Teste: uso registrado semanalmente.
- [ ] **INF-13 · Monitoramento.** Monitor gratuito de disponibilidade avisando por e-mail se o app cair. Teste: alerta chega ao e-mail.
- [ ] **BD-6 · Contração do banco.** Remover colunas antigas que sobraram do Streamlit, só depois de desligá-lo. Teste: React funciona sem elas.
- [ ] **FN-8 · Guia rápido de 1 página por perfil.** Teste: usuários operam sem suporte diário.
- [ ] **INF-14 · Desligar o Streamlit Community Cloud e marcar v2.0 no GitHub.** Teste: nenhum acesso restante ao app antigo.

**Pronto quando:** todos os clientes usam o React em produção sem suporte diário.

## Fase F · Automação com n8n e WhatsApp

- [ ] **INF-15 · Contratar a VPS.** Hostinger KVM 1 (Pix ou boleto) com n8n. Teste: n8n abre com HTTPS e senha forte.
- [ ] **INF-16 · Segurança básica da VPS.** Acesso por chave, firewall e atualizações automáticas. Teste: só portas necessárias respondem.
- [ ] **AUT-1 · Backup noturno automático.** n8n exporta tabelas e substitui o BKP-1. Teste: arquivo de hoje existe e restaura.
- [ ] **AUT-2 · Aviso ao representante.** Mensagem quando chega solicitação nova. Teste: aviso chega em menos de 1 minuto.
- [ ] **AUT-3 · Cotação por WhatsApp (O15).** Envio da cotação ao cliente após definir API oficial ou não oficial. Teste: cliente recebe cotação.
- [ ] **AUT-4 · Limpeza de PDFs guardados.** Apagar PDFs temporários no Storage após 30 dias. Teste: arquivo de teste some após o prazo.
