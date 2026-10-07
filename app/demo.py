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
KG, SC60, L, DZ, MACO, BANDEJA, PACOTE = 1, 3, 5, 11, 12, 14, 15
GRAOS, CAFE, HORTALICAS, FRUTAS, RAIZES = 10, 11, 12, 13, 14
LEITE, QUEIJOS, OVOS = 30, 31, 32
FARINHAS_BEBIDAS = 44
SAFRA, INSPECAO, REGISTRO = 1, 6, 7
JUNHO_A_OUTUBRO = sum(1 << (mes - 1) for mes in range(6, 11))


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


def _produto(db, vendedor_id, municipio_id, titulo, categoria_id, unidade_id, quantidade, consumidor=None,
             loja=None, minimo=None, so_verificados=False, descricao="", atributos=None, meses_safra=0):
    """`consumidor` e `loja` são os preços em centavos; None = não vende para esse público."""
    return servicos.criar_produto(db, vendedor_id, {
        "titulo": titulo, "categoria_id": categoria_id, "descricao": descricao, "unidade_id": unidade_id,
        "quantidade_disponivel": quantidade, "municipio_id": municipio_id,
        "para_consumidor": consumidor is not None, "preco_consumidor_centavos": consumidor,
        "para_lojista": loja is not None, "preco_lojista_centavos": loja, "pedido_minimo_lojista": minimo,
        "so_verificados": so_verificados,
        "disponibilidade": "safra" if meses_safra else "ano_todo", "meses_safra": meses_safra,
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
        marina = _conta(db, senha_hash, "Marina Costa", "marina", "PF", UBERABA)
        admin = _conta(db, senha_hash, "Equipe AgroEncomenda", "admin", "PJ", UBERABA)
        db.execute("UPDATE usuario SET papel = 'admin' WHERE id = ?", (admin,))

    # Produtores e o que produzem
    _produtor(db, ana, "Sítio Boa Vista", UBERABA,
              "Hortaliças e ovos caipira de produção familiar, colhidos no dia da entrega.",
              {"retirada", "entrega", "feira"}, onde="Feira do Produtor, sábados das 6h às 11h (exemplo fictício).",
              organico="ocs", registro="OCS Produtores do Triângulo (fictícia)")
    _produto(db, ana, UBERABA, "Alface crespa", HORTALICAS, MACO, 200, consumidor=350, loja=240, minimo=50,
             descricao="Colhida no dia. Sem agrotóxico.")
    _produto(db, ana, UBERABA, "Tomate italiano", HORTALICAS, KG, 150, consumidor=790, loja=550, minimo=20)
    _produto(db, ana, UBERABA, "Ovos caipira", OVOS, DZ, 80, consumidor=1400, loja=1050, minimo=10, so_verificados=True,
             descricao="Galinhas soltas, ração sem antibiótico.",
             atributos={INSPECAO: "SIM (municipal)", REGISTRO: "SIM 012 (fictício)"})
    _produto(db, ana, UBERABA, "Morango", FRUTAS, BANDEJA, 60, consumidor=1200, meses_safra=JUNHO_A_OUTUBRO)

    _produtor(db, carlos, "Queijaria Serra Azul", SACRAMENTO,
              "Queijo minas artesanal de leite cru, maturado por 22 dias.", {"retirada", "envio"})
    _produto(db, carlos, SACRAMENTO, "Queijo minas artesanal", QUEIJOS, KG, 120, consumidor=4800, loja=3600, minimo=5,
             atributos={INSPECAO: "Selo ARTE", REGISTRO: "ARTE 0001 (fictício)"})
    _produto(db, carlos, SACRAMENTO, "Leite refrigerado para laticínio", LEITE, L, 3000, loja=240, minimo=500,
             descricao="Tanque de expansão, coleta diária.",
             atributos={INSPECAO: "Sem registro: venda só para estabelecimento inspecionado"})

    _produtor(db, jose, "Fazenda Santa Clara", CONCEICAO,
              "Café arábica e milho. Entrega com caminhão próprio na região.", {"entrega", "envio"})
    _produto(db, jose, CONCEICAO, "Café arábica tipo 6", CAFE, SC60, 300, loja=145000, minimo=10, atributos={SAFRA: "2026"})
    _produto(db, jose, CONCEICAO, "Café torrado e moído 500 g", FARINHAS_BEBIDAS, PACOTE, 400, consumidor=3200, loja=2400,
             minimo=20)
    _produto(db, jose, CONCEICAO, "Milho em grão", GRAOS, SC60, 1000, loja=6800, minimo=50)

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

    # Uma conversa de exemplo: a loja pergunta à produtora sobre a alface.
    alface = db.execute("SELECT id FROM produto WHERE vendedor_id = ? AND titulo = 'Alface crespa'", (ana,)).fetchone()["id"]
    loja = {"id": rita, "nome": "Rita Souza", "tem_produtor": False}
    conversa_id = servicos.conversas.iniciar_conversa(
        db, "produto", alface, loja, "Bom dia! Vocês conseguem entregar 300 maços por semana em Uberaba, às segundas?"
    )
    servicos.conversas.responder(
        db, servicos.conversas.buscar_conversa(db, conversa_id, ana), ana,
        "Bom dia, Rita! Conseguimos, sim. Mande o pedido de cotação pelo produto que eu confirmo o preço.",
    )

    # Um contrato de fornecimento ativo, com a parceria pública autorizada pelas duas partes.
    contratos = servicos.contratos
    contrato_id = contratos.criar_contrato(db, ana, ana, rita, {
        "inicio": hoje().isoformat(), "termino": (hoje() + timedelta(days=182)).isoformat(),
        "frequencia": "semanal", "dia_entrega": "segundas-feiras, até as 10h", "transporte": "vendedor_entrega",
        "municipio_entrega_id": UBERABA, "local_entrega": "Doca de recebimento do mercado (exemplo fictício)",
        "condicoes_pagamento": "Boleto 14 dias após cada entrega", "padrao_qualidade": "Maços de 300 g, folhas inteiras",
        "reajuste": "Revisão de preço a cada 3 meses, de comum acordo", "aviso_previo_dias": 30, "observacoes": "",
    }, [{"produto_id": alface, "descricao": "Alface crespa", "quantidade": 300, "unidade_id": MACO, "preco_centavos": 230}])
    contratos.enviar_contrato(db, contratos.buscar_contrato(db, contrato_id, ana), ana)
    contrato = contratos.buscar_contrato(db, contrato_id, rita)
    contratos.aceitar_contrato(db, contrato, rita, contratos.versao_atual(db, contrato)["hash"])
    contrato = contratos.buscar_contrato(db, contrato_id, ana)
    contratos.alterar_parceria(db, contrato, ana, True)
    contratos.alterar_parceria(db, contrato, rita, True)

    # Uma denúncia aberta, para mostrar a fila da moderação.
    tomate = db.execute("SELECT id FROM produto WHERE vendedor_id = ? AND titulo = 'Tomate italiano'", (ana,)).fetchone()["id"]
    servicos.moderacao.denunciar(db, marina, "produto", tomate, "falso",
                                 "O preço na feira estava diferente do anunciado (exemplo fictício).")

    return (
        "Dados de demonstração carregados: 3 produtores, 2 comércios (1 verificado), 1 consumidor, 1 administração, "
        "9 produtos, 1 encomenda, 1 conversa, 1 contrato ativo e 1 denúncia. E-mails terminam em .demo@example.com. "
        "A senha está em app/demo.py."
    )
