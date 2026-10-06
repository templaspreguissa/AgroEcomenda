# AgroEncomenda

Plataforma que aproxima **quem produz no campo** de **comércios** (mercados, restaurantes, distribuidores, cooperativas) e do **consumidor final** da mesma região. Projeto acadêmico do **Trabalho A3** da disciplina **Projeto e Engenharia de Software**.

Uma mesma conta pode ter até três papéis:

- **produtor:** cria uma **vitrine** com o que produz, como vende (retirada, entrega, feira) e onde encontrar, e cadastra seus **produtos** com um preço para o consumidor final, um preço para lojas ou os dois;
- **comércio:** cadastra a **loja** com CNPJ e diz o que compra, para ser encontrado pelos produtores da região. Vê os **preços para lojas** e o pedido mínimo, pede cotações e publica **encomendas** do que precisa;
- **consumidor:** encontra produtores e produtos perto de casa, vê o preço de consumidor e faz pedidos.

A plataforma **não vende produtos, não intermedia pagamentos e não faz entregas**. Ela ajuda o produtor a vender mais, os comércios a conhecerem as opções da região e o consumidor a chegar direto a quem produz. A visão completa, as regras de negócio e as fontes estão em [docs/visao-produtor-comercio-consumidor.md](docs/visao-produtor-comercio-consumidor.md).

> **Status:** Iteração 4 concluída: cada **produto** pode ser vendido ao consumidor final, a lojas ou aos dois, com **preço de cada público**, **pedido mínimo** para lojas e opção "preço só para lojas verificadas". O preço mostrado depende de **quem acessa**, e quem não pode ver um preço não o recebe nem pelos filtros. Também entraram a **safra** (meses do ano), a **busca por região** em produtos e encomendas e a regra de **inspeção** que limita para quem cada produto pode ser vendido. Antes disso: vitrines, lojas com CNPJ, diretórios por região e encomendas com propostas. Próximo passo: conversas e notificações ([roadmap](#roadmap)).

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

# 5. (Opcional) Carregar dados de demonstração fictícios: 3 produtores, 2 lojas, 1 consumidor
flask --app app carregar-demo

# 6. Rodar em modo de desenvolvimento
flask --app app run --debug
```

Acesse <http://127.0.0.1:5000>. O banco fica em `instance/agroencomenda.db` e as fotos em `instance/uploads/`, ambos fora do Git.

As contas de demonstração usam e-mails terminados em `.demo@example.com` (por exemplo, `ana.demo@example.com` é produtora e `rita.demo@example.com` tem uma loja verificada). A senha, igual para todas, está em `app/demo.py`. Use só no computador local.

Para marcar uma loja como verificada depois de conferir o CNPJ na Receita Federal (enquanto não existe a tela de administração):

```powershell
flask --app app verificar-comercio <id da conta>
```

> **Atualizando de uma versão anterior?** O banco mudou nas Iterações 3 (regiões, vitrines e lojas) e 4 (a tabela `anuncio` virou `produto`, com dois preços). Rode `flask --app app init-db` e depois `flask --app app carregar-municipios MG` de novo, lembrando que `init-db` apaga os dados de teste. Se vier da Iteração 1, rode também `pip install -r requirements-dev.txt` (a Iteração 2 passou a usar a biblioteca Pillow).

No Linux ou macOS, troque `py -3` por `python3` e ative o ambiente com `source .venv/bin/activate`.

### Rodar os testes

```powershell
pytest
```

### Fora do modo de desenvolvimento

Sem a variável `FLASK_SECRET_KEY`, a aplicação usa uma chave temporária e as sessões caem a cada reinício. Para publicar, gere uma chave e defina a variável de ambiente antes de iniciar:

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
├── servicos/          # regras de negócio, sempre em transação: comum, encomendas e produtos
├── visibilidade.py    # quem vê quais produtos e quais preços (modo consumidor ou loja)
├── fotos.py           # upload seguro: valida o conteúdo, remove EXIF/GPS, redimensiona, renomeia
├── atributos.py       # campos específicos por categoria (RF05)
├── inspecao.py        # serviço de inspeção de produtos de origem animal e área de venda permitida
├── cnpj.py            # validação de CNPJ numérico e alfanumérico (Receita Federal, julho de 2026)
├── util.py            # reais, quantidades, unidades, telefones, datas e busca sem acentos
├── localidades.py     # municípios e regiões imediatas do IBGE, ordenação por proximidade
├── formularios.py     # base dos formulários (mensagens em português)
├── comandos.py        # comandos verificar-comercio e carregar-demo
├── demo.py            # dados de demonstração fictícios
├── auth/              # cadastro (com "como vai usar"), login, logout, limite de tentativas, decoradores
├── perfis/            # vitrine do produtor, loja (comércio), diretórios por região, dados da conta
├── produtos/          # produtos e propostas de compra: lista, cadastrar, editar, pausar, encerrar, fotos
├── encomendas/        # encomendas e propostas: lista, publicar, editar, cancelar, propor, aceitar, recusar
├── main/              # página inicial, termos, privacidade, painel
├── templates/         # HTML (Jinja)
└── static/            # CSS e JavaScript
docs/
├── benchmark-marketplaces.md            # análise de interface de OLX, Agrofy, MF Rural, Grão Direto, GetNinjas...
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
- Upload de fotos conforme a OWASP: só JPEG, PNG ou WebP conferidos pelo conteúdo (Pillow), até 8 MB cada e 5 por produto, proteção contra imagens gigantes, nome gerado pelo sistema, arquivos fora de `/static`. As fotos são regravadas **sem metadados EXIF** (que podem trazer a localização GPS de onde foram tiradas). Fotos de produto ou vitrine oculta pela moderação não podem ser abertas pelo link direto.

Durante o trabalho acadêmico, **use apenas dados fictícios**.

## Requisitos atendidos nesta versão

| Código | Requisito | Situação |
|---|---|---|
| RF01 | Cadastro de usuários | Feito (conta única que compra e vende, papel `admin` separado) |
| RF02 | Login e alteração de dados | Login e edição de nome, tipo de conta e município feitos. Recuperação de acesso na Iteração 7 |
| RF03 | Bloqueio de áreas por perfil | Feito (decoradores `login_obrigatorio` e `admin_obrigatorio`) |
| RF04 | Cadastrar produto com título, descrição, fotos, preço, quantidade, unidade e local | Feito (exige vitrine de produtor) |
| RF05 | Campos específicos por categoria | Feito (produção agrícola, pecuária, origem animal com inspeção, processados e serviços rurais) |
| RF06 | Busca e filtros de produtos | Feito (palavra-chave, categoria, estado, faixa de preço, região, safra, ordenação) |
| RF07 | Publicar encomenda com produto, quantidade, local e prazo | Feito |
| RF08 | Listar encomendas e enviar proposta | Feito (busca, filtros por categoria e estado, ordenação, paginação) |
| RF09 | Aceitar ou recusar proposta | Feito (com confirmação antes da ação) |
| RF10 | Status da negociação | Feito (estados separados para encomenda e proposta) |
| RF11 | Painel do usuário | Feito (vitrine, loja, produtos com os dois preços, encomendas e propostas enviadas) |
| RF13 | Notificação de proposta, aceite e recusa | Notificações já são registradas. A tela de notificações vem na Iteração 5 |
| RF16 | Excluir ou desativar produtos e encomendas | Feito (produto: editar, pausar, reativar, encerrar; encomenda: editar sem propostas, cancelar) |
| RF17 | Encerrar encomendas vencidas | Feito (automático) |
| RF18 | Proposta de compra sobre produto | Feito |
| RF22 | Aceite de Termos e Política de Privacidade | Feito |
| RF23 | Comparar propostas lado a lado | Feito |
| RF24 | Editar ou retirar proposta pendente | Feito |
| RF26 | Vitrine do produtor | Feito (formas de venda, onde encontrar, orgânico declarado, foto, telefone opcional) |
| RF27 | Perfil de comércio com CNPJ e diretório para produtores | Feito |
| RF28 | Produto para consumidor, para lojas ou para os dois, com preço de cada público | Feito (com pedido mínimo e "só verificadas") |
| RF29 | Preço mostrado conforme quem acessa | Feito (inclusive "Ver como consumidor" para quem tem loja) |
| RF30 | Busca por região (região imediata do IBGE) | Feito em produtos, encomendas, produtores e comércios |
| RF31 | Pedido do consumidor e cotação da loja | Feito (canal decidido no servidor, pedido mínimo) |
| RF32 | Safra e "o que tem neste mês" | Feito |
| RF38 | Verificação de comércio | Feito pelo comando `verificar-comercio`. Tela de administração na Iteração 7 |
| RNF01 | Interface responsiva | Feito para as telas existentes (a tabela de propostas vira cartões no celular) |
| RNF02 | Senhas com hash adaptativo | Feito |
| RNF05 | Integridade referencial no SQLite | Feito (`PRAGMA foreign_keys = ON` + restrições `CHECK`) |

## Roadmap

| Iteração | Entregas | Requisitos |
|---|---|---|
| 0 — Fundação ✔ | Estrutura, banco, cadastro, login, painel, termos | RF01–RF03, RF22 |
| 1 — Fluxo de demanda ✔ | Encomendas, lista de encomendas, propostas, aceite e recusa, estados, comparação | RF07–RF10, RF17, RF23, RF24 |
| 2 — Fluxo de oferta ✔ | Anúncios (hoje produtos) com fotos, campos por categoria, busca e filtros, proposta de compra | RF04–RF06, RF16, RF18 |
| 3 — Perfis e região ✔ | Vitrine do produtor, loja com CNPJ, diretórios por região imediata, categorias do que se produz, inspeção sanitária, dados de demonstração | RF02 (parte), RF26, RF27, RF30, RF38 (parte) |
| 4 — Preço por público ✔ | Produto para consumidor, para lojas ou para os dois, com preço de cada um e pedido mínimo; preço mostrado conforme quem acessa; disponibilidade sazonal; busca por região nos anúncios | RF28–RF32 |
| 5 — Comunicação | Conversas entre produtor, loja e consumidor; tela de notificações; alertas de produto novo na região | RF12–RF14, RF33, RF37 |
| 6 — Contratos | Contrato de fornecimento com versões, aceite registrado, impressão e "onde comprar" | RF34–RF36 |
| 7 — Confiança e fechamento | Administração mínima (verificar lojas, ocultar conteúdo), exclusão de conta, recuperação de acesso, acessibilidade e roteiro de demonstração | RF02, RF15, RF19–RF21, RF25, RF38 |

Fora do escopo: pagamento integrado, logística e frete, reputação, chat em tempo real e anúncios de máquinas e insumos.

## Equipe

[Nome dos integrantes do grupo]
