# AgroEncomenda

Plataforma que aproxima **quem produz no campo** de **comércios** (mercados, restaurantes, distribuidores, cooperativas) e do **consumidor final** da mesma região. Projeto acadêmico do **Trabalho A3** da disciplina **Projeto e Engenharia de Software**.

Uma mesma conta pode ter até três papéis:

- **produtor:** cria uma **vitrine** com o que produz, como vende (retirada, entrega, feira) e onde encontrar, e cadastra seus **produtos** com um preço para o consumidor final, um preço para lojas ou os dois;
- **comércio:** cadastra a **loja** com CNPJ e diz o que compra, para ser encontrado pelos produtores da região. Vê os **preços para lojas** e o pedido mínimo, pede cotações e publica **encomendas** do que precisa;
- **consumidor:** encontra produtores e produtos perto de casa, vê o preço de consumidor e faz pedidos.

A plataforma **não vende produtos, não intermedia pagamentos e não faz entregas**. Ela ajuda o produtor a vender mais, os comércios a conhecerem as opções da região e o consumidor a chegar direto a quem produz. A visão completa, as regras de negócio e as fontes estão em [docs/visao-produtor-comercio-consumidor.md](docs/visao-produtor-comercio-consumidor.md).

> **Status:** as sete iterações do plano estão concluídas. O sistema tem vitrines de produtores, lojas com CNPJ, produtos com preço para o consumidor e para lojas, busca por região, encomendas e propostas, conversas e avisos, contratos de fornecimento com aceite registrado e "onde comprar", e uma administração mínima com denúncias, verificação de lojas, bloqueio de contas e registro de cada ação. A conta pode baixar os próprios dados, ser excluída e recuperar a senha. São 334 testes automáticos, incluindo revisões de segurança e de acessibilidade. Para apresentar, siga o [roteiro de demonstração](docs/roteiro-demonstracao.md). Para colocar o site na internet, siga [Publicar no PythonAnywhere](docs/publicar-no-pythonanywhere.md).

## Como funciona: produtores, comércios e consumidores

1. No cadastro, a pessoa marca como vai usar o sistema e já é levada a criar a **vitrine** (produtor) e/ou a **loja** (comércio).
2. Só cadastra produtos quem tem vitrine. A vitrine mostra o município, a região, as formas de venda, onde e quando encontrar o produtor e, se ele quiser, um telefone com link para o WhatsApp. Produção orgânica só pode ser declarada com a certificadora ou a OCS.
3. A loja é cadastrada com **CNPJ conferido pelo dígito verificador**, sem repetição entre contas. Ela informa o tipo de comércio, o que compra e quanto. Os dados das lojas aparecem **só para produtores**.
4. Os diretórios de **Produtores** e de **Comércios** mostram primeiro quem está no mesmo município, depois na mesma **região imediata** do IBGE, depois no mesmo estado. Não há GPS: a pessoa escolhe a cidade em "Perto de".
5. Em produtos de origem animal, o produtor informa o **serviço de inspeção** (SIF, Sisbi-POA, SIE, SIM ou selo ARTE). A página do produto mostra até onde ele pode ser vendido, conforme a Lei nº 1.283/1950, e o sistema não aceita proposta de quem está fora dessa área (por exemplo, um comprador de outra cidade num produto com SIM). Produto sem registro de inspeção só pode ser oferecido a lojas.

## Como funciona a oferta: produtos com preço por público

1. O produtor cadastra um **produto** com até 5 fotos, unidade, quantidade disponível, município e **quando tem**: o ano todo, só na safra (marcando os meses) ou sob encomenda. Conforme a categoria, aparecem campos específicos: safra e variedade para a produção agrícola; raça, idade e sexo para a pecuária; serviço de inspeção para produtos de origem animal; validade e ingredientes para processados; área e período para serviços rurais.
2. Ele marca **para quem vende**: consumidor final, lojas ou os dois. Cada público tem o seu preço (ou "a combinar"). Para lojas, pode haver **pedido mínimo** e a opção de mostrar o preço **só a lojas verificadas**.
3. **Quem acessa vê o preço do seu público:**

   | Quem acessa | Produtos listados | Preço mostrado |
   |---|---|---|
   | Visitante ou conta sem loja | Os vendidos ao consumidor final | Preço de consumidor |
   | Conta com loja (modo loja) | Os vendidos a lojas | Preço para lojas, pedido mínimo e preço ao consumidor como referência |
   | Loja não verificada, em produto "só verificadas" | Aparece | "Preço só para lojas verificadas" |
   | Dono do produto ou administração | Todos | Os dois |

   Quem tem loja pode trocar entre **"Ver como loja"** e **"Ver como consumidor"** no topo da página. O preço que a pessoa não pode ver não vai para o HTML e não pode ser descoberto pelo filtro ou pela ordenação por preço.
4. Na busca de **Produtos**: palavra sem acento, categoria, estado, faixa de preço (sobre o preço que a pessoa vê), "Perto de", "Só a região de..." e "Só o que tem neste mês". A ordem padrão é do mais perto para o mais longe.
5. O consumidor **faz um pedido** e a loja **pede uma cotação**, com preço, quantidade, data de entrega e transporte. O sistema decide sozinho se a compra é como consumidor ou como loja, e a cotação de loja respeita o pedido mínimo. O produtor vê o nome da loja que pediu a cotação.
6. O produtor aceita ou recusa cada proposta. O produto continua ativo depois de um aceite, porque ele pode vender para mais de um comprador. Para parar de receber propostas, ele pode **pausar** ou **encerrar** o produto. Se deixar de vender para um público, as propostas pendentes daquele público são encerradas com aviso.
7. A regra de privacidade é a mesma das encomendas: nome completo e e-mail só aparecem para as duas partes depois do aceite.

## Como funciona a comunicação

1. **Mensagens:** "Perguntar ao produtor" (na página do produto), "Mandar mensagem" (na vitrine), "Apresentar meus produtos" (na página da loja, só para produtores), "Tirar dúvida com o comprador" (na encomenda) e "Mensagem" em cada proposta. Cada assunto tem uma conversa por par de pessoas: voltar ao mesmo assunto continua a conversa.
2. **Quem fala com quem sai do assunto**, consultado no servidor. Só os dois participantes leem a conversa; para qualquer outra pessoa ela não existe (404). Cada lado vê o primeiro nome e os nomes de vitrine ou loja do outro, nunca o e-mail.
3. **Contra spam:** até 20 conversas novas por dia e 60 mensagens por hora por pessoa (ajustáveis em `CONVERSAS_NOVAS_POR_DIA` e `MENSAGENS_POR_HORA`).
4. **Avisos:** proposta recebida, aceita ou recusada, mensagem nova, encomenda expirada e oportunidades perto de você. O topo mostra quantos avisos e mensagens estão sem ler. Abrir um aviso marca como lido e leva à página certa, sempre dentro do site.
5. **Alertas da região:** quando um produtor cadastra um produto vendido a lojas, as lojas da mesma região imediata que compram aquela categoria recebem um aviso. Quando uma loja publica uma encomenda, os produtores da mesma região que vendem aquela categoria também recebem.

## Como funcionam os contratos de fornecimento

1. **Quem propõe:** o produtor, na página de uma loja ("Propor contrato de fornecimento"); a loja, na página de um produto vendido a lojas; ou qualquer das partes, numa proposta aceita ("Transformar em contrato"). O formulário já vem preenchido com o que se sabe (produto, preço para lojas, pedido mínimo, quantidade e transporte da proposta).
2. **O que se combina:** até 10 itens (produto do catálogo ou descrição livre, quantidade por entrega, unidade e preço), início e fim (até dois anos), frequência (semanal, quinzenal, mensal ou sob demanda), dia e local de entrega, transporte, pagamento, reajuste, padrão de qualidade e aviso prévio para rescisão.
3. **Negociação:** o contrato nasce como rascunho, que só o autor vê. Ao enviar, o autor já aceita a versão 1. A outra parte aceita, recusa ou propõe alterações; cada alteração vira uma nova versão, já aceita por quem alterou, e a vez passa para o outro lado. O contrato fica **ativo** quando as duas partes aceitam a **mesma versão**.
4. **Registro:** cada versão é guardada em JSON canônico com **código SHA-256**, e cada aceite registra quem, quando, a versão e o código. Se o contrato mudou enquanto a pessoa lia, o aceite é recusado ("o contrato mudou, revise"). A página confere o código a cada visita.
5. **Impressão:** "Versão para imprimir ou salvar em PDF" gera as cláusulas a partir dos campos, com o registro de aceite e a cláusula em que as partes admitem o aceite eletrônico (MP nº 2.200-2/2001, art. 10, § 2º). Não usa biblioteca de PDF: o navegador imprime ou salva.
6. **Depois do aceite:** o contato das duas partes é liberado. Qualquer parte pode **rescindir** informando o motivo; as entregas seguem durante o aviso prévio. No fim da vigência, o contrato é encerrado sozinho.
7. **Onde comprar:** se as duas partes autorizarem, a vitrine do produtor mostra "Encontre também em: Mercado X — Cidade/UF", a página da loja mostra os "Fornecedores locais" e a página do produto mostra "Também à venda em". É o caminho do consumidor até a loja que revende o produto local.

## Como funcionam a moderação e os seus dados

1. **Denunciar:** produto, vitrine, loja, encomenda e conversa têm o link "Denunciar". A pessoa escolhe o motivo (golpe, produto proibido ou sem inspeção, informação falsa, conteúdo ofensivo, spam ou outro) e pode contar o que aconteceu. Quem foi denunciado não fica sabendo quem denunciou.
2. **Administração** (`/admin`, só para contas com papel de administração):
   - **Denúncias:** fila das mais antigas para as mais novas, com quantas denúncias o mesmo item recebeu. A decisão (procede ou não) pede um motivo e pode ocultar o item e bloquear a conta. A moderação só lê uma conversa se ela foi denunciada.
   - **Lojas:** verificar a loja depois de conferir o CNPJ na Receita Federal, ou retirar o selo.
   - **Usuários:** buscar e bloquear ou desbloquear. Conta bloqueada perde a sessão, e o que ela publicou some das listas e das páginas públicas.
   - **Categorias e unidades:** criar subcategorias e unidades, ativar e desativar categorias.
   - **Registro:** toda ação, com quem, quando, sobre o quê e por quê. Nada é feito sem motivo.
   - Nas páginas de produto, vitrine, loja e encomenda, a administração também vê uma caixa de **Moderação** para ocultar ou voltar a mostrar.
3. **Seus dados (LGPD, art. 18):** no painel, "Baixar meus dados" entrega tudo em JSON, e "Excluir minha conta" (com a senha) apaga ou anonimiza os dados pessoais. O que a outra parte precisa para o próprio histórico (mensagens recebidas, propostas, texto de contratos aceitos) continua, com o autor como "Usuário removido". Contratos ativos são rescindidos, com aviso para a outra parte.
4. **Esqueci minha senha:** o link vale por 1 hora e uma única vez. Só o hash do código fica guardado. A tela responde igual para qualquer e-mail, para não revelar quem tem conta. No projeto acadêmico não há servidor de e-mail: o link aparece no **registro (log) do servidor** de desenvolvimento.

## Como funciona o fluxo de demanda

1. O comprador publica uma **encomenda**: o que precisa, categoria, quantidade e unidade, município de entrega, prazo limite, quem faz o transporte e condições de pagamento.
2. Vendedores encontram a encomenda em **Encomendas abertas** (busca sem acento, filtro por categoria e estado) e enviam uma **proposta** com preço por unidade, quantidade, data de entrega, transporte e validade. Cada vendedor tem no máximo uma proposta pendente por encomenda e pode editá-la ou retirá-la.
3. O comprador **compara as propostas lado a lado** e aceita ou recusa. Ao aceitar, a encomenda é concluída e as demais propostas são encerradas, com aviso aos vendedores.
4. Até o aceite, cada lado vê só o primeiro nome e o município do outro. Depois do aceite, comprador e vendedor daquela proposta veem nome completo e e-mail para combinar pagamento e entrega.
5. Encomendas cujo prazo passou são encerradas automaticamente.

Estados: encomenda `aberta → em_negociacao → concluida | cancelada | expirada`; proposta `pendente → aceita | recusada | retirada | nao_selecionada`.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Interface | HTML5, CSS3 próprio (pensado primeiro para o celular) e JavaScript mínimo |
| Servidor | Python 3.9+ com Flask 3.1 e Flask-WTF (formulários e proteção CSRF) |
| Banco de dados | SQLite 3.37+ (tabelas `STRICT`, chaves estrangeiras ativadas em toda conexão) |
| Testes | pytest |
| Versionamento | Git e GitHub |

## Como rodar no Windows (PowerShell)

Pré-requisito: Python 3.9 ou mais novo ([python.org](https://www.python.org/downloads/) ou `winget install Python.Python.3.14`).

```powershell
# 0. Baixar o projeto
git clone https://github.com/templaspreguissa/AgroEcomenda.git
cd AgroEcomenda

# 1. Na pasta do projeto, criar e ativar o ambiente virtual
py -3 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Instalar as dependências (Flask, Flask-WTF, Pillow e pytest)
pip install -r requirements-dev.txt

# 3. Criar o banco e carregar categorias e unidades de medida
flask --app app init-db

# 4. Carregar os municípios de uma UF pela API do IBGE (com a região imediata de cada um)
flask --app app carregar-municipios MG

# 5. (Opcional) Carregar dados de demonstração fictícios: 3 produtores, 2 lojas, 1 consumidor e 1 administração
flask --app app carregar-demo --senha-fixa

# 6. Rodar em modo de desenvolvimento
flask --app app run --debug
```

Acesse <http://127.0.0.1:5000>. O banco fica em `instance/agroencomenda.db` e as fotos em `instance/uploads/`, ambos fora do Git.

As contas de demonstração usam e-mails terminados em `.demo@example.com`: `ana` (produtora), `carlos` (queijaria), `jose` (fazenda de café e milho), `rita` (mercado verificado), `paulo` (restaurante ainda não verificado), `marina` (consumidora) e `admin` (administração). Com `--senha-fixa`, a senha de todas é a de `app/demo.py`. Como esse arquivo é público, use essa opção só no computador local. Sem ela, o comando sorteia uma senha para as contas da história e outra para a administração, e mostra as duas uma única vez. É assim que se carrega a demonstração no site publicado.

Para dar o papel de administração a uma conta (ou tirar, com `--remover`):

```powershell
flask --app app tornar-admin <email da conta>
```

A verificação de lojas é feita em **Administração › Lojas**. O comando `flask --app app verificar-comercio <id da conta>` continua disponível.

> **Atualizando de uma versão anterior?** O banco mudou em várias iterações (a mais recente é a 7, com denúncias e recuperação de senha). Rode `flask --app app init-db` e depois `flask --app app carregar-municipios MG` de novo, lembrando que `init-db` apaga os dados de teste. Se vier da Iteração 1, rode também `pip install -r requirements-dev.txt` (a Iteração 2 passou a usar a biblioteca Pillow).

No Linux ou macOS, troque `py -3` por `python3` e ative o ambiente com `source .venv/bin/activate`.

### Rodar os testes

```powershell
pytest
```

São 334 testes. Além das regras de negócio, há três revisões automáticas que valem para as telas que forem criadas depois:

- `tests/test_seguranca.py` percorre **todas as rotas**: o que não é página pública exige login, a administração recusa quem não é administrador e todo POST sem token CSRF é recusado;
- `tests/test_acessibilidade.py` abre as páginas como visitante, produtora, loja e administração e confere idioma, título, um único `h1`, ids sem repetição, rótulo em todo campo, texto alternativo em imagens e nome em links e botões, além do **contraste** das cores do CSS (pelo menos 4,5:1, WCAG 2.2, critério 1.4.3);
- `tests/test_visibilidade.py` confere que o preço para lojas nunca chega ao HTML de quem não pode vê-lo.

### Fora do modo de desenvolvimento

O passo a passo completo para publicar está em [docs/publicar-no-pythonanywhere.md](docs/publicar-no-pythonanywhere.md). O PythonAnywhere foi escolhido porque o plano gratuito guarda os arquivos (o banco SQLite e as fotos) e libera a API do IBGE.

Sem a chave secreta (`SECRET_KEY` em `instance/config.py` ou a variável `FLASK_SECRET_KEY`), a aplicação usa uma chave temporária e as sessões caem a cada reinício. Para gerar uma e defini-la como variável de ambiente:

```powershell
python -c "import secrets; print(secrets.token_hex())"
$env:FLASK_SECRET_KEY = "<valor gerado>"
```

Nunca coloque a chave no código nem no Git.

## Estrutura

```text
app/
├── __init__.py        # create_app(): configuração, CSRF, cabeçalhos de segurança, blueprints
├── db.py              # conexão SQLite (PRAGMA foreign_keys = ON) e comandos init-db / carregar-municipios
├── schema.sql         # esquema completo do banco (usuário, perfis, produto, encomenda, proposta, mensagem...)
├── seed.sql           # unidades de medida, categorias e atributos por categoria
├── servicos/          # regras de negócio, sempre em transação: encomendas, produtos, conversas, alertas,
│                      # contratos, moderação e conta (exportar, excluir, recuperar senha)
├── visibilidade.py    # quem vê quais produtos e quais preços (modo consumidor ou loja)
├── fotos.py           # upload seguro: valida o conteúdo, remove EXIF/GPS, redimensiona, renomeia
├── atributos.py       # campos específicos por categoria (RF05)
├── inspecao.py        # serviço de inspeção de produtos de origem animal e área de venda permitida
├── cnpj.py            # validação de CNPJ numérico e alfanumérico (Receita Federal, julho de 2026)
├── util.py            # reais, quantidades, unidades, telefones, datas e busca sem acentos
├── localidades.py     # municípios e regiões imediatas do IBGE, ordenação por proximidade
├── formularios.py     # base dos formulários (mensagens em português)
├── comandos.py        # comandos carregar-demo, tornar-admin e verificar-comercio
├── demo.py            # dados de demonstração fictícios
├── auth/              # cadastro (com "como vai usar"), login, logout, limite de tentativas, decoradores
├── perfis/            # vitrine do produtor, loja (comércio), diretórios por região, dados da conta
├── comunicacao/       # mensagens (conversas) e avisos
├── contratos/         # contratos de fornecimento: propor, negociar versões, aceitar, imprimir, rescindir
├── admin/             # administração: denúncias, lojas, usuários, categorias, registro
├── produtos/          # produtos e propostas de compra: lista, cadastrar, editar, pausar, encerrar, fotos
├── encomendas/        # encomendas e propostas: lista, publicar, editar, cancelar, propor, aceitar, recusar
├── main/              # página inicial, termos, privacidade, painel
├── templates/         # HTML (Jinja)
└── static/            # CSS e JavaScript
docs/
├── benchmark-marketplaces.md            # análise de interface de OLX, Agrofy, MF Rural, Grão Direto, GetNinjas...
├── publicar-no-pythonanywhere.md       # passo a passo para colocar o site na internet
├── roteiro-demonstracao.md             # roteiro de 15 minutos para a apresentação
└── visao-produtor-comercio-consumidor.md # visão v2: papéis, regras, requisitos RF26–RF38, diagramas e fontes
tests/                 # testes automatizados (pytest)
```

## Segurança e privacidade já aplicadas

- Senhas guardadas com hash `pbkdf2:sha256:600000` (recomendação da OWASP). A senha nunca é armazenada.
- Regras de senha do NIST SP 800-63B-4: mínimo de 15 caracteres (frase-senha), sem regras de composição, bloqueio de senhas comuns e limite de tentativas de login.
- Proteção CSRF em todos os formulários. Logout só por POST.
- SQL sempre parametrizado. Escape automático de HTML nos templates.
- Cabeçalhos `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options` e `Referrer-Policy`.
- Cookie de sessão `HttpOnly` e `SameSite=Lax`, sessão renovada no login e redirecionamento só para páginas internas.
- Registro do aceite dos Termos e da Política de Privacidade (versão e data). Dados mínimos: sem CPF, sem endereço.
- CNPJ das lojas conferido pelo dígito verificador (formatos numérico e alfanumérico) e único por conta. Trocar o CNPJ tira o selo de verificado.
- Telefone público é opcional e decidido pelo próprio usuário. Os dados das lojas aparecem só para quem tem vitrine de produtor, para evitar raspagem de contatos.
- Sem GPS: a proximidade é calculada pelo município e pela região imediata do IBGE que a pessoa escolhe.
- Recuperação de senha com código de uso único, válido por 1 hora, guardado só como hash, e resposta igual para qualquer e-mail. Exclusão de conta pede a senha e usa o mesmo limite de tentativas do login.
- Área de administração protegida no blueprint inteiro (nenhuma rota nova fica aberta por esquecimento) e registro de toda ação com motivo (OWASP Top 10:2025, A09).
- Conta bloqueada ou excluída perde a sessão na próxima página, e o que ela publicou deixa de aparecer.
- Upload de fotos conforme a OWASP: só JPEG, PNG ou WebP conferidos pelo conteúdo (Pillow), até 8 MB cada e 5 por produto, proteção contra imagens gigantes, nome gerado pelo sistema, arquivos fora de `/static`. As fotos são regravadas **sem metadados EXIF** (que podem trazer a localização GPS de onde foram tiradas). Fotos de produto ou vitrine oculta pela moderação não podem ser abertas pelo link direto.

Durante o trabalho acadêmico, **use apenas dados fictícios**.

## Requisitos atendidos nesta versão

| Código | Requisito | Situação |
|---|---|---|
| RF01 | Cadastro de usuários | Feito (conta única que compra e vende, papel `admin` separado) |
| RF02 | Login e alteração de dados | Feito (edição de nome, tipo de conta e município; recuperação de senha por link de uso único) |
| RF03 | Bloqueio de áreas por perfil | Feito (decoradores `login_obrigatorio` e `admin_obrigatorio`) |
| RF04 | Cadastrar produto com título, descrição, fotos, preço, quantidade, unidade e local | Feito (exige vitrine de produtor) |
| RF05 | Campos específicos por categoria | Feito (produção agrícola, pecuária, origem animal com inspeção, processados e serviços rurais) |
| RF06 | Busca e filtros de produtos | Feito (palavra-chave, categoria, estado, faixa de preço, região, safra, ordenação) |
| RF07 | Publicar encomenda com produto, quantidade, local e prazo | Feito |
| RF08 | Listar encomendas e enviar proposta | Feito (busca, filtros por categoria e estado, ordenação, paginação) |
| RF09 | Aceitar ou recusar proposta | Feito (com confirmação antes da ação) |
| RF10 | Status da negociação | Feito (estados separados para encomenda e proposta) |
| RF11 | Painel do usuário | Feito (vitrine, loja, produtos com os dois preços, encomendas e propostas enviadas) |
| RF12 | Mensagens entre as partes | Feito (conversas por assunto, só entre os participantes) |
| RF13 | Notificação de proposta, aceite e recusa | Feito (tela de avisos, contador no topo, marcar como lidos) |
| RF14 | Notificação de mensagens | Feito (contador de mensagens não lidas no topo) |
| RF15 | Painel administrativo | Feito (denúncias, lojas, usuários, categorias, registro) |
| RF16 | Excluir ou desativar produtos e encomendas | Feito (produto: editar, pausar, reativar, encerrar; encomenda: editar sem propostas, cancelar) |
| RF17 | Encerrar encomendas vencidas | Feito (automático) |
| RF18 | Proposta de compra sobre produto | Feito |
| RF19 | Denunciar conteúdo | Feito (produto, vitrine, loja, encomenda e conversa, com motivo) |
| RF20 | Administração de categorias e unidades | Feito (criar subcategorias e unidades, ativar e desativar categorias; os campos por categoria ficam no `seed.sql`) |
| RF21 | Consultar, corrigir e excluir os próprios dados | Feito ("Meus dados", "Baixar meus dados" em JSON, "Excluir minha conta" com anonimização) |
| RF22 | Aceite de Termos e Política de Privacidade | Feito |
| RF23 | Comparar propostas lado a lado | Feito |
| RF24 | Editar ou retirar proposta pendente | Feito |
| RF25 | Bloquear usuários e registrar a moderação | Feito (bloqueio tira a sessão e esconde o conteúdo; registro com quem, quando, o quê e por quê) |
| RF26 | Vitrine do produtor | Feito (formas de venda, onde encontrar, orgânico declarado, foto, telefone opcional) |
| RF27 | Perfil de comércio com CNPJ e diretório para produtores | Feito |
| RF28 | Produto para consumidor, para lojas ou para os dois, com preço de cada público | Feito (com pedido mínimo e "só verificadas") |
| RF29 | Preço mostrado conforme quem acessa | Feito (inclusive "Ver como consumidor" para quem tem loja) |
| RF30 | Busca por região (região imediata do IBGE) | Feito em produtos, encomendas, produtores e comércios |
| RF31 | Pedido do consumidor e cotação da loja | Feito (canal decidido no servidor, pedido mínimo) |
| RF32 | Safra e "o que tem neste mês" | Feito |
| RF33 | Conversas entre produtor, comércio e consumidor | Feito (limites contra spam) |
| RF34 | Contrato de fornecimento com versões e aceite registrado | Feito (hash SHA-256 por versão, aceite protegido contra versão desatualizada) |
| RF35 | Versão para imprimir do contrato | Feito (cláusulas geradas, registro de aceite, CSS de impressão) |
| RF36 | Parcerias públicas: "onde comprar" | Feito (só com autorização das duas partes) |
| RF37 | Alertas de oportunidade na região | Feito (produto novo para lojas, encomenda nova para produtores) |
| RF38 | Verificação de comércio | Feito (Administração › Lojas, com motivo registrado) |
| RNF01 | Interface responsiva | Feito (pensada primeiro para o celular; tabelas viram cartões; topo cabe em uma linha) |
| RNF02 | Senhas com hash adaptativo | Feito |
| RNF05 | Integridade referencial no SQLite | Feito (`PRAGMA foreign_keys = ON` + restrições `CHECK`) |
| RNF08 | Acessibilidade (WCAG 2.2 AA) | Revisão automática de estrutura e contraste em `tests/test_acessibilidade.py`. Faltam testes com leitor de tela e com usuários |
| RNF09 | Privacidade: dados mínimos e localização por município | Feito (sem CPF, sem endereço público, sem GPS; telefone só se a pessoa quiser) |
| RNF10 | Segurança (CSRF, cookies, cabeçalhos, limite de tentativas) | Feito, com revisão automática de todas as rotas em `tests/test_seguranca.py` |
| RNF11 | Imagens seguras | Feito (conteúdo conferido, EXIF removido, redimensionadas e renomeadas) |
| RNF12 | Rastreabilidade | Feito (registro de login, falhas e redefinição de senha no log; ações da administração no banco) |

## Roadmap

| Iteração | Entregas | Requisitos |
|---|---|---|
| 0 — Fundação ✔ | Estrutura, banco, cadastro, login, painel, termos | RF01–RF03, RF22 |
| 1 — Fluxo de demanda ✔ | Encomendas, lista de encomendas, propostas, aceite e recusa, estados, comparação | RF07–RF10, RF17, RF23, RF24 |
| 2 — Fluxo de oferta ✔ | Anúncios (hoje produtos) com fotos, campos por categoria, busca e filtros, proposta de compra | RF04–RF06, RF16, RF18 |
| 3 — Perfis e região ✔ | Vitrine do produtor, loja com CNPJ, diretórios por região imediata, categorias do que se produz, inspeção sanitária, dados de demonstração | RF02 (parte), RF26, RF27, RF30, RF38 (parte) |
| 4 — Preço por público ✔ | Produto para consumidor, para lojas ou para os dois, com preço de cada um e pedido mínimo; preço mostrado conforme quem acessa; disponibilidade sazonal; busca por região nos anúncios | RF28–RF32 |
| 5 — Comunicação ✔ | Conversas entre produtor, loja e consumidor; tela de notificações; alertas de produto novo na região | RF12–RF14, RF33, RF37 |
| 6 — Contratos ✔ | Contrato de fornecimento com versões, aceite registrado, impressão e "onde comprar" | RF34–RF36 |
| 7 — Confiança e fechamento ✔ | Administração mínima (verificar lojas, ocultar conteúdo), exclusão de conta, recuperação de acesso, acessibilidade e roteiro de demonstração | RF02, RF15, RF19–RF21, RF25, RF38 |

Fora do escopo: pagamento integrado, logística e frete, reputação, chat em tempo real e anúncios de máquinas e insumos.

**Limitações conhecidas (para o texto do trabalho):**

- não há envio de e-mail: o link de nova senha vai para o log do servidor de desenvolvimento;
- o texto dos contratos é um modelo acadêmico e precisa de revisão jurídica antes de uso real;
- a verificação de lojas é manual: não há consulta automática ao cadastro da Receita Federal;
- os campos específicos de cada categoria são mantidos no `seed.sql`, não pela tela de administração;
- falta decidir, com revisão jurídica, que dados do fornecedor a vitrine deve mostrar em vendas ao consumidor (Decreto nº 7.962/2013) e o prazo de guarda das mensagens.

## Equipe

[Nome dos integrantes do grupo]
