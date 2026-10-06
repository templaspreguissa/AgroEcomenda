"""Regras de negócio de encomendas e propostas.

Toda mudança de status passa por aqui, dentro de uma transação. As atualizações
conferem o status atual no próprio UPDATE (ex.: "WHERE status = 'pendente'"),
para duas ações simultâneas não deixarem os dados inconsistentes.

Estados (seção 8.1 da pesquisa):
  Encomenda: aberta -> em_negociacao -> concluida | cancelada | expirada
  Proposta:  pendente -> aceita | recusada | retirada | nao_selecionada
"""
from flask import current_app

from .util import agora_utc_texto, hoje, normalizar_busca

STATUS_ENCOMENDA_ATIVA = ("aberta", "em_negociacao")


class RegraNegocio(Exception):
    """Ação não permitida pelas regras do sistema. A mensagem é mostrada ao usuário."""


# ---------- consultas ----------

SQL_ENCOMENDA = """
    SELECT e.*, u.sigla AS unidade_sigla, m.nome AS municipio_nome, m.uf AS municipio_uf,
           c.nome AS categoria_nome, us.nome AS comprador_nome, us.email AS comprador_email,
           (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id) AS total_propostas,
           (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id AND p.status = 'pendente') AS propostas_pendentes
      FROM encomenda e
      JOIN unidade_medida u ON u.id = e.unidade_id
      JOIN municipio m      ON m.codigo_ibge = e.municipio_entrega_id
      JOIN categoria c      ON c.id = e.categoria_id
      JOIN usuario us       ON us.id = e.comprador_id
"""

SQL_PROPOSTA = """
    SELECT p.*, v.nome AS vendedor_nome, v.email AS vendedor_email,
           vm.nome AS vendedor_municipio, vm.uf AS vendedor_uf,
           c.nome AS comprador_nome, c.email AS comprador_email,
           cm.nome AS comprador_municipio, cm.uf AS comprador_uf, u.sigla AS unidade_sigla
      FROM proposta p
      JOIN usuario v             ON v.id = p.vendedor_id
      LEFT JOIN municipio vm     ON vm.codigo_ibge = v.municipio_id
      JOIN usuario c             ON c.id = p.comprador_id
      LEFT JOIN municipio cm     ON cm.codigo_ibge = c.municipio_id
      JOIN unidade_medida u      ON u.id = p.unidade_id
"""


def buscar_encomenda(db, encomenda_id):
    return db.execute(SQL_ENCOMENDA + " WHERE e.id = ?", (encomenda_id,)).fetchone()


def buscar_proposta(db, proposta_id):
    return db.execute(SQL_PROPOSTA + " WHERE p.id = ?", (proposta_id,)).fetchone()


def propostas_da_encomenda(db, encomenda_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.encomenda_id = ? "
        "ORDER BY CASE p.status WHEN 'aceita' THEN 0 WHEN 'pendente' THEN 1 ELSE 2 END, "
        "p.preco_unitario_centavos, p.criado_em",
        (encomenda_id,),
    ).fetchall()


def proposta_pendente_do_vendedor(db, encomenda_id, vendedor_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.encomenda_id = ? AND p.vendedor_id = ? AND p.status = 'pendente'",
        (encomenda_id, vendedor_id),
    ).fetchone()


# ---------- apoio ----------

def notificar(db, usuario_id, tipo, texto, link):
    db.execute(
        "INSERT INTO notificacao (usuario_id, tipo, texto, link) VALUES (?, ?, ?, ?)",
        (usuario_id, tipo, texto, link),
    )


def _link_encomenda(encomenda_id):
    return f"/encomendas/{encomenda_id}"


def _recalcular_status(db, encomenda_id):
    """Encomenda ativa fica 'em_negociacao' enquanto houver proposta pendente, senão volta a 'aberta'."""
    db.execute(
        """UPDATE encomenda
              SET status = CASE WHEN EXISTS (SELECT 1 FROM proposta
                                              WHERE encomenda_id = encomenda.id AND status = 'pendente')
                                THEN 'em_negociacao' ELSE 'aberta' END
            WHERE id = ? AND status IN ('aberta', 'em_negociacao')""",
        (encomenda_id,),
    )


def _encerrar_pendentes(db, encomenda_id, titulo, texto, exceto=None):
    """Marca como 'nao_selecionada' as propostas pendentes e avisa cada vendedor."""
    pendentes = db.execute(
        "SELECT id, vendedor_id FROM proposta WHERE encomenda_id = ? AND status = 'pendente' AND id IS NOT ?",
        (encomenda_id, exceto),
    ).fetchall()
    agora = agora_utc_texto()
    for proposta in pendentes:
        db.execute(
            "UPDATE proposta SET status = 'nao_selecionada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora, proposta["id"]),
        )
        notificar(db, proposta["vendedor_id"], "proposta_recusada", texto.format(titulo=titulo), _link_encomenda(encomenda_id))


def _validar_prazo_encomenda(prazo_limite):
    if prazo_limite < hoje():
        raise RegraNegocio("O prazo limite não pode ser uma data que já passou.")


def _exigir_encomenda_ativa(encomenda):
    if encomenda["status"] not in STATUS_ENCOMENDA_ATIVA or encomenda["prazo_limite"] < hoje().isoformat():
        raise RegraNegocio("Esta encomenda não está mais recebendo propostas.")


def _validar_dados_proposta(encomenda, dados):
    if dados["quantidade"] > encomenda["quantidade"]:
        raise RegraNegocio("A quantidade oferecida não pode ser maior que a quantidade pedida na encomenda.")
    if dados["prazo_entrega"] < hoje():
        raise RegraNegocio("O prazo de entrega não pode ser uma data que já passou.")
    if dados["prazo_entrega"].isoformat() > encomenda["prazo_limite"]:
        raise RegraNegocio("O prazo de entrega precisa ser até o prazo limite da encomenda.")
    if dados.get("validade") and dados["validade"] < hoje():
        raise RegraNegocio("A validade da proposta não pode ser uma data que já passou.")


# ---------- expiração (RF17) ----------

def expirar_encomendas_vencidas(db):
    """Encerra encomendas cujo prazo limite passou. Roda no início das páginas de encomendas."""
    vencidas = db.execute(
        "SELECT id, comprador_id, titulo FROM encomenda WHERE status IN ('aberta', 'em_negociacao') AND prazo_limite < ?",
        (hoje().isoformat(),),
    ).fetchall()
    if not vencidas:
        return 0
    agora = agora_utc_texto()
    with db:
        for encomenda in vencidas:
            alterou = db.execute(
                "UPDATE encomenda SET status = 'expirada', encerrada_em = ? "
                "WHERE id = ? AND status IN ('aberta', 'em_negociacao')",
                (agora, encomenda["id"]),
            ).rowcount
            if not alterou:
                continue
            _encerrar_pendentes(
                db, encomenda["id"], encomenda["titulo"],
                'O prazo da encomenda "{titulo}" terminou sem que sua proposta fosse escolhida.',
            )
            notificar(
                db, encomenda["comprador_id"], "encomenda_expirada",
                f'O prazo da sua encomenda "{encomenda["titulo"]}" terminou.', _link_encomenda(encomenda["id"]),
            )
    return len(vencidas)


# ---------- encomendas (RF07, RF16) ----------

def criar_encomenda(db, comprador_id, dados):
    _validar_prazo_encomenda(dados["prazo_limite"])
    with db:
        cursor = db.execute(
            """INSERT INTO encomenda (comprador_id, categoria_id, titulo, titulo_busca, descricao, quantidade,
                                      unidade_id, municipio_entrega_id, prazo_limite, transporte, condicoes_pagamento)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                comprador_id, dados["categoria_id"], dados["titulo"], normalizar_busca(dados["titulo"]),
                dados["descricao"], dados["quantidade"], dados["unidade_id"], dados["municipio_id"],
                dados["prazo_limite"].isoformat(), dados["transporte"], dados["condicoes_pagamento"],
            ),
        )
        # Reaproveita o município da primeira encomenda no perfil (evita digitar de novo).
        db.execute(
            "UPDATE usuario SET municipio_id = ? WHERE id = ? AND municipio_id IS NULL",
            (dados["municipio_id"], comprador_id),
        )
    return cursor.lastrowid


def pode_editar_encomenda(encomenda, usuario_id):
    return (
        encomenda["comprador_id"] == usuario_id
        and encomenda["status"] == "aberta"
        and encomenda["total_propostas"] == 0
    )


def editar_encomenda(db, encomenda, usuario_id, dados):
    if encomenda["comprador_id"] != usuario_id:
        raise PermissionError
    if not pode_editar_encomenda(encomenda, usuario_id):
        raise RegraNegocio("Só é possível editar encomendas abertas que ainda não receberam propostas.")
    _validar_prazo_encomenda(dados["prazo_limite"])
    with db:
        alterou = db.execute(
            """UPDATE encomenda
                  SET categoria_id = ?, titulo = ?, titulo_busca = ?, descricao = ?, quantidade = ?, unidade_id = ?,
                      municipio_entrega_id = ?, prazo_limite = ?, transporte = ?, condicoes_pagamento = ?
                WHERE id = ? AND status = 'aberta'
                  AND NOT EXISTS (SELECT 1 FROM proposta WHERE encomenda_id = encomenda.id)""",
            (
                dados["categoria_id"], dados["titulo"], normalizar_busca(dados["titulo"]), dados["descricao"],
                dados["quantidade"], dados["unidade_id"], dados["municipio_id"], dados["prazo_limite"].isoformat(),
                dados["transporte"], dados["condicoes_pagamento"], encomenda["id"],
            ),
        ).rowcount
        if not alterou:
            raise RegraNegocio("A encomenda recebeu uma proposta enquanto você editava. Atualize a página.")


def cancelar_encomenda(db, encomenda, usuario_id):
    if encomenda["comprador_id"] != usuario_id:
        raise PermissionError
    with db:
        alterou = db.execute(
            "UPDATE encomenda SET status = 'cancelada', encerrada_em = ? "
            "WHERE id = ? AND status IN ('aberta', 'em_negociacao')",
            (agora_utc_texto(), encomenda["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta encomenda já está encerrada.")
        _encerrar_pendentes(db, encomenda["id"], encomenda["titulo"], 'O comprador cancelou a encomenda "{titulo}".')


# ---------- propostas (RF08, RF09, RF24) ----------

def enviar_proposta(db, encomenda, vendedor_id, dados):
    if encomenda["comprador_id"] == vendedor_id:
        raise RegraNegocio("Você não pode enviar proposta para a sua própria encomenda.")
    _exigir_encomenda_ativa(encomenda)
    if proposta_pendente_do_vendedor(db, encomenda["id"], vendedor_id):
        raise RegraNegocio("Você já tem uma proposta aguardando resposta nesta encomenda. Edite a proposta existente.")
    _validar_dados_proposta(encomenda, dados)
    with db:
        cursor = db.execute(
            """INSERT INTO proposta (encomenda_id, comprador_id, vendedor_id, autor_id, preco_unitario_centavos,
                                     unidade_id, quantidade, prazo_entrega, transporte, validade, observacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                encomenda["id"], encomenda["comprador_id"], vendedor_id, vendedor_id, dados["preco_centavos"],
                encomenda["unidade_id"], dados["quantidade"], dados["prazo_entrega"].isoformat(), dados["transporte"],
                dados["validade"].isoformat() if dados.get("validade") else None, dados["observacao"] or None,
            ),
        )
        _recalcular_status(db, encomenda["id"])
        notificar(
            db, encomenda["comprador_id"], "nova_proposta",
            f'Você recebeu uma nova proposta para "{encomenda["titulo"]}".', _link_encomenda(encomenda["id"]),
        )
    return cursor.lastrowid


def editar_proposta(db, proposta, encomenda, usuario_id, dados):
    if proposta["vendedor_id"] != usuario_id:
        raise PermissionError
    _exigir_encomenda_ativa(encomenda)
    _validar_dados_proposta(encomenda, dados)
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


def retirar_proposta(db, proposta, usuario_id):
    if proposta["vendedor_id"] != usuario_id:
        raise PermissionError
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = 'retirada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora_utc_texto(), proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta já foi respondida e não pode mais ser retirada.")
        _recalcular_status(db, proposta["encomenda_id"])


def aceitar_proposta(db, proposta, encomenda, usuario_id):
    if encomenda["comprador_id"] != usuario_id:
        raise PermissionError
    _exigir_encomenda_ativa(encomenda)
    agora = agora_utc_texto()
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = 'aceita', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora, proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta não está mais aguardando resposta.")
        encerrou = db.execute(
            "UPDATE encomenda SET status = 'concluida', encerrada_em = ? "
            "WHERE id = ? AND status IN ('aberta', 'em_negociacao')",
            (agora, encomenda["id"]),
        ).rowcount
        if not encerrou:
            raise RegraNegocio("Esta encomenda já foi encerrada.")  # desfaz a transação inteira
        _encerrar_pendentes(
            db, encomenda["id"], encomenda["titulo"],
            'O comprador escolheu outra proposta para "{titulo}".', exceto=proposta["id"],
        )
        notificar(
            db, proposta["vendedor_id"], "proposta_aceita",
            f'Sua proposta para "{encomenda["titulo"]}" foi aceita.', _link_encomenda(encomenda["id"]),
        )


def recusar_proposta(db, proposta, encomenda, usuario_id):
    if encomenda["comprador_id"] != usuario_id:
        raise PermissionError
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = 'recusada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora_utc_texto(), proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta não está mais aguardando resposta.")
        _recalcular_status(db, encomenda["id"])
        notificar(
            db, proposta["vendedor_id"], "proposta_recusada",
            f'Sua proposta para "{encomenda["titulo"]}" foi recusada.', _link_encomenda(encomenda["id"]),
        )


# =====================================================================
# Anúncios (RF04, RF05, RF16) e propostas de compra sobre anúncio (RF18)
#   Anúncio:  ativo <-> pausado -> encerrado   (oculto = moderação)
#   Proposta: o comprador é o autor e o vendedor responde.
# =====================================================================

SQL_ANUNCIO = """
    SELECT a.*, u.sigla AS unidade_sigla, m.nome AS municipio_nome, m.uf AS municipio_uf,
           c.nome AS categoria_nome, c.categoria_pai_id AS categoria_pai_id,
           v.nome AS vendedor_nome, v.email AS vendedor_email, v.criado_em AS vendedor_desde,
           (SELECT arquivo FROM foto_anuncio f WHERE f.anuncio_id = a.id ORDER BY f.ordem, f.id LIMIT 1) AS foto_principal,
           (SELECT COUNT(*) FROM proposta p WHERE p.anuncio_id = a.id AND p.status = 'pendente') AS propostas_pendentes
      FROM anuncio a
      JOIN unidade_medida u ON u.id = a.unidade_id
      JOIN municipio m      ON m.codigo_ibge = a.municipio_id
      JOIN categoria c      ON c.id = a.categoria_id
      JOIN usuario v        ON v.id = a.vendedor_id
"""


def buscar_anuncio(db, anuncio_id):
    return db.execute(SQL_ANUNCIO + " WHERE a.id = ?", (anuncio_id,)).fetchone()


def fotos_do_anuncio(db, anuncio_id):
    return db.execute(
        "SELECT id, arquivo, texto_alternativo, ordem FROM foto_anuncio WHERE anuncio_id = ? ORDER BY ordem, id",
        (anuncio_id,),
    ).fetchall()


def propostas_do_anuncio(db, anuncio_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.anuncio_id = ? "
        "ORDER BY CASE p.status WHEN 'aceita' THEN 0 WHEN 'pendente' THEN 1 ELSE 2 END, "
        "p.preco_unitario_centavos DESC, p.criado_em",
        (anuncio_id,),
    ).fetchall()


def proposta_pendente_do_comprador(db, anuncio_id, comprador_id):
    return db.execute(
        SQL_PROPOSTA + " WHERE p.anuncio_id = ? AND p.comprador_id = ? AND p.status = 'pendente'",
        (anuncio_id, comprador_id),
    ).fetchone()


def _link_anuncio(anuncio_id):
    return f"/anuncios/{anuncio_id}"


def _gravar_atributos(db, anuncio_id, atributos):
    db.execute("DELETE FROM anuncio_atributo WHERE anuncio_id = ?", (anuncio_id,))
    db.executemany(
        "INSERT INTO anuncio_atributo (anuncio_id, atributo_id, valor) VALUES (?, ?, ?)",
        [(anuncio_id, atributo_id, valor) for atributo_id, valor in atributos.items()],
    )


def _gravar_fotos(db, anuncio_id, titulo, nomes, ordem_inicial=0):
    for posicao, nome in enumerate(nomes, start=ordem_inicial):
        db.execute(
            "INSERT INTO foto_anuncio (anuncio_id, arquivo, texto_alternativo, ordem) VALUES (?, ?, ?, ?)",
            (anuncio_id, nome, f"{titulo}, foto {posicao + 1}", posicao),
        )


def criar_anuncio(db, vendedor_id, dados, atributos, fotos):
    with db:
        cursor = db.execute(
            """INSERT INTO anuncio (vendedor_id, categoria_id, titulo, titulo_busca, descricao, preco_centavos,
                                    unidade_id, quantidade_disponivel, condicao, municipio_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vendedor_id, dados["categoria_id"], dados["titulo"], normalizar_busca(dados["titulo"]),
                dados["descricao"], dados["preco_centavos"], dados["unidade_id"], dados["quantidade"],
                dados["condicao"], dados["municipio_id"],
            ),
        )
        anuncio_id = cursor.lastrowid
        _gravar_atributos(db, anuncio_id, atributos)
        _gravar_fotos(db, anuncio_id, dados["titulo"], fotos)
        db.execute(
            "UPDATE usuario SET municipio_id = ? WHERE id = ? AND municipio_id IS NULL",
            (dados["municipio_id"], vendedor_id),
        )
    return anuncio_id


def editar_anuncio(db, anuncio, usuario_id, dados, atributos, fotos_novas, remover_ids):
    """Atualiza o anúncio. Devolve os nomes de arquivo das fotos removidas (para apagar do disco)."""
    if anuncio["vendedor_id"] != usuario_id:
        raise PermissionError
    if anuncio["status"] not in ("ativo", "pausado"):
        raise RegraNegocio("Anúncios encerrados ou ocultos pela moderação não podem ser editados.")
    atuais = fotos_do_anuncio(db, anuncio["id"])
    removidas = [foto for foto in atuais if foto["id"] in set(remover_ids)]
    limite = current_app.config["FOTOS_POR_ANUNCIO"]
    if len(atuais) - len(removidas) + len(fotos_novas) > limite:
        raise RegraNegocio(f"Cada anúncio pode ter no máximo {limite} fotos.")
    with db:
        db.execute(
            """UPDATE anuncio
                  SET categoria_id = ?, titulo = ?, titulo_busca = ?, descricao = ?, preco_centavos = ?,
                      unidade_id = ?, quantidade_disponivel = ?, condicao = ?, municipio_id = ?, atualizado_em = ?
                WHERE id = ?""",
            (
                dados["categoria_id"], dados["titulo"], normalizar_busca(dados["titulo"]), dados["descricao"],
                dados["preco_centavos"], dados["unidade_id"], dados["quantidade"], dados["condicao"],
                dados["municipio_id"], agora_utc_texto(), anuncio["id"],
            ),
        )
        _gravar_atributos(db, anuncio["id"], atributos)
        for foto in removidas:
            db.execute("DELETE FROM foto_anuncio WHERE id = ? AND anuncio_id = ?", (foto["id"], anuncio["id"]))
        proxima_ordem = max([foto["ordem"] for foto in atuais], default=-1) + 1
        _gravar_fotos(db, anuncio["id"], dados["titulo"], fotos_novas, proxima_ordem)
    return [foto["arquivo"] for foto in removidas]


TRANSICOES_ANUNCIO = {
    "pausar": (("ativo",), "pausado"),
    "reativar": (("pausado",), "ativo"),
    "encerrar": (("ativo", "pausado"), "encerrado"),
}


def mudar_status_anuncio(db, anuncio, usuario_id, acao):
    if anuncio["vendedor_id"] != usuario_id:
        raise PermissionError
    origens, destino = TRANSICOES_ANUNCIO[acao]
    marcadores = ", ".join("?" for _ in origens)
    with db:
        alterou = db.execute(
            f"UPDATE anuncio SET status = ?, atualizado_em = ? WHERE id = ? AND status IN ({marcadores})",
            (destino, agora_utc_texto(), anuncio["id"], *origens),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Não é possível fazer isso com o anúncio na situação atual.")
        if destino != "ativo":
            # Pausado ou encerrado não recebe propostas: as pendentes são encerradas com aviso ao comprador.
            pendentes = db.execute(
                "SELECT id, comprador_id FROM proposta WHERE anuncio_id = ? AND status = 'pendente'",
                (anuncio["id"],),
            ).fetchall()
            for proposta in pendentes:
                db.execute(
                    "UPDATE proposta SET status = 'nao_selecionada', respondida_em = ? WHERE id = ?",
                    (agora_utc_texto(), proposta["id"]),
                )
                notificar(
                    db, proposta["comprador_id"], "proposta_recusada",
                    f'O anúncio "{anuncio["titulo"]}" deixou de receber propostas.', _link_anuncio(anuncio["id"]),
                )


def _validar_proposta_anuncio(anuncio, dados):
    disponivel = anuncio["quantidade_disponivel"]
    if disponivel is not None and dados["quantidade"] > disponivel:
        raise RegraNegocio("A quantidade pedida não pode ser maior que a quantidade disponível no anúncio.")
    if dados["prazo_entrega"] < hoje():
        raise RegraNegocio("A data de entrega não pode ser uma data que já passou.")
    if dados.get("validade") and dados["validade"] < hoje():
        raise RegraNegocio("A validade da proposta não pode ser uma data que já passou.")


def enviar_proposta_anuncio(db, anuncio, comprador_id, dados):
    if anuncio["vendedor_id"] == comprador_id:
        raise RegraNegocio("Você não pode fazer proposta no seu próprio anúncio.")
    if anuncio["status"] != "ativo":
        raise RegraNegocio("Este anúncio não está recebendo propostas.")
    if proposta_pendente_do_comprador(db, anuncio["id"], comprador_id):
        raise RegraNegocio("Você já tem uma proposta aguardando resposta neste anúncio. Edite a proposta existente.")
    _validar_proposta_anuncio(anuncio, dados)
    with db:
        cursor = db.execute(
            """INSERT INTO proposta (anuncio_id, comprador_id, vendedor_id, autor_id, preco_unitario_centavos,
                                     unidade_id, quantidade, prazo_entrega, transporte, validade, observacao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                anuncio["id"], comprador_id, anuncio["vendedor_id"], comprador_id, dados["preco_centavos"],
                anuncio["unidade_id"], dados["quantidade"], dados["prazo_entrega"].isoformat(), dados["transporte"],
                dados["validade"].isoformat() if dados.get("validade") else None, dados["observacao"] or None,
            ),
        )
        notificar(
            db, anuncio["vendedor_id"], "nova_proposta",
            f'Você recebeu uma proposta de compra para "{anuncio["titulo"]}".', _link_anuncio(anuncio["id"]),
        )
    return cursor.lastrowid


def editar_proposta_anuncio(db, proposta, anuncio, usuario_id, dados):
    if proposta["comprador_id"] != usuario_id:
        raise PermissionError
    if anuncio["status"] != "ativo":
        raise RegraNegocio("Este anúncio não está recebendo propostas.")
    _validar_proposta_anuncio(anuncio, dados)
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


def retirar_proposta_anuncio(db, proposta, usuario_id):
    if proposta["comprador_id"] != usuario_id:
        raise PermissionError
    with db:
        alterou = db.execute(
            "UPDATE proposta SET status = 'retirada', respondida_em = ? WHERE id = ? AND status = 'pendente'",
            (agora_utc_texto(), proposta["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta proposta já foi respondida e não pode mais ser retirada.")


def responder_proposta_anuncio(db, proposta, anuncio, usuario_id, aceitar):
    """O vendedor aceita ou recusa. O anúncio continua ativo: ele pode vender para outros compradores."""
    if anuncio["vendedor_id"] != usuario_id:
        raise PermissionError
    if aceitar and anuncio["status"] != "ativo":
        raise RegraNegocio("Reative o anúncio antes de aceitar propostas.")
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
            f'Sua proposta para "{anuncio["titulo"]}" foi {"aceita" if aceitar else "recusada"}.',
            _link_anuncio(anuncio["id"]),
        )
