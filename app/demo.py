"""Dados de demonstração, todos fictícios (comando: flask --app app carregar-demo).

Servem para apresentar o trabalho e testar no navegador sem cadastrar tudo à mão.
Use só em ambiente local. Nomes, e-mails (domínio reservado example.com) e CNPJs são inventados;
os CNPJs têm dígitos verificadores válidos, mas o prefixo DEMO deixa claro que não são de empresas reais.
As contas não têm telefone público para não exibir número de alguém de verdade.
"""
from datetime import timedelta

from werkzeug.security import generate_password_hash

from . import servicos
from .auth.routes import METODO_HASH
from .cnpj import digitos_verificadores
from .db import salvar_municipios
from .perfis.dados import salvar_perfil_comercio, salvar_perfil_produtor, verificar_comercio
from .util import agora_utc_texto, hoje

# Senha das contas de demonstração (mesma para todas). Só para uso local.
DEMO_SENHA = "demonstracao do agro na feira"
DOMINIO = "example.com"

UBERABA, SACRAMENTO, CONCEICAO, BELO_HORIZONTE = 3170107, 3156908, 3117306, 3106200
MUNICIPIOS = [
    (UBERABA, "Uberaba", 310055, "Uberaba"),
    (SACRAMENTO, "Sacramento", 310055, "Uberaba"),
    (CONCEICAO, "Conceição das Alagoas", 310055, "Uberaba"),
    (BELO_HORIZONTE, "Belo Horizonte", 310001, "Belo Horizonte"),
]

# Ids do seed.sql
KG, SC60, L, DZ, MACO = 1, 3, 5, 11, 12
GRAOS, CAFE, HORTALICAS, FRUTAS, RAIZES = 10, 11, 12, 13, 14
LEITE, QUEIJOS, OVOS = 30, 31, 32
SAFRA, INSPECAO, REGISTRO = 1, 6, 7


class DemoJaCarregada(Exception):
    pass


def _cnpj(base12):
    return base12 + digitos_verificadores(base12)


def _conta(db, senha_hash, nome, apelido, tipo_pessoa, municipio_id):
    cursor = db.execute(
        "INSERT INTO usuario (nome, email, senha_hash, tipo_pessoa, municipio_id, termos_versao, termos_aceitos_em) "
        "VALUES (?, ?, ?, ?, ?, 'demo', ?)",
        (nome, f"{apelido}.demo@{DOMINIO}", senha_hash, tipo_pessoa, municipio_id, agora_utc_texto()),
    )
    return cursor.lastrowid


def _produtor(db, usuario_id, nome_vitrine, municipio_id, descricao, formas, onde="", organico="nao", registro=""):
    salvar_perfil_produtor(db, usuario_id, {
        "nome_vitrine": nome_vitrine, "descricao": descricao, "municipio_id": municipio_id,
        "vende_retirada": "retirada" in formas, "vende_entrega": "entrega" in formas,
        "vende_feira": "feira" in formas, "vende_envio": "envio" in formas,
        "onde_encontrar": onde, "organico": organico, "organico_registro": registro,
        "telefone_publico": None, "telefone_whatsapp": False,
    })


def _anuncio(db, vendedor_id, municipio_id, titulo, categoria_id, unidade_id, preco_centavos, quantidade,
             descricao="", atributos=None):
    return servicos.criar_anuncio(db, vendedor_id, {
        "titulo": titulo, "categoria_id": categoria_id, "descricao": descricao, "preco_centavos": preco_centavos,
        "unidade_id": unidade_id, "quantidade": quantidade, "municipio_id": municipio_id,
    }, atributos or {}, [])


def _comercio(db, usuario_id, nome, cnpj, tipo, municipio_id, interesses, volume, descricao=""):
    salvar_perfil_comercio(db, usuario_id, {
        "nome_fantasia": nome, "cnpj": cnpj, "tipo": tipo, "descricao": descricao, "municipio_id": municipio_id,
        "volume_compra": volume, "telefone_publico": None, "telefone_whatsapp": False,
    }, interesses)


def carregar_demo(db):
    if db.execute("SELECT 1 FROM usuario WHERE email LIKE ?", (f"%.demo@{DOMINIO}",)).fetchone():
        raise DemoJaCarregada("Os dados de demonstração já foram carregados. Para recomeçar, rode init-db antes.")

    for codigo, nome, regiao_id, regiao_nome in MUNICIPIOS:
        uf = "MG"
        salvar_municipios(uf, [(codigo, nome, regiao_id, regiao_nome)])

    senha_hash = generate_password_hash(DEMO_SENHA, method=METODO_HASH)
    with db:
        ana = _conta(db, senha_hash, "Ana Ribeiro", "ana", "PF", UBERABA)
        carlos = _conta(db, senha_hash, "Carlos Mendes", "carlos", "PJ", SACRAMENTO)
        jose = _conta(db, senha_hash, "José Antunes", "jose", "PF", CONCEICAO)
        rita = _conta(db, senha_hash, "Rita Souza", "rita", "PJ", UBERABA)
        paulo = _conta(db, senha_hash, "Paulo Lima", "paulo", "PJ", SACRAMENTO)
        _conta(db, senha_hash, "Marina Costa", "marina", "PF", UBERABA)

    # Produtores e o que produzem
    _produtor(db, ana, "Sítio Boa Vista", UBERABA,
              "Hortaliças e ovos caipira de produção familiar, colhidos no dia da entrega.",
              {"retirada", "entrega", "feira"}, onde="Feira do Produtor, sábados das 6h às 11h (exemplo fictício).",
              organico="ocs", registro="OCS Produtores do Triângulo (fictícia)")
    _anuncio(db, ana, UBERABA, "Alface crespa", HORTALICAS, MACO, 350, 200, "Colhida no dia. Sem agrotóxico.")
    _anuncio(db, ana, UBERABA, "Tomate italiano", HORTALICAS, KG, 790, 150)
    _anuncio(db, ana, UBERABA, "Ovos caipira", OVOS, DZ, 1400, 80, "Galinhas soltas, ração sem antibiótico.",
             {INSPECAO: "SIM (municipal)", REGISTRO: "SIM 012 (fictício)"})

    _produtor(db, carlos, "Queijaria Serra Azul", SACRAMENTO,
              "Queijo minas artesanal de leite cru, maturado por 22 dias.", {"retirada", "envio"})
    _anuncio(db, carlos, SACRAMENTO, "Queijo minas artesanal", QUEIJOS, KG, 4800, 120,
             atributos={INSPECAO: "Selo ARTE", REGISTRO: "ARTE 0001 (fictício)"})
    _anuncio(db, carlos, SACRAMENTO, "Leite refrigerado para laticínio", LEITE, L, 240, 3000,
             "Tanque de expansão, coleta diária.", {INSPECAO: "Sem registro: venda só para estabelecimento inspecionado"})

    _produtor(db, jose, "Fazenda Santa Clara", CONCEICAO,
              "Café arábica e milho. Entrega com caminhão próprio na região.", {"entrega", "envio"})
    _anuncio(db, jose, CONCEICAO, "Café arábica tipo 6", CAFE, SC60, 145000, 300, atributos={SAFRA: "2026"})
    _anuncio(db, jose, CONCEICAO, "Milho em grão", GRAOS, SC60, 6800, 1000)

    # Comércios
    _comercio(db, rita, "Mercado Bom Preço (fictício)", _cnpj("DEMOMERC0001"), "mercado", UBERABA,
              [HORTALICAS, FRUTAS, OVOS, QUEIJOS], "300 maços de verduras e 60 dúzias de ovos por semana.",
              "Mercado de bairro com seção de hortifrúti.")
    verificar_comercio(db, rita)
    _comercio(db, paulo, "Restaurante Sabor da Roça (fictício)", _cnpj("DEMOREST0001"), "restaurante", SACRAMENTO,
              [QUEIJOS, HORTALICAS, RAIZES], "20 kg de queijo e 40 kg de mandioca por semana.")

    servicos.criar_encomenda(db, rita, {
        "titulo": "Alface crespa toda semana", "categoria_id": HORTALICAS,
        "descricao": "Entregas às segundas, maços padronizados.", "quantidade": 300, "unidade_id": MACO,
        "municipio_id": UBERABA, "prazo_limite": hoje() + timedelta(days=20), "transporte": "vendedor_entrega",
        "condicoes_pagamento": "Boleto 14 dias",
    })

    return (
        "Dados de demonstração carregados: 3 produtores, 2 comércios (1 verificado), 1 consumidor, "
        "7 anúncios e 1 encomenda. E-mails terminam em .demo@example.com. A senha está em app/demo.py."
    )
