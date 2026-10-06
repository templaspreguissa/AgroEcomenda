# AgroEncomenda

Marketplace de negociações no agronegócio. Projeto acadêmico do **Trabalho A3** da disciplina **Projeto e Engenharia de Software**.

O AgroEncomenda tem um **fluxo duplo**:

- **quem vende** publica anúncios de produção, animais, máquinas, insumos e serviços;
- **quem compra** publica encomendas dizendo exatamente o que precisa (produto, quantidade, unidade, município e prazo) e recebe propostas de vendedores.

Comprador e vendedor negociam e trocam mensagens dentro da plataforma, com o status da negociação registrado. A plataforma **não intermedia pagamentos nem faz entregas**.

> **Status:** Iteração 2 concluída. Os dois fluxos funcionam: **anúncios de venda** (com fotos, campos por categoria, busca com filtros de preço e condição, pausar e encerrar, proposta de compra) e **encomendas** (proposta de venda, comparação lado a lado, aceite, recusa e expiração automática). As próximas iterações estão no [roadmap](#roadmap).

## Como funciona o fluxo de oferta

1. O vendedor publica um **anúncio** com até 5 fotos, preço por unidade (ou "a combinar"), quantidade disponível, condição (novo ou usado) e município. Conforme a categoria, aparecem campos específicos: marca, modelo, ano e horas para máquinas; raça, idade e sexo para animais; safra e variedade para a produção agrícola.
2. Compradores encontram o anúncio em **Anúncios** (busca sem acento, filtros por categoria, estado, condição e faixa de preço, ordenação por preço) e fazem uma **proposta de compra** com preço oferecido, quantidade, data de entrega e transporte.
3. O vendedor aceita ou recusa cada proposta. O anúncio continua ativo depois de um aceite, porque o vendedor pode vender para mais de um comprador. Para parar de receber propostas, ele pode **pausar** ou **encerrar** o anúncio.
4. A regra de privacidade é a mesma das encomendas: nome completo e e-mail só aparecem para as duas partes depois do aceite.

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

# 4. (Opcional) Carregar os municípios de uma UF pela API do IBGE
flask --app app carregar-municipios MG

# 5. Rodar em modo de desenvolvimento
flask --app app run --debug
```

Acesse <http://127.0.0.1:5000>. O banco fica em `instance/agroencomenda.db` e as fotos em `instance/uploads/`, ambos fora do Git.

> **Atualizando de uma versão anterior?** Rode `pip install -r requirements-dev.txt` de novo (a Iteração 2 usa a biblioteca Pillow). Se quiser o esquema mais recente do banco, rode `flask --app app init-db`, lembrando que isso apaga os dados de teste.

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
├── schema.sql         # esquema completo do banco (usuário, anúncio, encomenda, proposta, mensagem...)
├── seed.sql           # unidades de medida, categorias e atributos por categoria
├── servicos.py        # regras de negócio: estados de anúncio, encomenda e proposta, sempre em transação
├── fotos.py           # upload seguro: valida o conteúdo, remove EXIF/GPS, redimensiona, renomeia
├── atributos.py       # campos específicos por categoria (RF05)
├── util.py            # reais, quantidades, unidades, datas e busca sem acentos
├── localidades.py     # municípios (código IBGE) para formulários e filtros
├── formularios.py     # base dos formulários (mensagens em português)
├── auth/              # cadastro, login, logout, limite de tentativas, decoradores de acesso
├── anuncios/          # anúncios e propostas de compra: lista, publicar, editar, pausar, encerrar, fotos
├── encomendas/        # encomendas e propostas: lista, publicar, editar, cancelar, propor, aceitar, recusar
├── main/              # página inicial, termos, privacidade, painel
├── templates/         # HTML (Jinja)
└── static/            # CSS e JavaScript
docs/
└── benchmark-marketplaces.md   # análise de interface de OLX, Agrofy, MF Rural, Grão Direto, GetNinjas...
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
- Upload de fotos conforme a OWASP: só JPEG, PNG ou WebP conferidos pelo conteúdo (Pillow), até 8 MB cada e 5 por anúncio, proteção contra imagens gigantes, nome gerado pelo sistema, arquivos fora de `/static`. As fotos são regravadas **sem metadados EXIF** (que podem trazer a localização GPS de onde foram tiradas). Fotos de anúncio oculto pela moderação não podem ser abertas pelo link direto.

Durante o trabalho acadêmico, **use apenas dados fictícios**.

## Requisitos atendidos nesta versão

| Código | Requisito | Situação |
|---|---|---|
| RF01 | Cadastro de usuários | Feito (conta única que compra e vende, papel `admin` separado) |
| RF02 | Login e alteração de dados | Login feito. Recuperação de acesso e edição de perfil nas próximas iterações |
| RF03 | Bloqueio de áreas por perfil | Feito (decoradores `login_obrigatorio` e `admin_obrigatorio`) |
| RF04 | Publicar anúncio com título, descrição, fotos, preço, quantidade, unidade, local e condição | Feito |
| RF05 | Campos específicos por categoria | Feito (máquinas, animais, produção agrícola e serviços) |
| RF06 | Busca e filtros de anúncios | Feito (palavra-chave, categoria, estado, condição, faixa de preço, ordenação) |
| RF07 | Publicar encomenda com produto, quantidade, local e prazo | Feito |
| RF08 | Listar encomendas e enviar proposta | Feito (busca, filtros por categoria e estado, ordenação, paginação) |
| RF09 | Aceitar ou recusar proposta | Feito (com confirmação antes da ação) |
| RF10 | Status da negociação | Feito (estados separados para encomenda e proposta) |
| RF11 | Painel do usuário | Feito (anúncios, encomendas e propostas enviadas) |
| RF13 | Notificação de proposta, aceite e recusa | Notificações já são registradas. A tela de notificações vem na Iteração 3 |
| RF16 | Excluir ou desativar anúncios e encomendas | Feito (anúncio: editar, pausar, reativar, encerrar; encomenda: editar sem propostas, cancelar) |
| RF17 | Encerrar encomendas vencidas | Feito (automático) |
| RF18 | Proposta de compra sobre anúncio | Feito |
| RF22 | Aceite de Termos e Política de Privacidade | Feito |
| RF23 | Comparar propostas lado a lado | Feito |
| RF24 | Editar ou retirar proposta pendente | Feito |
| RNF01 | Interface responsiva | Feito para as telas existentes (a tabela de propostas vira cartões no celular) |
| RNF02 | Senhas com hash adaptativo | Feito |
| RNF05 | Integridade referencial no SQLite | Feito (`PRAGMA foreign_keys = ON` + restrições `CHECK`) |

## Roadmap

| Iteração | Entregas | Requisitos |
|---|---|---|
| 0 — Fundação ✔ | Estrutura, banco, cadastro, login, painel, termos | RF01–RF03, RF22 |
| 1 — Fluxo de demanda ✔ | Encomendas, lista de encomendas, propostas, aceite e recusa, estados, comparação | RF07–RF10, RF17, RF23, RF24 |
| 2 — Fluxo de oferta ✔ | Anúncios com fotos, campos por categoria, busca e filtros, proposta sobre anúncio | RF04–RF06, RF16, RF18 |
| 3 — Comunicação | Mensagens, tela de notificações, painel completo | RF11–RF14 |
| 4 — Administração e confiança | Painel administrativo, denúncias, bloqueio, recuperação de acesso, exclusão de conta | RF02, RF15, RF19–RF21, RF25 |
| 5 — Qualidade | Revisão de segurança e acessibilidade (WCAG 2.2 AA), testes, dados de demonstração | RNF03–RNF12 |

Fora do escopo: pagamento integrado, logística e frete, reputação e chat em tempo real.

## Equipe

[Nome dos integrantes do grupo]
