"""Inspeção de produtos de origem animal: até onde cada produto pode ser vendido.

Todo produto de origem animal passa por fiscalização prévia (Lei nº 1.283/1950, art. 1º).
Quem fiscaliza define a área de venda (art. 4º, com a redação da Lei nº 7.889/1989):

- SIF, do Ministério da Agricultura: comércio interestadual;
- SIE, da secretaria estadual: comércio intermunicipal, dentro do estado;
- SIM, do município: só dentro do município.

Serviços estaduais e municipais do Sisbi-POA podem vender para outros estados
(Lei nº 8.171/1991, art. 29-A, § 7º, incluído pela Lei nº 14.515/2022). Produto artesanal
com selo ARTE também (Lei nº 1.283/1950, art. 10-A, incluído pela Lei nº 13.680/2018).

O AgroEncomenda não confere o registro. Ele mostra o que o produtor declarou e avisa o comprador.
"""
ATRIBUTO_INSPECAO = 6
SEM_REGISTRO = "Sem registro: venda só para estabelecimento inspecionado"

_TODO_O_PAIS = "Pode ser vendido em todo o país."
ABRANGENCIA = {
    "SIF (federal)": _TODO_O_PAIS,
    "Sisbi-POA": _TODO_O_PAIS,
    "Selo ARTE": _TODO_O_PAIS,
    "SIE (estadual)": "Inspeção estadual: pode ser vendido só dentro de {uf}.",
    "SIM (municipal)": "Inspeção municipal: pode ser vendido só dentro de {municipio}/{uf}.",
    SEM_REGISTRO: (
        "Sem registro de inspeção: só pode ser vendido para estabelecimento inspecionado "
        "(por exemplo, leite para laticínio). Não é para o consumidor final."
    ),
}


def aviso_inspecao(atributos, municipio, uf):
    """Texto sobre a área de venda, a partir dos atributos salvos do anúncio (ou None)."""
    for atributo in atributos:
        if atributo["id"] == ATRIBUTO_INSPECAO:
            modelo = ABRANGENCIA.get(atributo["valor"])
            return modelo.format(municipio=municipio, uf=uf) if modelo else None
    return None
