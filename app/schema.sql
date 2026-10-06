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
DROP TABLE IF EXISTS anuncio_atributo;
DROP TABLE IF EXISTS foto_anuncio;
DROP TABLE IF EXISTS anuncio;
DROP TABLE IF EXISTS unidade_medida;
DROP TABLE IF EXISTS atributo_categoria;
DROP TABLE IF EXISTS categoria;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS municipio;

CREATE TABLE municipio (
    codigo_ibge INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL,
    uf          TEXT NOT NULL CHECK (length(uf) = 2)
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

CREATE TABLE anuncio (
    id                    INTEGER PRIMARY KEY,
    vendedor_id           INTEGER NOT NULL REFERENCES usuario(id),
    categoria_id          INTEGER NOT NULL REFERENCES categoria(id),
    titulo                TEXT    NOT NULL,
    titulo_busca          TEXT    NOT NULL,
    descricao             TEXT    NOT NULL DEFAULT '',
    preco_centavos        INTEGER CHECK (preco_centavos IS NULL OR preco_centavos > 0),
    unidade_id            INTEGER NOT NULL REFERENCES unidade_medida(id),
    quantidade_disponivel REAL    CHECK (quantidade_disponivel IS NULL OR quantidade_disponivel > 0),
    condicao              TEXT    NOT NULL DEFAULT 'nao_se_aplica' CHECK (condicao IN ('novo', 'usado', 'nao_se_aplica')),
    municipio_id          INTEGER NOT NULL REFERENCES municipio(codigo_ibge),
    status                TEXT    NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo', 'pausado', 'encerrado', 'oculto')),
    criado_em             TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em         TEXT
) STRICT;

CREATE TABLE foto_anuncio (
    id                INTEGER PRIMARY KEY,
    anuncio_id        INTEGER NOT NULL REFERENCES anuncio(id),
    arquivo           TEXT    NOT NULL UNIQUE,
    texto_alternativo TEXT    NOT NULL DEFAULT '',
    ordem             INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE anuncio_atributo (
    anuncio_id  INTEGER NOT NULL REFERENCES anuncio(id),
    atributo_id INTEGER NOT NULL REFERENCES atributo_categoria(id),
    valor       TEXT    NOT NULL,
    PRIMARY KEY (anuncio_id, atributo_id)
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
-- Origem: uma encomenda (autor = vendedor) OU um anúncio (autor = comprador).
CREATE TABLE proposta (
    id                      INTEGER PRIMARY KEY,
    encomenda_id            INTEGER REFERENCES encomenda(id),
    anuncio_id              INTEGER REFERENCES anuncio(id),
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
    CHECK ((encomenda_id IS NULL) <> (anuncio_id IS NULL)),
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
    alvo_tipo      TEXT    NOT NULL CHECK (alvo_tipo IN ('anuncio', 'encomenda', 'proposta', 'mensagem', 'usuario')),
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

-- No máximo uma proposta pendente por comprador em cada anúncio.
CREATE UNIQUE INDEX proposta_pendente_anuncio
    ON proposta (anuncio_id, comprador_id)
    WHERE status = 'pendente' AND anuncio_id IS NOT NULL;

CREATE INDEX idx_anuncio_busca     ON anuncio (status, categoria_id, municipio_id);
CREATE INDEX idx_encomenda_busca   ON encomenda (status, categoria_id, municipio_entrega_id, prazo_limite);
CREATE INDEX idx_proposta_encomenda ON proposta (encomenda_id);
CREATE INDEX idx_proposta_anuncio  ON proposta (anuncio_id);
CREATE INDEX idx_mensagem_proposta ON mensagem (proposta_id, enviada_em);
CREATE INDEX idx_notificacao_usuario ON notificacao (usuario_id, lida_em);
CREATE INDEX idx_municipio_uf      ON municipio (uf, nome);
