# Benchmark de interface: marketplaces e plataformas semelhantes

Levantamento feito em 4 e 5 de outubro de 2026, no navegador, só em páginas públicas e sem login, em tamanho de celular (375 px) e de computador. O objetivo é orientar o desenho das telas do AgroEncomenda. As funcionalidades e modelos de negócio dessas plataformas foram analisados antes, na pesquisa do projeto (seções 4 e 5).

| Plataforma | Tipo | Páginas observadas |
|---|---|---|
| [OLX](https://www.olx.com.br/agro-e-industria/tratores-e-maquinas-agricolas/estado-mg) | Classificados generalistas | Lista "Tratores e máquinas agrícolas em MG" e página de um anúncio |
| [Mercado Livre](https://www.mercadolivre.com.br/c/agro) | Marketplace generalista | Página da categoria Agro. A lista de resultados pediu verificação de conta e não foi analisada |
| [Agrofy](https://www.agrofy.com.br/tratores) | Marketplace agro | Lista de tratores e página de um anúncio |
| [MF Rural](https://www.mfrural.com.br/busca/tratores) | Classificados agro | Resultado de busca "tratores" |
| [Grão Direto](https://www.graodireto.com.br/) | Negociação de grãos (compra e venda) | Página inicial com ofertas |
| [GetNinjas](https://www.getninjas.com.br/) | Pedido de serviço com orçamentos | Página inicial |
| [BBZ Agro](https://www.bbzagro.com.br/) e [AgrSis](https://agrsis.com.br/) | Cotação de insumos | Páginas iniciais (texto "como funciona") |

## 1. Observações por tela

### Cabeçalho e navegação
- **OLX:** links de acessibilidade no topo ("Ir para o menu principal", "Ir para o conteúdo da página", "Ir para o rodapé"). No computador mostra Notificações, Entrar, Chat, Meus anúncios, Minhas vendas e Minhas compras. No celular tem barra fixa embaixo com **Início, Buscar, Anunciar, Chat e Menu**.
- **Mercado Livre:** busca "Digite o que você quer encontrar", seletor "Enviar para" com cidade e CEP, link "Pular para o conteúdo" e link "Comentar sobre acessibilidade".
- **Agrofy:** abas "Agrofy Market / Agrofy News", busca "O que está procurando?" e "Área de entrega".
- **Grão Direto:** cabeçalho mínimo no celular (menu, logo, Entrar e Cadastrar-se).

### Página inicial
- **Grão Direto:** frase principal ("Compre, venda e tenha preços e informações para negociar soja, milho e sorgo!") e duas abas grandes: **"Quero vender" e "Quero comprar"**. Logo abaixo, filtros de região e cidade e as ofertas.
- **GetNinjas:** "Mais de 500 tipos de serviços em um só lugar", serviços populares em atalhos, botão "Solicitar orçamento" em cada serviço e um **"como funciona" em três passos**: "Faça o seu pedido", "Receba até quatro orçamentos" e "Escolha o melhor".

### Localização
- **OLX:** seletor de estado acima dos filtros ("Minas Gerais") e caminho "Brasil > MG".
- **Agrofy:** na primeira visita abre uma janela pedindo a localização ("Usar minha localização atual" ou "Agora não"). Na lista, botão liga/desliga "Perto de mim".
- **Grão Direto:** filtros de Região e Cidade antes das ofertas.

### Lista de resultados e filtros
- **OLX:** título com local, "1 - 50 de 1.426 resultados", ordenação "Mais Relevantes", alternância entre lista e grade, botão "Filtros" e paginação "Página 1 de 29".
- **Agrofy:** barra com "Perto de mim", "Classificar" e "Filtrar", contagem ("278 resultados") e **atalhos de filtro em pílulas** (Usado, 4x4, Com preço, Venda).
- **MF Rural:** "Encontramos 11625 anúncios à venda com a expressão Tratores", botão "Filtrar" e uma lista longa de buscas relacionadas antes dos anúncios.

### Card de anúncio
| Plataforma | O que o card mostra |
|---|---|
| OLX | Foto, título, preço, parcelamento, cidade e bairro, data e hora ("Hoje, 16:40"), botão Chat, favoritar |
| Agrofy | Foto, condição (Usado), título, preço, ano, favoritar |
| MF Rural | Título, descrição curta, **preço com unidade** ("R$ 200.000,00 Unidade"), **cidade/UF**, "Ver produto" |
| Grão Direto | Preço por saca de 60 kg, **etiqueta CIF/FOB** (quem paga o frete), cidade/UF, "Ver oferta" |

### Página do anúncio
- **OLX:**
  - galeria ("1/6"), título, preço, descrição com "Ver descrição completa";
  - "Detalhes" (categoria, localização com bairro, cidade, UF e CEP);
  - **"Sobre o anunciante"** (vendas concluídas e canceladas, informações verificadas);
  - **"Dicas de segurança"**, **"Denunciar anúncio"** e "Publicado em 05/10 às 17:34";
  - no celular, botões **fixos no rodapé** ("Comprar" e "Chat").
- **Agrofy:**
  - galeria, condição, título, preço, cidade/UF;
  - "Informação sobre o vendedor" (nome, anos no setor, outros produtos);
  - número da publicação, "Denunciar" e "Última atualização";
  - **"Detalhes técnicos"** por categoria (tipo de operação, condição, cidade/estado, marca, modelo, ano).

### Publicar e pedir
- **AgrSis:** pedido de cotação em **cinco etapas** (categoria, produtos e quantidades, prazo e pagamento, local de entrega e frete, revisão).
- **BBZ Agro:** "pedidos padronizados com produto, quantidade, local de entrega, prazo e condições de pagamento". Propostas comparadas **lado a lado**.
- **AgrSis:** o comprador fica **anônimo** até a negociação ser fechada.

### Confiança
Dicas de segurança e botão de denúncia (OLX, Agrofy), dados do vendedor (OLX, Agrofy), depoimentos com cidade (GetNinjas) e identificação da empresa no rodapé (OLX).

### O que atrapalhou o uso no celular
- A OLX cobre metade da tela com um convite para baixar o aplicativo.
- A Agrofy abre uma janela pedindo localização antes de mostrar o conteúdo.
- Há publicidade entre os resultados em OLX e Mercado Livre.

## 2. Decisões de interface do AgroEncomenda

| # | Decisão | Inspiração | Quando |
|---|---|---|---|
| D1 | Página inicial com duas escolhas grandes, **"Quero vender" e "Quero comprar"** | Grão Direto | Iteração 0 (feito) |
| D2 | **"Como funciona" em três passos** na página inicial | GetNinjas | Iteração 0 (feito) |
| D3 | Link "Pular para o conteúdo", alvos de toque de 44 a 48 px e rótulos sempre visíveis | OLX, Mercado Livre, WCAG 2.2 | Iteração 0 (feito) |
| D4 | Identificação da plataforma e aviso "não intermedia pagamentos nem entregas" no rodapé | OLX, Decreto nº 7.962/2013 | Iteração 0 (feito) |
| D5 | Localização por **UF e município escolhidos pelo usuário**, sem pedir GPS e sem janela bloqueando a tela | OLX (estado), Agrofy (contraexemplo da janela) | Iterações 1 e 2 |
| D6 | Lista com título, contagem ("1–20 de 57"), ordenação, botão "Filtrar" que abre painel no celular, **filtros rápidos em pílulas** e paginação | OLX, Agrofy | Iterações 1 e 2 |
| D7 | **Card de anúncio:** foto, título, **preço por unidade** ("R$ 147,00 / saca 60 kg"), município/UF, data e condição | MF Rural, Grão Direto, OLX | Iteração 2 |
| D8 | **Card de encomenda:** quantidade + unidade, município de entrega, prazo ("faltam 5 dias"), número de propostas e etiqueta de status com texto e cor | Grão Direto, BBZ Agro | Iteração 1 |
| D9 | Etiqueta de transporte: "Vendedor entrega" ou "Comprador retira" (versão em português simples do CIF/FOB) | Grão Direto | Iterações 1 e 2 |
| D10 | Página de detalhe com detalhes por categoria, "Sobre o anunciante" (nome, município, membro desde), dicas de segurança, "Denunciar", data de publicação e **ação principal fixa no rodapé no celular** ("Fazer proposta") | OLX, Agrofy | Iterações 1, 2 e 4 |
| D11 | Publicar em **assistente de três passos** (o quê; quanto, onde e quando; detalhes e fotos) com revisão no final | AgrSis | Iterações 1 e 2 |
| D12 | Propostas de uma encomenda **comparadas lado a lado** | BBZ Agro | Iteração 3 |
| D13 | Até o aceite, mostrar só o **primeiro nome e o município** das partes | AgrSis (anonimato) | Iteração 1 |
| D14 | Quando houver as áreas de busca, publicação e mensagens, avaliar **barra fixa embaixo no celular** (Início, Buscar, Publicar, Mensagens, Painel) | OLX | Iteração 3 |
| D15 | Não usar janelas de convite (aplicativo, localização) nem publicidade entre os resultados | Contraexemplos OLX e Agrofy | Sempre |
