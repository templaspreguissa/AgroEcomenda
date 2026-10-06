"""Inspeção de produtos de origem animal: até onde cada produto pode ser vendido.

Todo produto de origem animal passa por fiscalização prévia (Lei nº 1.283/1950, art. 1º).
Quem fiscaliza define a área de venda (art. 4º, com a redação da Lei nº 7.889/1989):

- SIF, do Ministério da Agricultura: comércio interestadual;
- SIE, da secretaria estadual: comércio intermunicipal, dentro do estado;
- SIM, do município: só dentro do município.

Serviços estaduais e municipais do Sisbi-POA podem vender para outros estados
(Lei nº 8.171/1991, art. 29-A, § 7º, incluído pela Lei nº 14.515/2022). Produto artesanal
com selo ARTE também (Lei nº 1.283/1950, art. 10-A, incluído pela Lei nº 13.680/2018).

O AgroEncomenda não confere o registro. Ele mostra o que o produtor declarou, avisa o comprador
e não deixa enviar proposta de quem está fora da área de venda.
"""
ATRIBUTO_INSPECAO = 6
SEM_REGISTRO = "Sem registro: venda só para estabelecimento inspecionado"

# Área de venda de cada serviço de inspeção.
AREA = {
    "SIF (federal)": "pais",
    "Sisbi-POA": "pais",
    "Selo ARTE": "pais",
    "SIE (estadual)": "uf",
    "SIM (municipal)": "municipio",
    SEM_REGISTRO: "estabelecimento",
}

AVISOS = {
    "pais": "Pode ser vendido em todo o país.",
    "uf": "Inspeção estadual: pode ser vendido só dentro de {uf}.",
    "municipio": "Inspeção municipal: pode ser vendido só dentro de {municipio}/{uf}.",
    "estabelecimento": (
        "Sem registro de inspeção: só pode ser vendido para estabelecimento inspecionado "
        "(por exemplo, leite para laticínio). Não é para o consumidor final."
    ),
}


def area_de_venda(atributos):
    """'pais', 'uf', 'municipio', 'estabelecimento' ou None (produto sem inspeção informada)."""
    for atributo in atributos:
        if atributo["id"] == ATRIBUTO_INSPECAO:
            return AREA.get(atributo["valor"])
    return None


def aviso_inspecao(atributos, municipio, uf):
    """Texto sobre a área de venda, a partir dos atributos salvos do produto (ou None)."""
    area = area_de_venda(atributos)
    return AVISOS[area].format(municipio=municipio, uf=uf) if area else None


def motivo_para_nao_vender(area, produto, comprador, canal):
    """Por que o comprador não pode comprar este produto (ou None se pode).

    `produto` traz municipio_id, municipio_nome e municipio_uf. `comprador` é o município de quem
    compra (codigo_ibge, uf), ou None se a cidade não é conhecida. Nesse caso vale o aviso na página.
    """
    if area == "estabelecimento" and canal != "lojista":
        return "Produto sem registro de inspeção só pode ser vendido para lojas e outros estabelecimentos."
    if comprador is None:
        return None
    if area == "municipio" and comprador["codigo_ibge"] != produto["municipio_id"]:
        return (
            f"Este produto tem inspeção municipal (SIM) e só pode ser vendido dentro de "
            f"{produto['municipio_nome']}/{produto['municipio_uf']}."
        )
    if area == "uf" and comprador["uf"] != produto["municipio_uf"]:
        return f"Este produto tem inspeção estadual (SIE) e só pode ser vendido dentro de {produto['municipio_uf']}."
    return None
