"""Regras de negócio dos produtos (RF04, RF05, RF16, RF28, RF32) e das propostas de compra sobre eles (RF18, RF31).

  Produto:  ativo <-> pausado -> encerrado   (oculto = moderação)
  Proposta: o comprador é o autor e o produtor responde. O canal diz se a compra é como
            consumidor final ou como loja, e vale o preço e as regras daquele público.
"""
from flask import current_app

from ..inspecao import area_de_venda, motivo_para_nao_vender
from ..util import agora_utc_texto, hoje, normalizar_busca
from .alertas import avisar_lojas_da_regiao
from .comum import SQL_PROPOSTA, RegraNegocio, notificar

SQL_PRODUTO = """
    SELECT pd.*, u.sigla AS unidade_sigla, m.nome AS municipio_nome, m.uf AS municipio_uf,
           m.regiao_imediata_id, c.nome AS categoria_nome, c.categoria_pai_id AS categoria_pai_id,
           v.nome AS vendedor_nome, v.email AS vendedor_email, v.criado_em AS vendedor_desde,
           pp.nome_vitrine AS vitrine_nome,
           (SELECT arquivo FROM foto_produto f WHERE f.produto_id = pd.id ORDER BY f.ordem, f.id LIMIT 1) AS foto_principal,
           (SELECT COUNT(*) FROM proposta pr WHERE pr.produto_id = pd.id AND pr.status = 'pendente') AS propostas_pendentes
      FROM produto pd
      JOIN unidade_medida u ON u.id = pd.unidade_id
      JOIN municipio m      ON m.codigo_ibge = pd.municipio_id
      JOIN categoria c      ON c.id = pd.categoria_id
      JOIN usuario v        ON v.id = pd.vendedor_id
      LEFT JOIN perfil_produtor pp ON pp.usuario_id = pd.vendedor_id
"""

CAMPOS = (
    "categoria_id", "titulo", "descricao", "unidade_id", "quantidade_disponivel", "municipio_id",
    "para_consumidor", "para_lojista", "preco_consumidor_centavos", "preco_lojista_centavos",
    "pedido_minimo_lojista", "so_verificados", "disponibilidade", "meses_safra",
)


def buscar_produto(db, produto_id):
    return db.execute(SQL_PRODUTO + " WHERE pd.id = ?", (produto_id,)).fetchone()


def fotos_do_produto(db, produto_id):
    return db.execute(
        "SELECT id, arquivo, texto_alternativo, ordem FROM foto_produto WHERE produto_id = ? ORDER BY ordem, id",
        (produto_id,),
    ).fetchall()


def atributos_do_produto(db, produto_id):
    return db.execute(
        """SELECT a.id, a.nome, v.valor FROM produto_atributo v
             JOIN atributo_categoria a ON a.id = v.atributo_id
            WHERE v.produto_id = ? ORDER BY a.id""",
        (produto_id,),
    ).fetchall()


def propostas_do_produto(db, produto_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.produto_id = ? "
        "ORDER BY CASE p.status WHEN 'aceita' THEN 0 WHEN 'pendente' THEN 1 ELSE 2 END, "
        "p.preco_unitario_centavos DESC, p.criado_em",
        (produto_id,),
    ).fetchall()


def proposta_pendente_do_comprador(db, produto_id, comprador_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.produto_id = ? AND p.comprador_id = ? AND p.status = 'pendente'",
        (produto_id, comprador_id),
    ).fetchone()


def _link_produto(produto_id):
    return f"/produtos/{produto_id}"


def _gravar_atributos(db, produto_id, atributos):
    db.execute("DELETE FROM produto_atributo WHERE produto_id = ?", (produto_id,))
    db.executemany(
        "INSERT INTO produto_atributo (produto_id, atributo_id, valor) VALUES (?, ?, ?)",
        [(produto_id, atributo_id, valor) for atributo_id, valor in atributos.items()],
    )


def _gravar_fotos(db, produto_id, titulo, nomes, ordem_inicial=0):
    for posicao, nome in enumerate(nomes, start=ordem_inicial):
        db.execute(
            "INSERT INTO foto_produto (produto_id, arquivo, texto_alternativo, ordem) VALUES (?, ?, ?, ?)",
            (produto_id, nome, f"{titulo}, foto {posicao + 1}", posicao),
        )


def _valores(dados):
    return [dados[campo] for campo in CAMPOS]


# ---------- cadastrar e editar (RF04, RF28) ----------

def criar_produto(db, vendedor_id, dados, atributos, fotos):
    with db:
        cursor = db.execute(
            f"""INSERT INTO produto (vendedor_id, titulo_busca, {', '.join(CAMPOS)})
                VALUES (?, ?, {', '.join('?' * len(CAMPOS))})""",
            [vendedor_id, normalizar_busca(dados["titulo"]), *_valores(dados)],
        )
        produto_id = cursor.lastrowid
        _gravar_atributos(db, produto_id, atributos)
        _gravar_fotos(db, produto_id, dados["titulo"], fotos)
        db.execute(
            "UPDATE usuario SET municipio_id = ? WHERE id = ? AND municipio_id IS NULL",
            (dados["municipio_id"], vendedor_id),
        )
        avisar_lojas_da_regiao(db, produto_id)
    return produto_id


def editar_produto(db, produto, usuario_id, dados, atributos, fotos_novas, remover_ids):
    """Atualiza o produto. Devolve os nomes de arquivo das fotos removidas (para apagar do disco)."""
    if produto["vendedor_id"] != usuario_id:
        raise PermissionError
    if produto["status"] not in ("ativo", "pausado"):
        raise RegraNegocio("Produtos encerrados ou ocultos pela moderação não podem ser editados.")
    atuais = fotos_do_produto(db, produto["id"])
    removidas = [foto for foto in atuais if foto["id"] in set(remover_ids)]
    limite = current_app.config["FOTOS_POR_PRODUTO"]
    if len(atuais) - len(removidas) + len(fotos_novas) > limite:
        raise RegraNegocio(f"Cada produto pode ter no máximo {limite} fotos.")
    with db:
        db.execute(
            f"""UPDATE produto
                   SET titulo_busca = ?, atualizado_em = ?, {', '.join(f'{campo} = ?' for campo in CAMPOS)}
                 WHERE id = ?""",
            [normalizar_busca(dados["titulo"]), agora_utc_texto(), *_valores(dados), produto["id"]],
        )
        _gravar_atributos(db, produto["id"], atributos)
        for foto in removidas:
            db.execute("DELETE FROM foto_produto WHERE id = ? AND produto_id = ?", (foto["id"], produto["id"]))
        proxima_ordem = max([foto["ordem"] for foto in atuais], default=-1) + 1
        _gravar_fotos(db, produto["id"], dados["titulo"], fotos_novas, proxima_ordem)
        _encerrar_propostas_de_publico_retirado(db, produto, dados)
    return [foto["arquivo"] for foto in removidas]


def _encerrar_propostas_de_publico_retirado(db, produto, dados):
    """Se o produtor deixou de vender para um público, as propostas pendentes daquele público acabam."""
    canais = [canal for canal, chave in (("consumidor", "para_consumidor"), ("lojista", "para_lojista"))
              if not dados[chave]]
    for canal in canais:
        _encerrar_pendentes(db, produto, f'O produto "{produto["titulo"]}" deixou de ser vendido para esse público.', canal)


def _encerrar_pendentes(db, produto, texto, canal=None):
    pendentes = db.execute(
        "SELECT id, comprador_id FROM proposta WHERE produto_id = ? AND status = 'pendente' AND (? IS NULL OR canal = ?)",
        (produto["id"], canal, canal),
    ).fetchall()
    for proposta in pendentes:
        db.execute(
            "UPDATE proposta SET status = 'nao_selecionada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora_utc_texto(), proposta["id"]),
        )
        notificar(db, proposta["comprador_id"], "proposta_recusada", texto, _link_produto(produto["id"]))


# ---------- pausar, reativar, encerrar (RF16) ----------

TRANSICOES_PRODUTO = {
    "pausar": (("ativo",), "pausado"),
    "reativar": (("pausado",), "ativo"),
    "encerrar": (("ativo", "pausado"), "encerrado"),
}


def mudar_status_produto(db, produto, usuario_id, acao):
    if produto["vendedor_id"] != usuario_id:
        raise PermissionError
    origens, destino = TRANSICOES_PRODUTO[acao]
    marcadores = ", ".join("?" for _ in origens)
    with db:
        alterou = db.execute(
            f"UPDATE produto SET status = ?, atualizado_em = ? WHERE id = ? AND status IN ({marcadores})",
            (destino, agora_utc_texto(), produto["id"], *origens),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Não é possível fazer isso com o produto na situação atual.")
        if destino != "ativo":
            # Pausado ou encerrado não recebe propostas: as pendentes são encerradas com aviso ao comprador.
            _encerrar_pendentes(db, produto, f'O produto "{produto["titulo"]}" deixou de receber propostas.')


# ---------- propostas de compra (RF18, RF31) ----------

def _validar_proposta(db, produto, dados, canal, comprador):
    disponivel = produto["quantidade_disponivel"]
    if disponivel is not None and dados["quantidade"] > disponivel:
        raise RegraNegocio("A quantidade pedida não pode ser maior que a quantidade disponível.")
    minimo = produto["pedido_minimo_lojista"]
    if canal == "lojista" and minimo is not None and dados["quantidade"] < minimo:
        raise RegraNegocio("A quantidade é menor que o pedido mínimo para lojas.")
    if dados["prazo_entrega"] < hoje():
        raise RegraNegocio("A data de entrega não pode ser uma data que já passou.")
    if dados.get("validade") and dados["validade"] < hoje():
        raise RegraNegocio("A validade da proposta não pode ser uma data que já passou.")
    motivo = motivo_para_nao_vender(area_de_venda(atributos_do_produto(db, produto["id"])), produto, comprador, canal)
    if motivo:
        raise RegraNegocio(motivo)


def enviar_proposta_produto(db, produto, comprador_id, dados, canal, comprador=None):
    """`canal` vem de visibilidade.canal_de_compra (decidido no servidor, nunca pelo formulário)."""
    if produto["vendedor_id"] == comprador_id:
        raise RegraNegocio("Você não pode fazer proposta no seu próprio produto.")
    if produto["status"] != "ativo":
        raise RegraNegocio("Este produto não está recebendo propostas.")
    if canal is None:
        raise RegraNegocio("Este produto não está à venda para você.")
    if proposta_pendente_do_comprador(db, produto["id"], comprador_id):
        raise RegraNegocio("Você já tem uma proposta aguardando resposta neste produto. Edite a proposta existente.")
    _validar_proposta(db, produto, dados, canal, comprador)
    with db:
        cursor = db.execute(
            """INSERT INTO proposta (produto_id, canal, comprador_id, vendedor_id, autor_id, preco_unitario_centavos,
                                     unidade_id, quantidade, prazo_entrega, transporte, validade, observacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                produto["id"], canal, comprador_id, produto["vendedor_id"], comprador_id, dados["preco_centavos"],
                produto["unidade_id"], dados["quantidade"], dados["prazo_entrega"].isoformat(), dados["transporte"],
                dados["validade"].isoformat() if dados.get("validade") else None, dados["observacao"] or None,
            ),
        )
        origem = "uma loja" if canal == "lojista" else "um consumidor"
        notificar(
            db, produto["vendedor_id"], "nova_proposta",
            f'Você recebeu uma proposta de compra de {origem} para "{produto["titulo"]}".', _link_produto(produto["id"]),
        )
    return cursor.lastrowid


def editar_proposta_produto(db, proposta, produto, usuario_id, dados, comprador=None):
    if proposta["comprador_id"] != usuario_id:
        raise PermissionError
    if produto["status"] != "ativo":
        raise RegraNegocio("Este produto não está recebendo propostas.")
    _validar_proposta(db, produto, dados, proposta["canal"], comprador)
    with db:
        alterou = db.execute(
            """UPDATE proposta
                  SET preco_unitario_centavos = ?, quantidade = ?, prazo_entrega = ?, transporte = ?,
                      validade = ?, observacao = ?
                WHERE id = ? AND status = 'pendente'""",
            (
                dados["preco_centavos"], dados["quantidade"], dados["prazo_entrega"].isoformat(), dados["transporte"],
                dados["validade"].isoformat() if dados.get("validade") else None, dados["observacao"] or None,
                proposta["id"],
            ),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta já foi respondida e não pode mais ser alterada.")


def retirar_proposta_produto(db, proposta, usuario_id):
    if proposta["comprador_id"] != usuario_id:
        raise PermissionError
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = 'retirada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora_utc_texto(), proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta já foi respondida e não pode mais ser retirada.")


def responder_proposta_produto(db, proposta, produto, usuario_id, aceitar):
    """O produtor aceita ou recusa. O produto continua ativo: ele pode vender para outros compradores."""
    if produto["vendedor_id"] != usuario_id:
        raise PermissionError
    if aceitar and produto["status"] != "ativo":
        raise RegraNegocio("Reative o produto antes de aceitar propostas.")
    novo_status = "aceita" if aceitar else "recusada"
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = ?, respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (novo_status, agora_utc_texto(), proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta não está mais aguardando resposta.")
        notificar(
            db, proposta["comprador_id"], "proposta_aceita" if aceitar else "proposta_recusada",
            f'Sua proposta para "{produto["titulo"]}" foi {"aceita" if aceitar else "recusada"}.',
            _link_produto(produto["id"]),
        )
