-- AgroEncomenda: esquema do banco (SQLite 3.37+ por causa das tabelas STRICT).
-- Baseado na seção 9.4.4 da pesquisa do projeto.
-- Datas em texto ISO 8601 (UTC). Dinheiro em centavos (INTEGER).

DROP TABLE IF EXISTS bloqueio_login;
DROP TABLE IF EXISTS acao_moderacao;
DROP TABLE IF EXISTS denuncia;
DROP TABLE IF EXISTS notificacao;
DROP TABLE IF EXISTS mensagem;
DROP TABLE IF EXISTS proposta;
DROP TABLE IF EXISTS encomenda_atributo;
DROP TABLE IF EXISTS encomenda;
DROP TABLE IF EXISTS produto_atributo;
DROP TABLE IF EXISTS foto_produto;
DROP TABLE IF EXISTS produto;
DROP TABLE IF EXISTS comercio_interesse;
DROP TABLE IF EXISTS perfil_comercio;
DROP TABLE IF EXISTS perfil_produtor;
DROP TABLE IF EXISTS unidade_medida;
DROP TABLE IF EXISTS atributo_categoria;
DROP TABLE IF EXISTS categoria;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS municipio;
DROP TABLE IF EXISTS regiao_imediata;

-- Região Geográfica Imediata do IBGE (2017): cidades próximas onde a população
-- busca bens e serviços. É o recorte de "minha região" nas buscas.
CREATE TABLE regiao_imediata (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    uf   TEXT NOT NULL CHECK (length(uf) = 2)
) STRICT;

CREATE TABLE municipio (
    codigo_ibge        INTEGER PRIMARY KEY,
    nome               TEXT    NOT NULL,
    uf                 TEXT    NOT NULL CHECK (length(uf) = 2),
    regiao_imediata_id INTEGER REFERENCES regiao_imediata(id)
) STRICT;

CREATE TABLE usuario (
    id                INTEGER PRIMARY KEY,
    nome              TEXT    NOT NULL,
    email             TEXT    NOT NULL UNIQUE,
    senha_hash        TEXT    NOT NULL,
    papel             TEXT    NOT NULL DEFAULT 'usuario' CHECK (papel IN ('usuario', 'admin')),
    tipo_pessoa       TEXT    NOT NULL CHECK (tipo_pessoa IN ('PF', 'PJ')),
    telefone          TEXT,
    municipio_id      INTEGER REFERENCES municipio(codigo_ibge),
    status            TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'bloqueado', 'excluido')),
    termos_versao     TEXT    NOT NULL,
    termos_aceitos_em TEXT    NOT NULL,
    criado_em         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     TEXT
) STRICT;

CREATE TABLE categoria (
    id               INTEGER PRIMARY KEY,
    categoria_pai_id INTEGER REFERENCES categoria(id),
    nome             TEXT    NOT NULL,
    ativa            INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1))
) STRICT;

CREATE TABLE atributo_categoria (
    id           INTEGER PRIMARY KEY,
    categoria_id INTEGER NOT NULL REFERENCES categoria(id),
    nome         TEXT    NOT NULL,
    tipo         TEXT    NOT NULL CHECK (tipo IN ('texto', 'numero', 'ano', 'lista')),
    obrigatorio  INTEGER NOT NULL DEFAULT 0 CHECK (obrigatorio IN (0, 1)),
    opcoes       TEXT
) STRICT;

CREATE TABLE unidade_medida (
    id    INTEGER PRIMARY KEY,
    sigla TEXT NOT NULL UNIQUE,
    nome  TEXT NOT NULL
) STRICT;

-- Perfil de produtor: a vitrine pública de quem produz (exigido para cadastrar produtos).
CREATE TABLE perfil_produtor (
    usuario_id        INTEGER PRIMARY KEY REFERENCES usuario(id),
    nome_vitrine      TEXT    NOT NULL,
    nome_busca        TEXT    NOT NULL,
    descricao         TEXT    NOT NULL DEFAULT '',
    municipio_id      INTEGER NOT NULL REFERENCES municipio(codigo_ibge),
    vende_retirada    INTEGER NOT NULL DEFAULT 0 CHECK (vende_retirada IN (0, 1)),
    vende_entrega     INTEGER NOT NULL DEFAULT 0 CHECK (vende_entrega IN (0, 1)),
    vende_feira       INTEGER NOT NULL DEFAULT 0 CHECK (vende_feira IN (0, 1)),
    vende_envio       INTEGER NOT NULL DEFAULT 0 CHECK (vende_envio IN (0, 1)),
    onde_encontrar    TEXT    NOT NULL DEFAULT '',
    organico          TEXT    NOT NULL DEFAULT 'nao' CHECK (organico IN ('nao', 'certificado', 'ocs')),
    organico_registro TEXT    NOT NULL DEFAULT '',
    telefone_publico  TEXT    CHECK (telefone_publico IS NULL OR length(telefone_publico) IN (10, 11)),
    telefone_whatsapp INTEGER NOT NULL DEFAULT 0 CHECK (telefone_whatsapp IN (0, 1)),
    foto              TEXT    UNIQUE,
    status            TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'oculto')),
    criado_em         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     TEXT,
    CHECK (vende_retirada + vende_entrega + vende_feira + vende_envio >= 1)
) STRICT;

-- Perfil de comércio: loja, restaurante, distribuidor... Com CNPJ válido, vê preços para lojas.
CREATE TABLE perfil_comercio (
    usuario_id        INTEGER PRIMARY KEY REFERENCES usuario(id),
    nome_fantasia     TEXT    NOT NULL,
    nome_busca        TEXT    NOT NULL,
    cnpj              TEXT    NOT NULL UNIQUE CHECK (length(cnpj) = 14),
    tipo              TEXT    NOT NULL CHECK (tipo IN ('mercado', 'hortifruti', 'restaurante', 'padaria',
                                                       'distribuidor', 'cooperativa', 'agroindustria',
                                                       'emporio', 'outro')),
    descricao         TEXT    NOT NULL DEFAULT '',
    municipio_id      INTEGER NOT NULL REFERENCES municipio(codigo_ibge),
    volume_compra     TEXT    NOT NULL DEFAULT '',
    telefone_publico  TEXT    CHECK (telefone_publico IS NULL OR length(telefone_publico) IN (10, 11)),
    telefone_whatsapp INTEGER NOT NULL DEFAULT 0 CHECK (telefone_whatsapp IN (0, 1)),
    verificado_em     TEXT,
    verificado_por    INTEGER REFERENCES usuario(id),
    status            TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'oculto')),
    criado_em         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em     TEXT
) STRICT;

-- O que o comércio costuma comprar (categorias), para os produtores o encontrarem.
CREATE TABLE comercio_interesse (
    usuario_id   INTEGER NOT NULL REFERENCES perfil_comercio(usuario_id),
    categoria_id INTEGER NOT NULL REFERENCES categoria(id),
    PRIMARY KEY (usuario_id, categoria_id)
) STRICT;

-- Produto do catálogo do produtor. Pode ser oferecido ao consumidor final, a lojas ou aos dois,
-- com um preço para cada público (RF28). Preço nulo = "a combinar".
CREATE TABLE produto (
    id                        INTEGER PRIMARY KEY,
    vendedor_id               INTEGER NOT NULL REFERENCES usuario(id),
    categoria_id              INTEGER NOT NULL REFERENCES categoria(id),
    titulo                    TEXT    NOT NULL,
    titulo_busca              TEXT    NOT NULL,
    descricao                 TEXT    NOT NULL DEFAULT '',
    unidade_id                INTEGER NOT NULL REFERENCES unidade_medida(id),
    quantidade_disponivel     REAL    CHECK (quantidade_disponivel IS NULL OR quantidade_disponivel > 0),
    para_consumidor           INTEGER NOT NULL DEFAULT 1 CHECK (para_consumidor IN (0, 1)),
    para_lojista              INTEGER NOT NULL DEFAULT 0 CHECK (para_lojista IN (0, 1)),
    preco_consumidor_centavos INTEGER CHECK (preco_consumidor_centavos IS NULL OR preco_consumidor_centavos > 0),
    preco_lojista_centavos    INTEGER CHECK (preco_lojista_centavos IS NULL OR preco_lojista_centavos > 0),
    pedido_minimo_lojista     REAL    CHECK (pedido_minimo_lojista IS NULL OR pedido_minimo_lojista > 0),
    so_verificados            INTEGER NOT NULL DEFAULT 0 CHECK (so_verificados IN (0, 1)),
    disponibilidade           TEXT    NOT NULL DEFAULT 'ano_todo'
                              CHECK (disponibilidade IN ('ano_todo', 'safra', 'sob_encomenda')),
    meses_safra               INTEGER NOT NULL DEFAULT 0 CHECK (meses_safra BETWEEN 0 AND 4095),  -- bit 0 = janeiro
    municipio_id              INTEGER NOT NULL REFERENCES municipio(codigo_ibge),
    status                    TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'pausado', 'encerrado', 'oculto')),
    criado_em                 TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em             TEXT,
    CHECK (para_consumidor + para_lojista >= 1),
    CHECK (para_consumidor = 1 OR preco_consumidor_centavos IS NULL),
    CHECK (para_lojista = 1 OR (preco_lojista_centavos IS NULL AND pedido_minimo_lojista IS NULL AND so_verificados = 0)),
    CHECK (disponibilidade = 'safra' OR meses_safra = 0),
    CHECK (disponibilidade <> 'safra' OR meses_safra > 0)
) STRICT;

CREATE TABLE foto_produto (
    id                INTEGER PRIMARY KEY,
    produto_id        INTEGER NOT NULL REFERENCES produto(id),
    arquivo           TEXT    NOT NULL UNIQUE,
    texto_alternativo TEXT    NOT NULL DEFAULT '',
    ordem             INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE produto_atributo (
    produto_id  INTEGER NOT NULL REFERENCES produto(id),
    atributo_id INTEGER NOT NULL REFERENCES atributo_categoria(id),
    valor       TEXT    NOT NULL,
    PRIMARY KEY (produto_id, atributo_id)
) STRICT;

CREATE TABLE encomenda (
    id                   INTEGER PRIMARY KEY,
    comprador_id         INTEGER NOT NULL REFERENCES usuario(id),
    categoria_id         INTEGER NOT NULL REFERENCES categoria(id),
    titulo               TEXT    NOT NULL,
    titulo_busca         TEXT    NOT NULL,
    descricao            TEXT    NOT NULL DEFAULT '',
    quantidade           REAL    NOT NULL CHECK (quantidade > 0),
    unidade_id           INTEGER NOT NULL REFERENCES unidade_medida(id),
    municipio_entrega_id INTEGER NOT NULL REFERENCES municipio(codigo_ibge),
    prazo_limite         TEXT    NOT NULL,
    transporte           TEXT    NOT NULL CHECK (transporte IN ('comprador_retira', 'vendedor_entrega', 'a_combinar')),
    condicoes_pagamento  TEXT    NOT NULL DEFAULT '',
    status               TEXT    NOT NULL DEFAULT 'aberta'
                         CHECK (status IN ('aberta', 'em_negociacao', 'concluida', 'cancelada', 'expirada')),
    criado_em            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    encerrada_em         TEXT
) STRICT;

CREATE TABLE encomenda_atributo (
    encomenda_id INTEGER NOT NULL REFERENCES encomenda(id),
    atributo_id  INTEGER NOT NULL REFERENCES atributo_categoria(id),
    valor        TEXT    NOT NULL,
    PRIMARY KEY (encomenda_id, atributo_id)
) STRICT;

-- Uma proposta é uma negociação entre comprador e vendedor.
-- Origem: uma encomenda (autor = vendedor) OU um produto (autor = comprador).
-- Em produto, o canal diz se a compra é como consumidor final ou como loja (RF31).
CREATE TABLE proposta (
    id                      INTEGER PRIMARY KEY,
    encomenda_id            INTEGER REFERENCES encomenda(id),
    produto_id              INTEGER REFERENCES produto(id),
    canal                   TEXT    CHECK (canal IS NULL OR canal IN ('consumidor', 'lojista')),
    comprador_id            INTEGER NOT NULL REFERENCES usuario(id),
    vendedor_id             INTEGER NOT NULL REFERENCES usuario(id),
    autor_id                INTEGER NOT NULL REFERENCES usuario(id),
    preco_unitario_centavos INTEGER NOT NULL CHECK (preco_unitario_centavos > 0),
    unidade_id              INTEGER NOT NULL REFERENCES unidade_medida(id),
    quantidade              REAL    NOT NULL CHECK (quantidade > 0),
    prazo_entrega           TEXT    NOT NULL,
    transporte              TEXT    NOT NULL CHECK (transporte IN ('comprador_retira', 'vendedor_entrega', 'a_combinar')),
    validade                TEXT,
    observacao              TEXT,
    status                  TEXT    NOT NULL DEFAULT 'pendente'
                            CHECK (status IN ('pendente', 'aceita', 'recusada', 'retirada',
                                              'nao_selecionada', 'concluida', 'cancelada')),
    criado_em               TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    respondida_em           TEXT,
    CHECK ((encomenda_id IS NULL) <> (produto_id IS NULL)),
    CHECK ((produto_id IS NULL) = (canal IS NULL)),
    CHECK (comprador_id <> vendedor_id),
    CHECK (autor_id IN (comprador_id, vendedor_id))
) STRICT;

CREATE TABLE mensagem (
    id           INTEGER PRIMARY KEY,
    proposta_id  INTEGER NOT NULL REFERENCES proposta(id),
    remetente_id INTEGER NOT NULL REFERENCES usuario(id),
    conteudo     TEXT    NOT NULL CHECK (length(conteudo) BETWEEN 1 AND 2000),
    enviada_em   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lida_em      TEXT
) STRICT;

CREATE TABLE notificacao (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo       TEXT    NOT NULL CHECK (tipo IN ('nova_proposta', 'proposta_aceita', 'proposta_recusada',
                                               'nova_mensagem', 'encomenda_expirada', 'conteudo_moderado')),
    texto      TEXT    NOT NULL,
    link       TEXT    NOT NULL,
    criada_em  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lida_em    TEXT
) STRICT;

CREATE TABLE denuncia (
    id             INTEGER PRIMARY KEY,
    denunciante_id INTEGER NOT NULL REFERENCES usuario(id),
    alvo_tipo      TEXT    NOT NULL CHECK (alvo_tipo IN ('produto', 'encomenda', 'proposta', 'mensagem', 'usuario', 'vitrine', 'loja')),
    alvo_id        INTEGER NOT NULL,
    motivo         TEXT    NOT NULL,
    descricao      TEXT    NOT NULL DEFAULT '',
    status         TEXT    NOT NULL DEFAULT 'aberta' CHECK (status IN ('aberta', 'em_analise', 'procedente', 'improcedente')),
    moderador_id   INTEGER REFERENCES usuario(id),
    criada_em      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolvida_em   TEXT
) STRICT;

CREATE TABLE acao_moderacao (
    id        INTEGER PRIMARY KEY,
    admin_id  INTEGER NOT NULL REFERENCES usuario(id),
    alvo_tipo TEXT    NOT NULL,
    alvo_id   INTEGER NOT NULL,
    acao      TEXT    NOT NULL CHECK (acao IN ('ocultar', 'reativar', 'bloquear_usuario', 'desbloquear_usuario')),
    motivo    TEXT    NOT NULL,
    criada_em TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT;

-- Limite de tentativas de login por e-mail (NIST SP 800-63B-4: rate limiting).
CREATE TABLE bloqueio_login (
    email        TEXT    PRIMARY KEY,
    falhas       INTEGER NOT NULL DEFAULT 0,
    ultima_falha TEXT    NOT NULL
) STRICT;

-- No máximo uma proposta pendente por vendedor em cada encomenda.
CREATE UNIQUE INDEX proposta_pendente_unica
    ON proposta (encomenda_id, vendedor_id)
    WHERE status = 'pendente' AND encomenda_id IS NOT NULL;

-- No máximo uma proposta pendente por comprador em cada produto.
CREATE UNIQUE INDEX proposta_pendente_produto
    ON proposta (produto_id, comprador_id)
    WHERE status = 'pendente' AND produto_id IS NOT NULL;

CREATE INDEX idx_produto_busca     ON produto (status, categoria_id, municipio_id);
CREATE INDEX idx_produto_vendedor  ON produto (vendedor_id, status);
CREATE INDEX idx_encomenda_busca   ON encomenda (status, categoria_id, municipio_entrega_id, prazo_limite);
CREATE INDEX idx_proposta_encomenda ON proposta (encomenda_id);
CREATE INDEX idx_proposta_produto  ON proposta (produto_id);
CREATE INDEX idx_mensagem_proposta ON mensagem (proposta_id, enviada_em);
CREATE INDEX idx_notificacao_usuario ON notificacao (usuario_id, lida_em);
CREATE INDEX idx_municipio_uf      ON municipio (uf, nome);
CREATE INDEX idx_municipio_regiao  ON municipio (regiao_imediata_id);
CREATE INDEX idx_produtor_municipio ON perfil_produtor (municipio_id);
CREATE INDEX idx_comercio_municipio ON perfil_comercio (municipio_id);
