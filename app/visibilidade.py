"""Que produtos e que preços cada pessoa vê (RF28, RF29).

- Visitante ou conta sem perfil de comércio: modo "consumidor". Vê os produtos para o consumidor final
  e o preço de consumidor.
- Conta com perfil de comércio: modo "loja" (pode trocar para "consumidor" no topo da página). Vê os
  produtos para lojas, o preço para lojas, o pedido mínimo e o preço ao consumidor como referência.
- Produto marcado "só verificados": o preço para lojas aparece só para comércio verificado.

Tudo é decidido aqui, no servidor. Um preço que a pessoa não pode ver não vai para o HTML,
nem pode ser descoberto pelos filtros e pela ordenação por preço.
"""
from dataclasses import dataclass
from typing import Optional

from flask import g, session

MODO_CONSUMIDOR = "consumidor"
MODO_LOJA = "loja"


def _usuario():
    return g.get("usuario")


def tem_comercio():
    usuario = _usuario()
    return bool(usuario and usuario["tem_comercio"])


def comercio_verificado():
    usuario = _usuario()
    return bool(usuario and usuario["comercio_verificado"])


def modo():
    """'loja' para quem tem perfil de comércio (salvo se escolheu ver como consumidor), senão 'consumidor'."""
    if "modo_acesso" not in g:
        g.modo_acesso = MODO_LOJA if tem_comercio() and session.get("ver_como") != MODO_CONSUMIDOR else MODO_CONSUMIDOR
    return g.modo_acesso


def ve_tudo(produto):
    """O dono do produto e a administração veem os dois preços."""
    usuario = _usuario()
    return bool(usuario) and (usuario["id"] == produto["vendedor_id"] or usuario["papel"] == "admin")


def publico_sql(alias="pd"):
    """Condição SQL dos produtos que aparecem nas listas para o modo atual."""
    return f"{alias}.para_lojista = 1" if modo() == MODO_LOJA else f"{alias}.para_consumidor = 1"


def preco_sql(alias="pd"):
    """Expressão SQL do preço que a pessoa pode ver (para filtrar e ordenar sem vazar preço escondido)."""
    if modo() == MODO_LOJA:
        if comercio_verificado():
            return f"{alias}.preco_lojista_centavos"
        return f"CASE WHEN {alias}.so_verificados = 1 THEN NULL ELSE {alias}.preco_lojista_centavos END"
    return f"{alias}.preco_consumidor_centavos"


@dataclass(frozen=True)
class Preco:
    """O que mostrar no lugar do preço."""
    centavos: Optional[int] = None   # None com mostrar=True significa "a combinar"
    mostrar: bool = True
    rotulo: str = ""                 # ex.: "Preço para lojas"
    aviso: str = ""                  # texto no lugar do valor quando mostrar=False
    pedido_minimo: Optional[float] = None
    referencia_consumidor: Optional[int] = None  # preço ao consumidor, mostrado às lojas


def preco_visivel(produto):
    if modo() == MODO_LOJA and produto["para_lojista"]:
        if produto["so_verificados"] and not comercio_verificado() and not ve_tudo(produto):
            return Preco(mostrar=False, rotulo="Preço para lojas", aviso="Preço só para lojas verificadas")
        return Preco(
            centavos=produto["preco_lojista_centavos"], rotulo="Preço para lojas",
            pedido_minimo=produto["pedido_minimo_lojista"],
            referencia_consumidor=produto["preco_consumidor_centavos"] if produto["para_consumidor"] else None,
        )
    if produto["para_consumidor"]:
        rotulo = "Preço ao consumidor" if modo() == MODO_LOJA else ""
        return Preco(centavos=produto["preco_consumidor_centavos"], rotulo=rotulo)
    return Preco(mostrar=False, aviso="Vendido só para lojas")


def canal_de_compra(produto):
    """Como a pessoa compraria este produto: 'lojista', 'consumidor' ou None (não pode comprar).

    Decidido no servidor a partir do perfil e do modo, nunca a partir do formulário.
    """
    if modo() == MODO_LOJA and produto["para_lojista"] and (not produto["so_verificados"] or comercio_verificado()):
        return "lojista"
    if produto["para_consumidor"]:
        return "consumidor"
    return None


def motivo_sem_compra(produto):
    """Explicação para quem não pode comprar (quando canal_de_compra devolve None)."""
    if produto["para_lojista"] and modo() == MODO_LOJA:
        return "O produtor vende este produto só para lojas verificadas."
    if produto["para_lojista"] and tem_comercio():
        return "Este produto é vendido só para lojas. Escolha “Ver como loja” no topo da página para comprar."
    return "Este produto é vendido só para lojas e outros comércios."


def registrar(app):
    # Global (e não só variável de contexto) para funcionar dentro dos macros importados.
    app.add_template_global(preco_visivel, "preco_visivel")

    @app.context_processor
    def dados_de_visibilidade():
        return {"modo_acesso": modo()}
