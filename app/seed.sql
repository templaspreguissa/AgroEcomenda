-- Dados iniciais: unidades de medida, categorias e atributos por categoria (RF05).
-- Municípios são carregados à parte: flask --app app carregar-municipios <UF>
-- Categorias: só o que se produz no campo (decisão de escopo de outubro de 2026).

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
    (10, 'serv', 'Serviço (preço fechado)'),
    (11, 'dz',   'Dúzia'),
    (12, 'mc',   'Maço'),
    (13, 'cx',   'Caixa'),
    (14, 'bdj',  'Bandeja'),
    (15, 'pct',  'Pacote');

-- Categorias principais
INSERT INTO categoria (id, categoria_pai_id, nome) VALUES
    (1, NULL, 'Produção agrícola'),
    (2, NULL, 'Pecuária'),
    (3, NULL, 'Produtos de origem animal'),
    (4, NULL, 'Processados e artesanais'),
    (5, NULL, 'Serviços rurais');

-- Subcategorias
INSERT INTO categoria (id, categoria_pai_id, nome) VALUES
    (10, 1, 'Grãos e cereais'),
    (11, 1, 'Café'),
    (12, 1, 'Hortaliças e verduras'),
    (13, 1, 'Frutas'),
    (14, 1, 'Raízes e tubérculos'),
    (15, 1, 'Flores, mudas e plantas'),
    (20, 2, 'Bovinos'),
    (21, 2, 'Aves'),
    (22, 2, 'Suínos'),
    (23, 2, 'Ovinos e caprinos'),
    (30, 3, 'Leite'),
    (31, 3, 'Queijos e laticínios'),
    (32, 3, 'Ovos'),
    (33, 3, 'Mel e derivados'),
    (34, 3, 'Carnes e embutidos'),
    (35, 3, 'Pescados'),
    (40, 4, 'Doces e geleias'),
    (41, 4, 'Pães, bolos e biscoitos'),
    (42, 4, 'Conservas e molhos'),
    (43, 4, 'Farinhas, fubá e polvilho'),
    (44, 4, 'Bebidas'),
    (50, 5, 'Pulverização'),
    (51, 5, 'Colheita e plantio'),
    (52, 5, 'Transporte e frete'),
    (53, 5, 'Assistência técnica');

-- Atributos específicos (valem para a categoria principal e suas subcategorias).
-- Origem animal: todo produto de origem animal passa por inspeção prévia (Lei nº 1.283/1950, art. 1º).
-- O tipo de serviço define até onde o produto pode ser vendido (ver app/inspecao.py).
INSERT INTO atributo_categoria (id, categoria_id, nome, tipo, obrigatorio, opcoes) VALUES
    (1,  1, 'Safra',                 'texto',  0, NULL),
    (2,  1, 'Variedade ou tipo',     'texto',  0, NULL),
    (3,  2, 'Raça',                  'texto',  0, NULL),
    (4,  2, 'Idade (meses)',         'numero', 0, NULL),
    (5,  2, 'Sexo',                  'lista',  0, '["Macho","Fêmea","Misto"]'),
    (6,  3, 'Serviço de inspeção',   'lista',  1, '["SIF (federal)","Sisbi-POA","SIE (estadual)","SIM (municipal)","Selo ARTE","Sem registro: venda só para estabelecimento inspecionado"]'),
    (7,  3, 'Número do registro',    'texto',  0, NULL),
    (8,  4, 'Validade (dias)',       'numero', 0, NULL),
    (9,  4, 'Ingredientes principais', 'texto', 0, NULL),
    (10, 5, 'Área atendida (ha)',    'numero', 0, NULL),
    (11, 5, 'Período disponível',    'texto',  0, NULL);
