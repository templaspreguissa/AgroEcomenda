"""Regras de negócio de encomendas e das propostas de venda feitas a elas.

Toda mudança de status passa por aqui, dentro de uma transação. As atualizações
conferem o status atual no próprio UPDATE (ex.: "WHERE status = 'pendente'"),
para duas ações simultâneas não deixarem os dados inconsistentes.

Estados (seção 8.1 da pesquisa):
  Encomenda: aberta -> em_negociacao -> concluida | cancelada | expirada
  Proposta:  pendente -> aceita | recusada | retirada | nao_selecionada
"""
from ..util import agora_utc_texto, hoje, normalizar_busca
from .alertas import avisar_produtores_da_regiao
from .comum import SQL_PROPOSTA, RegraNegocio, notificar

STATUS_ENCOMENDA_ATIVA = ("aberta", "em_negociacao")


# ---------- consultas ----------

SQL_ENCOMENDA = """
    SELECT e.*, u.sigla AS unidade_sigla, m.nome AS municipio_nome, m.uf AS municipio_uf,
           c.nome AS categoria_nome, us.nome AS comprador_nome, us.email AS comprador_email, us.status AS comprador_status,
           (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id) AS total_propostas,
           (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id AND p.status = 'pendente') AS propostas_pendentes
      FROM encomenda e
      JOIN unidade_medida u ON u.id = e.unidade_id
      JOIN municipio m      ON m.codigo_ibge = e.municipio_entrega_id
      JOIN categoria c      ON c.id = e.categoria_id
      JOIN usuario us       ON us.id = e.comprador_id
"""

def buscar_encomenda(db, encomenda_id):
    return db.execute(SQL_ENCOMENDA + " WHERE e.id = ?", (encomenda_id,)).fetchone()


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
        avisar_produtores_da_regiao(db, cursor.lastrowid)
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
