"""Encomendas (pedidos de compra) e propostas dos vendedores."""
from datetime import date
from math import ceil

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from .. import servicos
from ..auth.routes import login_obrigatorio
from ..db import get_db
from ..formularios import escolhas_categorias
from ..localidades import municipios_para_lista, rotulo_do_codigo, ufs_carregadas
from ..util import formatar_numero, hoje, normalizar_busca
from . import bp
from .forms import EncomendaForm, PropostaForm

ORDENACOES = {
    "prazo": ("Prazo mais próximo", "e.prazo_limite ASC, e.id DESC"),
    "recentes": ("Mais recentes", "e.criado_em DESC, e.id DESC"),
}


@bp.before_request
def encerrar_vencidas():
    servicos.expirar_encomendas_vencidas(get_db())


def _encomenda_ou_404(encomenda_id):
    encomenda = servicos.buscar_encomenda(get_db(), encomenda_id)
    if encomenda is None:
        abort(404)
    return encomenda


def _proposta_ou_404(proposta_id):
    proposta = servicos.buscar_proposta(get_db(), proposta_id)
    if proposta is None or proposta["encomenda_id"] is None:
        abort(404)
    return proposta


def _data(texto):
    return date.fromisoformat(texto) if texto else None


def _reais_para_campo(centavos):
    return f"{centavos // 100},{centavos % 100:02d}"


def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------- lista e busca (RF08: listar encomendas) ----------

@bp.route("/encomendas")
def lista():
    db = get_db()
    termo = (request.args.get("q") or "").strip()[:100]
    categoria = request.args.get("categoria", type=int)
    uf = (request.args.get("uf") or "").upper()[:2]
    ordem = request.args.get("ordem") if request.args.get("ordem") in ORDENACOES else "prazo"
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    por_pagina = current_app.config["ITENS_POR_PAGINA"]

    condicoes = ["e.status IN ('aberta', 'em_negociacao')", "e.prazo_limite >= ?"]
    parametros = [hoje().isoformat()]
    for palavra in normalizar_busca(termo).split():
        condicoes.append("e.titulo_busca LIKE ? ESCAPE '\\'")
        parametros.append(f"%{_escapar_like(palavra)}%")
    if categoria:
        condicoes.append("(e.categoria_id = ? OR c.categoria_pai_id = ?)")
        parametros += [categoria, categoria]
    if uf:
        condicoes.append("m.uf = ?")
        parametros.append(uf)
    onde = " AND ".join(condicoes)
    base = """FROM encomenda e
              JOIN unidade_medida u ON u.id = e.unidade_id
              JOIN municipio m      ON m.codigo_ibge = e.municipio_entrega_id
              JOIN categoria c      ON c.id = e.categoria_id
              JOIN usuario us       ON us.id = e.comprador_id"""

    total = db.execute(f"SELECT COUNT(*) {base} WHERE {onde}", parametros).fetchone()[0]
    paginas = max(ceil(total / por_pagina), 1)
    pagina = min(pagina, paginas)
    encomendas = db.execute(
        f"""SELECT e.id, e.titulo, e.quantidade, e.prazo_limite, e.transporte, e.status, e.comprador_id,
                   u.sigla AS unidade_sigla, m.nome AS municipio_nome, m.uf AS municipio_uf,
                   c.nome AS categoria_nome, us.nome AS comprador_nome,
                   (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id AND p.status = 'pendente') AS propostas_pendentes
              {base} WHERE {onde}
             ORDER BY {ORDENACOES[ordem][1]} LIMIT ? OFFSET ?""",
        parametros + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()

    filtros_ativos = bool(termo or categoria or uf)
    return render_template(
        "encomendas/lista.html",
        encomendas=encomendas, total=total, pagina=pagina, paginas=paginas,
        inicio=(pagina - 1) * por_pagina + 1 if total else 0, fim=(pagina - 1) * por_pagina + len(encomendas),
        termo=termo, categoria=categoria, uf=uf, ordem=ordem, ordenacoes=ORDENACOES,
        categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"), ufs=ufs_carregadas(db),
        filtros_ativos=filtros_ativos,
    )


# ---------- publicar, editar e cancelar (RF07, RF16) ----------

@bp.route("/encomendas/nova", methods=["GET", "POST"])
@login_obrigatorio
def nova():
    db = get_db()
    form = EncomendaForm()
    if request.method == "GET":
        form.municipio.data = rotulo_do_codigo(db, _municipio_do_usuario(db))
    if form.validate_on_submit():
        try:
            encomenda_id = servicos.criar_encomenda(db, g.usuario["id"], form.dados())
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Encomenda publicada. Agora é só aguardar as propostas.", "sucesso")
            return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))
    return render_template("encomendas/form.html", form=form, municipios=municipios_para_lista(db), editando=False)


def _municipio_do_usuario(db):
    linha = db.execute("SELECT municipio_id FROM usuario WHERE id = ?", (g.usuario["id"],)).fetchone()
    return linha["municipio_id"] if linha else None


@bp.route("/encomendas/<int:encomenda_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar(encomenda_id):
    db = get_db()
    encomenda = _encomenda_ou_404(encomenda_id)
    if encomenda["comprador_id"] != g.usuario["id"]:
        abort(403)
    if not servicos.pode_editar_encomenda(encomenda, g.usuario["id"]):
        flash("Só é possível editar encomendas abertas que ainda não receberam propostas.", "erro")
        return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))

    form = EncomendaForm()
    if request.method == "GET":
        form.titulo.data = encomenda["titulo"]
        form.categoria_id.data = encomenda["categoria_id"]
        form.descricao.data = encomenda["descricao"]
        form.quantidade.data = formatar_numero(encomenda["quantidade"])
        form.unidade_id.data = encomenda["unidade_id"]
        form.municipio.data = rotulo_do_codigo(db, encomenda["municipio_entrega_id"])
        form.prazo_limite.data = _data(encomenda["prazo_limite"])
        form.transporte.data = encomenda["transporte"]
        form.condicoes_pagamento.data = encomenda["condicoes_pagamento"]
    if form.validate_on_submit():
        try:
            servicos.editar_encomenda(db, encomenda, g.usuario["id"], form.dados())
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Encomenda atualizada.", "sucesso")
            return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))
    return render_template(
        "encomendas/form.html", form=form, municipios=municipios_para_lista(db), editando=True, encomenda=encomenda
    )


@bp.route("/encomendas/<int:encomenda_id>/cancelar", methods=["POST"])
@login_obrigatorio
def cancelar(encomenda_id):
    encomenda = _encomenda_ou_404(encomenda_id)
    try:
        servicos.cancelar_encomenda(get_db(), encomenda, g.usuario["id"])
    except PermissionError:
        abort(403)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Encomenda cancelada. Os vendedores com proposta foram avisados.", "info")
    return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))


# ---------- detalhe ----------

@bp.route("/encomendas/<int:encomenda_id>")
def detalhe(encomenda_id):
    db = get_db()
    encomenda = _encomenda_ou_404(encomenda_id)
    usuario_id = g.usuario["id"] if g.usuario else None
    sou_comprador = usuario_id == encomenda["comprador_id"]

    if sou_comprador:
        propostas = servicos.propostas_da_encomenda(db, encomenda_id)
    elif usuario_id:
        # O vendedor só vê as próprias propostas.
        propostas = [p for p in servicos.propostas_da_encomenda(db, encomenda_id) if p["vendedor_id"] == usuario_id]
    else:
        propostas = []
    aceita = next((p for p in propostas if p["status"] == "aceita"), None)
    minha_pendente = next((p for p in propostas if p["status"] == "pendente" and p["vendedor_id"] == usuario_id), None)
    ativa = encomenda["status"] in servicos.STATUS_ENCOMENDA_ATIVA and encomenda["prazo_limite"] >= hoje().isoformat()

    return render_template(
        "encomendas/detalhe.html",
        encomenda=encomenda, propostas=propostas, aceita=aceita, minha_pendente=minha_pendente,
        sou_comprador=sou_comprador, ativa=ativa,
        pode_editar=sou_comprador and servicos.pode_editar_encomenda(encomenda, usuario_id),
        pode_propor=bool(usuario_id) and not sou_comprador and ativa and minha_pendente is None,
    )


# ---------- propostas (RF08, RF09, RF24) ----------

@bp.route("/encomendas/<int:encomenda_id>/proposta", methods=["GET", "POST"])
@login_obrigatorio
def proposta(encomenda_id):
    """Envia uma proposta ou edita a proposta pendente do próprio vendedor."""
    db = get_db()
    encomenda = _encomenda_ou_404(encomenda_id)
    if encomenda["comprador_id"] == g.usuario["id"]:
        flash("Você não pode enviar proposta para a sua própria encomenda.", "erro")
        return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))
    existente = servicos.proposta_pendente_do_vendedor(db, encomenda_id, g.usuario["id"])

    form = PropostaForm()
    if request.method == "GET":
        if existente:
            form.preco.data = _reais_para_campo(existente["preco_unitario_centavos"])
            form.quantidade.data = formatar_numero(existente["quantidade"])
            form.prazo_entrega.data = _data(existente["prazo_entrega"])
            form.transporte.data = existente["transporte"]
            form.validade.data = _data(existente["validade"])
            form.observacao.data = existente["observacao"]
        else:
            form.quantidade.data = formatar_numero(encomenda["quantidade"])
            form.transporte.data = encomenda["transporte"]
    if form.validate_on_submit():
        try:
            if existente:
                servicos.editar_proposta(db, existente, encomenda, g.usuario["id"], form.dados())
                flash("Proposta atualizada.", "sucesso")
            else:
                servicos.enviar_proposta(db, encomenda, g.usuario["id"], form.dados())
                flash("Proposta enviada. O comprador foi avisado.", "sucesso")
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda_id))
    return render_template("encomendas/proposta_form.html", form=form, encomenda=encomenda, existente=existente)


@bp.route("/propostas/<int:proposta_id>/retirar", methods=["POST"])
@login_obrigatorio
def retirar(proposta_id):
    proposta = _proposta_ou_404(proposta_id)
    try:
        servicos.retirar_proposta(get_db(), proposta, g.usuario["id"])
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Proposta retirada.", "info")
    return redirect(url_for("encomendas.detalhe", encomenda_id=proposta["encomenda_id"]))


def _responder(proposta_id, acao):
    proposta = _proposta_ou_404(proposta_id)
    encomenda = _encomenda_ou_404(proposta["encomenda_id"])
    try:
        acao(get_db(), proposta, encomenda, g.usuario["id"])
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
        return None, encomenda
    return proposta, encomenda


@bp.route("/propostas/<int:proposta_id>/aceitar", methods=["POST"])
@login_obrigatorio
def aceitar(proposta_id):
    proposta, encomenda = _responder(proposta_id, servicos.aceitar_proposta)
    if proposta:
        flash("Proposta aceita. A encomenda foi concluída e os demais vendedores foram avisados.", "sucesso")
    return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda["id"]))


@bp.route("/propostas/<int:proposta_id>/recusar", methods=["POST"])
@login_obrigatorio
def recusar(proposta_id):
    proposta, encomenda = _responder(proposta_id, servicos.recusar_proposta)
    if proposta:
        flash("Proposta recusada. O vendedor foi avisado.", "info")
    return redirect(url_for("encomendas.detalhe", encomenda_id=encomenda["id"]))
