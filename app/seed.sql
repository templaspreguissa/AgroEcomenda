-- Dados iniciais: unidades de medida, categorias e atributos por categoria (RF05).
-- Municípios são carregados à parte: flask --app app carregar-municipios <UF>

INSERT INTO unidade_medida (id, sigla, nome) VALUES
    (1,  'kg',   'Quilograma'),
    (2,  't',    'Tonelada'),
    (3,  'sc60', 'Saca de 60 kg'),
    (4,  '@',    'Arroba (15 kg)'),
    (5,  'L',    'Litro'),
    (6,  'cab',  'Cabeça'),
    (7,  'un',   'Unidade'),
    (8,  'ha',   'Hectare'),
    (9,  'h',    'Hora'),
    (10, 'serv', 'Serviço (preço fechado)');

-- Categorias principais
INSERT INTO categoria (id, categoria_pai_id, nome) VALUES
    (1, NULL, 'Produção agrícola'),
    (2, NULL, 'Animais'),
    (3, NULL, 'Máquinas e equipamentos'),
    (4, NULL, 'Insumos'),
    (5, NULL, 'Serviços');

-- Subcategorias
INSERT INTO categoria (id, categoria_pai_id, nome) VALUES
    (10, 1, 'Grãos'),
    (11, 1, 'Café'),
    (12, 1, 'Hortaliças e frutas'),
    (13, 1, 'Leite'),
    (20, 2, 'Bovinos'),
    (21, 2, 'Aves'),
    (22, 2, 'Suínos'),
    (23, 2, 'Ovinos e caprinos'),
    (30, 3, 'Tratores'),
    (31, 3, 'Implementos'),
    (32, 3, 'Colheitadeiras'),
    (33, 3, 'Peças'),
    (40, 4, 'Sementes e mudas'),
    (41, 4, 'Fertilizantes e corretivos'),
    (42, 4, 'Nutrição animal'),
    (50, 5, 'Pulverização'),
    (51, 5, 'Colheita e plantio'),
    (52, 5, 'Transporte e frete'),
    (53, 5, 'Assistência técnica');

-- Atributos específicos (valem para a categoria principal e suas subcategorias)
INSERT INTO atributo_categoria (categoria_id, nome, tipo, obrigatorio, opcoes) VALUES
    (1, 'Safra',               'texto',  0, NULL),
    (1, 'Variedade ou tipo',   'texto',  0, NULL),
    (2, 'Raça',                'texto',  0, NULL),
    (2, 'Idade (meses)',       'numero', 0, NULL),
    (2, 'Sexo',                'lista',  0, '["Macho","Fêmea","Misto"]'),
    (3, 'Marca',               'texto',  1, NULL),
    (3, 'Modelo',              'texto',  0, NULL),
    (3, 'Ano de fabricação',   'ano',    0, NULL),
    (3, 'Horas de uso',        'numero', 0, NULL),
    (5, 'Área atendida (ha)',  'numero', 0, NULL),
    (5, 'Período disponível',  'texto',  0, NULL);
