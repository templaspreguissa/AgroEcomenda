# Roteiro de demonstração (cerca de 15 minutos)

Roteiro para apresentar o AgroEncomenda no Trabalho A3 usando só os **dados fictícios** do comando `carregar-demo`. Cada passo diz o que abrir, o que mostrar e qual requisito ele comprova.

## Antes de começar

Recrie o banco para a demonstração começar sempre igual:

```powershell
flask --app app init-db --yes
flask --app app carregar-municipios MG
flask --app app carregar-demo --senha-fixa
flask --app app run --debug
```

- Contas: `ana`, `carlos`, `jose`, `rita`, `paulo`, `marina` e `admin`, todas com e-mail `<nome>.demo@example.com`. A senha está em `app/demo.py` (opção `--senha-fixa`). No site publicado, as senhas são as que o `carregar-demo` mostrou no servidor ([como publicar](publicar-no-pythonanywhere.md)).
- Dica: use **duas janelas** do navegador, uma normal e uma anônima, para mostrar duas pessoas ao mesmo tempo (por exemplo, a loja e a produtora).
- Deixe um terminal aberto com o `pytest` já rodado (334 testes) para a parte de qualidade.

| Conta | Papel na história |
|---|---|
| Ana Ribeiro, Sítio Boa Vista (Uberaba) | Produtora de hortaliças, ovos e morango; tem contrato ativo com o Mercado Bom Preço |
| Carlos Mendes, Queijaria Serra Azul (Sacramento) | Queijo artesanal com selo ARTE e leite vendido só para laticínio |
| José Antunes, Fazenda Santa Clara (Conceição das Alagoas) | Café e milho vendidos só para lojas |
| Rita Souza, Mercado Bom Preço (Uberaba) | Loja **verificada** |
| Paulo Lima, Restaurante Sabor da Roça (Sacramento) | Loja **ainda não verificada** |
| Marina Costa (Uberaba) | Consumidora |
| Equipe AgroEncomenda | Administração |

## 1. O problema e a proposta (1 min)

Página inicial, sem entrar. Mostre as três portas: "Sou produtor", "Tenho um comércio" e "Quero comprar do produtor". Explique que a plataforma **não vende nada** (rodapé): ela aproxima quem produz de comércios e consumidores da região.

## 2. O que o consumidor vê (3 min)

1. **Produtos** com "Perto de: Uberaba/MG": a ordem vai do mesmo município para a mesma região imediata do IBGE e depois para o resto (RF30). Marque "Só a região de Uberaba".
2. O card do **Morango** mostra a safra de junho a outubro: "Na safra" ou "Fora da safra", conforme o mês da apresentação. Mostre também o filtro "Só o que tem neste mês" (RF32).
3. Abra **Ovos caipira**: o aviso "Inspeção municipal: pode ser vendido só dentro de Uberaba/MG" vem da Lei nº 1.283/1950 (seção 6.1 do documento de visão).
4. Abra a vitrine **Sítio Boa Vista**: formas de venda, feira, orgânico declarado com OCS e "**Encontre também em: Mercado Bom Preço**", que só aparece porque as duas partes do contrato autorizaram (RF26, RF36).
5. Repare que leite, café em grão e milho **não aparecem**: são vendidos só para lojas.
6. Entre como **Marina** e faça um pedido do **Queijo minas artesanal**: o preço vem preenchido com o preço de consumidor (RF31).

## 3. O que a loja vê no mesmo produto (3 min)

1. Entre como **Rita** (outra janela). A faixa no topo diz "Preços que você vê: para lojas".
2. Abra o **Queijo minas artesanal**: agora aparecem o preço para lojas, o **pedido mínimo** e o preço ao consumidor como referência (RF28, RF29). Clique em "Ver como consumidor" e volte.
3. Abra o **Leite refrigerado para laticínio**: só para lojas, com o aviso de produto sem registro de inspeção. "Pedir cotação para a loja" já vem com o pedido mínimo de 500 litros.
4. Abra **Contratos › Contrato nº 1**: versão, código SHA-256, aceites das duas partes com data e hora e "**Versão para imprimir ou salvar em PDF**" (RF34, RF35).

## 4. Preço só para lojas verificadas (1 min)

1. Entre como **Paulo** (loja **não** verificada) e abra **Ovos caipira**: aparece "Preço só para lojas verificadas", e o filtro de preço também não revela o valor (RN13).
2. Entre como **admin**, vá em **Administração › Lojas** e verifique o Restaurante Sabor da Roça, escrevendo o motivo (RF38).
3. Volte para Paulo e recarregue: o preço para lojas aparece.

## 5. O dia a dia da produtora (3 min)

1. Entre como **Ana**. O topo mostra **Avisos** e **Mensagens** com contador (RF13, RF14).
2. Em **Avisos**: "Encomenda nova perto de você" (o alerta da região, RF37) e a mensagem da Rita.
3. Em **Mensagens**: a conversa sobre a alface; responda (RF33).
4. Em **Comércios**, que só produtores veem, aparecem o Mercado e o Restaurante, do mais perto para o mais longe (RF27). Abra o Restaurante e clique em "**Propor contrato de fornecimento**": preencha um item, salve o rascunho e envie.
5. Entre como **Paulo**: o aviso chega, ele abre o contrato e **aceita a versão 1**. O contrato fica ativo.
   - Se der tempo, Paulo pode "Propor alterações" antes de aceitar. Isso cria a versão 2, e a Ana precisa aceitar a nova versão (RN19).

## 6. Confiança (2 min)

1. Entre como **admin** e abra **Denúncias**: a denúncia da Marina sobre o tomate. Mostre que o denunciado não vê quem denunciou e que a decisão pede um motivo (RF19, RF25).
2. Abra **Registro**: cada ação com quem, quando, sobre o quê e por quê (RNF12).
3. Na conta da Marina, mostre no painel "**Baixar meus dados**" (JSON) e "**Excluir minha conta**" (LGPD, art. 18; RF21). Não precisa excluir.
4. Na tela de entrar, mostre "**Esqueci minha senha**". O link de nova senha aparece no terminal do servidor, porque o projeto não tem servidor de e-mail.

## 7. Qualidade (2 min)

- `pytest`: 334 testes. Destaque `test_visibilidade.py` (o preço de loja nunca chega ao HTML de quem não pode vê-lo), `test_seguranca.py` (todas as rotas, login, administração e CSRF) e `test_acessibilidade.py` (estrutura das páginas e contraste das cores).
- Documentos: `docs/visao-produtor-comercio-consumidor.md` (requisitos RF26–RF38, regras de negócio, diagramas e fontes), `docs/benchmark-marketplaces.md` e a pesquisa do projeto.

## Perguntas que a banca pode fazer

| Pergunta | Resposta curta |
|---|---|
| Por que não tem pagamento? | Fora do escopo por decisão: a plataforma aproxima e registra a negociação, e o pagamento é direto entre as partes. Isso mantém o MVP simples e evita guardar dados financeiros. |
| O consumidor consegue ver o preço de loja? | Não. O servidor decide o que mostrar (`app/visibilidade.py`). O valor não vai para o HTML e não pode ser descoberto pelo filtro de preço, e há testes para isso. |
| E se alguém cadastrar um CNPJ falso? | O dígito verificador é conferido (inclusive no CNPJ alfanumérico de 2026) e o CNPJ não pode se repetir entre contas. O produtor pode exigir loja verificada, e a verificação é feita pela administração. |
| O contrato tem validade? | O Código Civil (art. 107) não exige forma especial para a maioria dos contratos, e a MP nº 2.200-2/2001 (art. 10, § 2º) aceita outros meios de prova de autoria e integridade quando as partes admitem. O sistema registra o aceite com o código SHA-256 da versão e recomenda revisão jurídica. |
| Como fica a LGPD? | Dados mínimos, sem CPF e sem GPS. Telefone só se a pessoa quiser. Aceite dos termos registrado. Exportação, correção e exclusão com anonimização. A moderação só lê conversas denunciadas. |
| Por que Flask e SQLite? | São suficientes para o MVP acadêmico, fáceis de rodar no computador de qualquer pessoa do grupo e bem documentados. A seção 9.2 da pesquisa diz quando valeria mudar. |
| O que é "região"? | A Região Geográfica Imediata do IBGE (2017): cidades próximas onde a população busca bens e serviços. Vem da API de Localidades do IBGE, sem precisar de coordenadas. |
