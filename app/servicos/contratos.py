"""Contratos de fornecimento entre produtor e comércio (RF34–RF36).

Fluxo:
  rascunho  -> só o autor vê e edita. Ao enviar, a versão 1 é registrada e o envio vale como aceite do autor.
  enviado   -> quem está sendo aguardado aceita, recusa ou propõe alterações (nova versão, já aceita por quem
               alterou, e a vez passa para a outra parte). Quem enviou pode cancelar.
  ativo     -> as duas partes aceitaram a MESMA versão. Pode ser rescindido por qualquer parte (com motivo
               e aviso prévio) e é encerrado sozinho depois do término.

Cada versão enviada é guardada em JSON canônico com hash SHA-256. O aceite registra quem, quando, a versão e
o hash que a pessoa viu: se o contrato mudou enquanto ela lia, o aceite é recusado (UPDATE protegido).
Base legal do aceite eletrônico: Código Civil, art. 107, e MP nº 2.200-2/2001, art. 10, § 2º.
"""
import hashlib
import json
from datetime import date, timedelta

from ..util import FREQUENCIAS, TRANSPORTE, agora_utc_texto, hoje
from .comum import RegraNegocio, notificar

VIGENCIA_MAXIMA_DIAS = 731  # dois anos
ITENS_MAXIMOS = 10

SQL_CONTRATO = """
    SELECT c.*,
           pu.nome AS produtor_nome, pp.nome_vitrine AS produtor_vitrine,
           pm.nome AS produtor_municipio, pm.uf AS produtor_uf, pu.email AS produtor_email,
           cu.nome AS comercio_nome, pc.nome_fantasia AS comercio_loja, pc.cnpj AS comercio_cnpj,
           pc.verificado_em IS NOT NULL AS comercio_verificado,
           cm.nome AS comercio_municipio, cm.uf AS comercio_uf, cu.email AS comercio_email,
           me.nome AS entrega_municipio, me.uf AS entrega_uf
      FROM contrato c
      JOIN usuario pu              ON pu.id = c.produtor_id
      LEFT JOIN perfil_produtor pp ON pp.usuario_id = c.produtor_id
      LEFT JOIN municipio pm       ON pm.codigo_ibge = pp.municipio_id
      JOIN usuario cu              ON cu.id = c.comercio_id
      LEFT JOIN perfil_comercio pc ON pc.usuario_id = c.comercio_id
      LEFT JOIN municipio cm       ON cm.codigo_ibge = pc.municipio_id
      JOIN municipio me            ON me.codigo_ibge = c.municipio_entrega_id
"""

CAMPOS = (
    "inicio", "termino", "frequencia", "dia_entrega", "transporte", "municipio_entrega_id", "local_entrega",
    "condicoes_pagamento", "padrao_qualidade", "reajuste", "aviso_previo_dias", "observacoes",
)


# ---------- consultas ----------

def buscar_contrato(db, contrato_id, usuario_id):
    """O contrato visto por uma das partes. O rascunho só existe para o autor. None para os demais."""
    contrato = db.execute(SQL_CONTRATO + " WHERE c.id = ?", (contrato_id,)).fetchone()
    if contrato is None or usuario_id not in (contrato["produtor_id"], contrato["comercio_id"]):
        return None
    if contrato["status"] == "rascunho" and usuario_id != contrato["autor_id"]:
        return None
    return contrato


def contratos_do_usuario(db, usuario_id):
    return db.execute(
        SQL_CONTRATO + """ WHERE ? IN (c.produtor_id, c.comercio_id) AND (c.status <> 'rascunho' OR c.autor_id = ?)
         ORDER BY CASE WHEN c.aguardando_id = ? THEN 0 WHEN c.status IN ('rascunho', 'enviado') THEN 1
                       WHEN c.status = 'ativo' THEN 2 ELSE 3 END, COALESCE(c.atualizado_em, c.criado_em) DESC""",
        (usuario_id, usuario_id, usuario_id),
    ).fetchall()


def itens_do_contrato(db, contrato_id):
    return db.execute(
        """SELECT i.*, u.sigla AS unidade_sigla FROM contrato_item i JOIN unidade_medida u ON u.id = i.unidade_id
            WHERE i.contrato_id = ? ORDER BY i.ordem, i.id""",
        (contrato_id,),
    ).fetchall()


def versoes_do_contrato(db, contrato_id):
    return db.execute(
        """SELECT v.versao, v.hash, v.criada_em, v.criada_por, u.nome AS criada_por_nome
             FROM contrato_versao v JOIN usuario u ON u.id = v.criada_por
            WHERE v.contrato_id = ? ORDER BY v.versao DESC""",
        (contrato_id,),
    ).fetchall()


def aceites_do_contrato(db, contrato_id):
    return db.execute(
        """SELECT a.versao, a.usuario_id, a.hash, a.aceito_em, u.nome FROM contrato_aceite a
             JOIN usuario u ON u.id = a.usuario_id WHERE a.contrato_id = ? ORDER BY a.aceito_em, a.versao""",
        (contrato_id,),
    ).fetchall()


def versao_atual(db, contrato):
    return db.execute(
        "SELECT versao, termos, hash FROM contrato_versao WHERE contrato_id = ? AND versao = ?",
        (contrato["id"], contrato["versao_atual"]),
    ).fetchone()


def integridade_ok(versao):
    """Recalcula o hash do JSON guardado e compara com o hash registrado."""
    return versao is not None and hashlib.sha256(versao["termos"].encode("utf-8")).hexdigest() == versao["hash"]


def contratos_aguardando(db, usuario_id):
    return db.execute(
        "SELECT COUNT(*) FROM contrato WHERE aguardando_id = ? AND status = 'enviado'", (usuario_id,)
    ).fetchone()[0]


# ---------- partes ----------

def outra_parte(contrato, usuario_id):
    return contrato["comercio_id"] if usuario_id == contrato["produtor_id"] else contrato["produtor_id"]


def conferir_partes(db, produtor_id, comercio_id):
    """O fornecedor precisa de vitrine e o comprador, de loja. Levanta RegraNegocio com a explicação."""
    if produtor_id == comercio_id:
        raise RegraNegocio("Um contrato precisa de duas pessoas diferentes.")
    produtor = db.execute(
        """SELECT 1 FROM perfil_produtor pp JOIN usuario u ON u.id = pp.usuario_id
            WHERE pp.usuario_id = ? AND pp.status = 'ativo' AND u.status = 'ativo'""", (produtor_id,)
    ).fetchone()
    if produtor is None:
        raise RegraNegocio("Contratos de fornecimento são feitos com produtores que têm vitrine.")
    comercio = db.execute(
        """SELECT 1 FROM perfil_comercio pc JOIN usuario u ON u.id = pc.usuario_id
            WHERE pc.usuario_id = ? AND pc.status = 'ativo' AND u.status = 'ativo'""", (comercio_id,)
    ).fetchone()
    if comercio is None:
        raise RegraNegocio("Contratos de fornecimento são feitos com comércios que têm loja cadastrada.")


def _nome_da_parte(contrato, usuario_id):
    if usuario_id == contrato["produtor_id"]:
        return contrato["produtor_vitrine"] or contrato["produtor_nome"]
    return contrato["comercio_loja"] or contrato["comercio_nome"]


def _link(contrato_id):
    return f"/contratos/{contrato_id}"


# ---------- validação dos termos ----------

def validar_termos(db, produtor_id, termos, itens):
    inicio, termino = date.fromisoformat(termos["inicio"]), date.fromisoformat(termos["termino"])
    if termino <= inicio:
        raise RegraNegocio("O término precisa ser depois do início.")
    if termino < hoje():
        raise RegraNegocio("O término não pode ser uma data que já passou.")
    if (termino - inicio).days > VIGENCIA_MAXIMA_DIAS:
        raise RegraNegocio("Use uma vigência de até dois anos. Depois, as partes podem fazer um novo contrato.")
    if termos["frequencia"] not in FREQUENCIAS or termos["transporte"] not in TRANSPORTE:
        raise RegraNegocio("Escolha a frequência e o transporte.")
    if not 0 <= termos["aviso_previo_dias"] <= 180:
        raise RegraNegocio("O aviso prévio vai de 0 a 180 dias.")
    if not itens:
        raise RegraNegocio("Inclua pelo menos um item no contrato.")
    if len(itens) > ITENS_MAXIMOS:
        raise RegraNegocio(f"Use no máximo {ITENS_MAXIMOS} itens.")
    for item in itens:
        if item["produto_id"] is not None:
            dono = db.execute(
                "SELECT vendedor_id FROM produto WHERE id = ? AND status <> 'oculto'", (item["produto_id"],)
            ).fetchone()
            if dono is None or dono["vendedor_id"] != produtor_id:
                raise RegraNegocio("Um dos itens aponta para um produto que não é deste produtor.")


# ---------- termos canônicos e hash ----------

def termos_canonicos(db, contrato_id):
    """JSON com tudo o que foi combinado (partes, termos e itens), sempre na mesma forma, e o hash dele."""
    contrato = db.execute(SQL_CONTRATO + " WHERE c.id = ?", (contrato_id,)).fetchone()
    itens = itens_do_contrato(db, contrato_id)
    termos = {
        "contrato": contrato["id"],
        "versao": contrato["versao_atual"],
        "fornecedor": {
            "usuario_id": contrato["produtor_id"], "nome": contrato["produtor_nome"],
            "vitrine": contrato["produtor_vitrine"],
            "municipio": f"{contrato['produtor_municipio']}/{contrato['produtor_uf']}",
        },
        "comprador": {
            "usuario_id": contrato["comercio_id"], "nome": contrato["comercio_nome"], "loja": contrato["comercio_loja"],
            "cnpj": contrato["comercio_cnpj"], "municipio": f"{contrato['comercio_municipio']}/{contrato['comercio_uf']}",
        },
        "vigencia": {"inicio": contrato["inicio"], "termino": contrato["termino"]},
        "entrega": {
            "frequencia": contrato["frequencia"], "dia": contrato["dia_entrega"], "transporte": contrato["transporte"],
            "municipio": f"{contrato['entrega_municipio']}/{contrato['entrega_uf']}", "local": contrato["local_entrega"],
        },
        "pagamento": contrato["condicoes_pagamento"],
        "reajuste": contrato["reajuste"],
        "qualidade": contrato["padrao_qualidade"],
        "aviso_previo_dias": contrato["aviso_previo_dias"],
        "observacoes": contrato["observacoes"],
        "itens": [
            {
                "descricao": item["descricao"], "produto_id": item["produto_id"],
                "quantidade_por_entrega": item["quantidade_por_entrega"], "unidade": item["unidade_sigla"],
                "preco_unitario_centavos": item["preco_unitario_centavos"],
            }
            for item in itens
        ],
    }
    texto = json.dumps(termos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return texto, hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _registrar_versao_e_aceite(db, contrato_id, versao, usuario_id):
    texto, codigo = termos_canonicos(db, contrato_id)
    db.execute(
        "INSERT INTO contrato_versao (contrato_id, versao, termos, hash, criada_por) VALUES (?, ?, ?, ?, ?)",
        (contrato_id, versao, texto, codigo, usuario_id),
    )
    db.execute(
        "INSERT INTO contrato_aceite (contrato_id, versao, usuario_id, hash) VALUES (?, ?, ?, ?)",
        (contrato_id, versao, usuario_id, codigo),
    )
    return codigo


# ---------- gravação ----------

def _gravar_itens(db, contrato_id, itens):
    db.execute("DELETE FROM contrato_item WHERE contrato_id = ?", (contrato_id,))
    db.executemany(
        """INSERT INTO contrato_item (contrato_id, produto_id, descricao, quantidade_por_entrega, unidade_id,
                                      preco_unitario_centavos, ordem) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (contrato_id, item["produto_id"], item["descricao"], item["quantidade"], item["unidade_id"],
             item["preco_centavos"], ordem)
            for ordem, item in enumerate(itens)
        ],
    )


def criar_contrato(db, autor_id, produtor_id, comercio_id, termos, itens, origem_proposta_id=None):
    if autor_id not in (produtor_id, comercio_id):
        raise PermissionError
    conferir_partes(db, produtor_id, comercio_id)
    validar_termos(db, produtor_id, termos, itens)
    with db:
        contrato_id = db.execute(
            f"""INSERT INTO contrato (produtor_id, comercio_id, autor_id, origem_proposta_id, {', '.join(CAMPOS)})
                VALUES (?, ?, ?, ?, {', '.join('?' * len(CAMPOS))})""",
            [produtor_id, comercio_id, autor_id, origem_proposta_id, *(termos[campo] for campo in CAMPOS)],
        ).lastrowid
        _gravar_itens(db, contrato_id, itens)
    return contrato_id


def editar_contrato(db, contrato, usuario_id, termos, itens):
    """No rascunho, o autor muda à vontade. Enviado, quem está sendo aguardado propõe alterações (nova versão)."""
    if contrato["status"] == "rascunho":
        if usuario_id != contrato["autor_id"]:
            raise PermissionError
    elif contrato["status"] == "enviado":
        if usuario_id != contrato["aguardando_id"]:
            raise RegraNegocio("Agora é a vez da outra parte responder. Espere a resposta antes de alterar.")
    else:
        raise RegraNegocio("Este contrato não pode mais ser alterado.")
    validar_termos(db, contrato["produtor_id"], termos, itens)
    with db:
        if contrato["status"] == "rascunho":
            alterou = db.execute(
                f"""UPDATE contrato SET atualizado_em = ?, {', '.join(f'{campo} = ?' for campo in CAMPOS)}
                     WHERE id = ? AND status = 'rascunho'""",
                [agora_utc_texto(), *(termos[campo] for campo in CAMPOS), contrato["id"]],
            ).rowcount
        else:
            nova = contrato["versao_atual"] + 1
            outro = outra_parte(contrato, usuario_id)
            alterou = db.execute(
                f"""UPDATE contrato SET versao_atual = ?, aguardando_id = ?, atualizado_em = ?,
                                        {', '.join(f'{campo} = ?' for campo in CAMPOS)}
                     WHERE id = ? AND status = 'enviado' AND versao_atual = ? AND aguardando_id = ?""",
                [nova, outro, agora_utc_texto(), *(termos[campo] for campo in CAMPOS),
                 contrato["id"], contrato["versao_atual"], usuario_id],
            ).rowcount
        if not alterou:
            raise RegraNegocio("O contrato mudou enquanto você editava. Abra de novo e revise.")
        _gravar_itens(db, contrato["id"], itens)
        if contrato["status"] == "enviado":
            _registrar_versao_e_aceite(db, contrato["id"], nova, usuario_id)
            notificar(
                db, outro, "contrato",
                f"{_nome_da_parte(contrato, usuario_id)} propôs alterações no contrato nº {contrato['id']} (versão {nova}).",
                _link(contrato["id"]),
            )


def enviar_contrato(db, contrato, usuario_id):
    if contrato["status"] != "rascunho" or usuario_id != contrato["autor_id"]:
        raise RegraNegocio("Só o autor envia o rascunho.")
    if contrato["termino"] < hoje().isoformat():
        raise RegraNegocio("O término já passou. Edite as datas antes de enviar.")
    conferir_partes(db, contrato["produtor_id"], contrato["comercio_id"])
    outro = outra_parte(contrato, usuario_id)
    with db:
        alterou = db.execute(
            "UPDATE contrato SET status = 'enviado', aguardando_id = ?, atualizado_em = ? WHERE id = ? AND status = 'rascunho'",
            (outro, agora_utc_texto(), contrato["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Este rascunho já foi enviado ou cancelado.")
        _registrar_versao_e_aceite(db, contrato["id"], contrato["versao_atual"], usuario_id)
        notificar(
            db, outro, "contrato",
            f"{_nome_da_parte(contrato, usuario_id)} enviou uma proposta de contrato de fornecimento (nº {contrato['id']}).",
            _link(contrato["id"]),
        )


def aceitar_contrato(db, contrato, usuario_id, hash_visto):
    if contrato["status"] != "enviado" or usuario_id != contrato["aguardando_id"]:
        raise RegraNegocio("Este contrato não está aguardando a sua resposta.")
    atual = versao_atual(db, contrato)
    if atual is None or hash_visto != atual["hash"]:
        raise RegraNegocio("O contrato mudou desde que você abriu a página. Revise a versão atual antes de aceitar.")
    if contrato["termino"] < hoje().isoformat():
        raise RegraNegocio("O término já passou. Proponha novas datas antes de aceitar.")
    outro = outra_parte(contrato, usuario_id)
    with db:
        alterou = db.execute(
            """UPDATE contrato SET status = 'ativo', aguardando_id = NULL, ativado_em = ?, atualizado_em = ?
                WHERE id = ? AND status = 'enviado' AND versao_atual = ? AND aguardando_id = ?""",
            (agora_utc_texto(), agora_utc_texto(), contrato["id"], atual["versao"], usuario_id),
        ).rowcount
        if not alterou:
            raise RegraNegocio("O contrato mudou desde que você abriu a página. Revise a versão atual antes de aceitar.")
        db.execute(
            "INSERT INTO contrato_aceite (contrato_id, versao, usuario_id, hash) VALUES (?, ?, ?, ?)",
            (contrato["id"], atual["versao"], usuario_id, atual["hash"]),
        )
        aceites = db.execute(
            "SELECT COUNT(DISTINCT usuario_id) FROM contrato_aceite WHERE contrato_id = ? AND versao = ? AND hash = ?",
            (contrato["id"], atual["versao"], atual["hash"]),
        ).fetchone()[0]
        if aceites != 2:  # nunca deveria acontecer: quem propôs a versão já a aceitou
            raise RegraNegocio("Falta o aceite da outra parte nesta versão.")
        notificar(
            db, outro, "contrato",
            f"{_nome_da_parte(contrato, usuario_id)} aceitou o contrato nº {contrato['id']}. Ele está ativo.",
            _link(contrato["id"]),
        )


def recusar_contrato(db, contrato, usuario_id, motivo=""):
    if contrato["status"] != "enviado" or usuario_id != contrato["aguardando_id"]:
        raise RegraNegocio("Este contrato não está aguardando a sua resposta.")
    outro = outra_parte(contrato, usuario_id)
    with db:
        alterou = db.execute(
            """UPDATE contrato SET status = 'recusado', aguardando_id = NULL, encerrado_em = ?, motivo_encerramento = ?
                WHERE id = ? AND status = 'enviado' AND aguardando_id = ?""",
            (agora_utc_texto(), motivo, contrato["id"], usuario_id),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Este contrato não está mais aguardando resposta.")
        notificar(db, outro, "contrato", f"O contrato nº {contrato['id']} foi recusado.", _link(contrato["id"]))


def cancelar_contrato(db, contrato, usuario_id):
    """O autor descarta o rascunho (que é apagado, porque a outra parte nunca o viu), ou quem enviou a
    última versão retira a proposta antes da resposta (fica registrada como cancelada)."""
    if contrato["status"] == "rascunho" and usuario_id == contrato["autor_id"]:
        with db:
            db.execute("DELETE FROM contrato_item WHERE contrato_id = ?", (contrato["id"],))
            db.execute("DELETE FROM contrato WHERE id = ? AND status = 'rascunho'", (contrato["id"],))
        return "descartado"
    if not (contrato["status"] == "enviado" and usuario_id != contrato["aguardando_id"]):
        raise RegraNegocio("Este contrato não pode ser cancelado por você agora.")
    with db:
        alterou = db.execute(
            """UPDATE contrato SET status = 'cancelado', aguardando_id = NULL, encerrado_em = ?
                WHERE id = ? AND status = 'enviado'""",
            (agora_utc_texto(), contrato["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Este contrato já foi respondido.")
        notificar(
            db, outra_parte(contrato, usuario_id), "contrato",
            f"A proposta de contrato nº {contrato['id']} foi cancelada por quem enviou.", _link(contrato["id"]),
        )
    return "cancelado"


def rescindir_contrato(db, contrato, usuario_id, motivo):
    if contrato["status"] != "ativo":
        raise RegraNegocio("Só contratos ativos podem ser rescindidos.")
    motivo = (motivo or "").strip()
    if len(motivo) < 5:
        raise RegraNegocio("Explique o motivo da rescisão.")
    efetiva = hoje() + timedelta(days=contrato["aviso_previo_dias"])
    with db:
        alterou = db.execute(
            """UPDATE contrato SET status = 'rescindido', encerrado_em = ?, motivo_encerramento = ?, rescisao_efetiva_em = ?
                WHERE id = ? AND status = 'ativo'""",
            (agora_utc_texto(), motivo[:500], efetiva.isoformat(), contrato["id"]),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Este contrato já não está ativo.")
        notificar(
            db, outra_parte(contrato, usuario_id), "contrato",
            f"{_nome_da_parte(contrato, usuario_id)} rescindiu o contrato nº {contrato['id']}. "
            f"As entregas combinadas seguem até {efetiva.strftime('%d/%m/%Y')} (aviso prévio).",
            _link(contrato["id"]),
        )
    return efetiva


def encerrar_contratos_vencidos(db):
    """Contratos ativos cujo término passou viram 'encerrado'. Roda no início das páginas de contratos e do painel."""
    vencidos = db.execute(
        "SELECT id, produtor_id, comercio_id FROM contrato WHERE status = 'ativo' AND termino < ?", (hoje().isoformat(),)
    ).fetchall()
    if not vencidos:
        return 0
    with db:
        for contrato in vencidos:
            alterou = db.execute(
                "UPDATE contrato SET status = 'encerrado', encerrado_em = ?, motivo_encerramento = 'Fim da vigência' "
                "WHERE id = ? AND status = 'ativo'",
                (agora_utc_texto(), contrato["id"]),
            ).rowcount
            if alterou:
                for parte in (contrato["produtor_id"], contrato["comercio_id"]):
                    notificar(db, parte, "contrato", f"O contrato nº {contrato['id']} chegou ao fim da vigência.",
                              _link(contrato["id"]))
    return len(vencidos)


# ---------- parcerias públicas: "onde comprar" (RF36) ----------

def alterar_parceria(db, contrato, usuario_id, mostrar):
    if contrato["status"] != "ativo":
        raise RegraNegocio("Só contratos ativos podem ser mostrados como parceria.")
    coluna = "parceria_produtor" if usuario_id == contrato["produtor_id"] else "parceria_comercio"
    with db:
        db.execute(f"UPDATE contrato SET {coluna} = ? WHERE id = ? AND status = 'ativo'", (int(bool(mostrar)), contrato["id"]))


_PARCERIA = "c.status = 'ativo' AND c.parceria_produtor = 1 AND c.parceria_comercio = 1"


def lojas_parceiras_do_produtor(db, produtor_id):
    return db.execute(
        f"""SELECT DISTINCT pc.usuario_id, pc.nome_fantasia, m.nome AS municipio_nome, m.uf AS municipio_uf
              FROM contrato c JOIN perfil_comercio pc ON pc.usuario_id = c.comercio_id AND pc.status = 'ativo'
              JOIN municipio m ON m.codigo_ibge = pc.municipio_id
             WHERE c.produtor_id = ? AND {_PARCERIA} ORDER BY pc.nome_busca""",
        (produtor_id,),
    ).fetchall()


def fornecedores_da_loja(db, comercio_id):
    return db.execute(
        f"""SELECT DISTINCT pp.usuario_id, pp.nome_vitrine, m.nome AS municipio_nome, m.uf AS municipio_uf
              FROM contrato c JOIN perfil_produtor pp ON pp.usuario_id = c.produtor_id AND pp.status = 'ativo'
              JOIN municipio m ON m.codigo_ibge = pp.municipio_id
             WHERE c.comercio_id = ? AND {_PARCERIA} ORDER BY pp.nome_busca""",
        (comercio_id,),
    ).fetchall()


def lojas_que_vendem_o_produto(db, produto_id):
    return db.execute(
        f"""SELECT DISTINCT pc.usuario_id, pc.nome_fantasia, m.nome AS municipio_nome, m.uf AS municipio_uf
              FROM contrato_item i JOIN contrato c ON c.id = i.contrato_id
              JOIN perfil_comercio pc ON pc.usuario_id = c.comercio_id AND pc.status = 'ativo'
              JOIN municipio m ON m.codigo_ibge = pc.municipio_id
             WHERE i.produto_id = ? AND {_PARCERIA} ORDER BY pc.nome_busca""",
        (produto_id,),
    ).fetchall()
