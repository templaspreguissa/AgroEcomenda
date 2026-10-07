"""Contratos de fornecimento (RF34–RF36): propor, negociar versões, aceitar, imprimir, rescindir e parcerias."""
from datetime import date, timedelta
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, render_template, request, url_for

from .. import servicos
from ..auth.routes import destino_seguro, login_obrigatorio
from ..db import get_db
from ..localidades import municipios_para_lista, rotulo_do_codigo
from ..servicos import contratos
from ..servicos.comum import RegraNegocio
from ..util import agora_utc_texto, formatar_numero, hoje
from . import bp
from .forms import ContratoForm

DURACAO_SUGERIDA = timedelta(days=182)  # seis meses


@bp.before_request
def encerrar_vencidos():
    contratos.encerrar_contratos_vencidos(get_db())


def _contrato_ou_404(contrato_id):
    contrato = contratos.buscar_contrato(get_db(), contrato_id, g.usuario["id"])
    if contrato is None:
        abort(404)  # quem não é parte nem fica sabendo que o contrato existe
    return contrato


def _voltar():
    """Volta para a página de onde a pessoa veio, se for deste site; senão, para o painel."""
    origem = urlsplit(request.referrer or "")
    caminho = origem.path + (f"?{origem.query}" if origem.query else "")
    mesmo_site = origem.netloc in ("", request.host)
    return (destino_seguro(caminho) if mesmo_site else None) or url_for("main.painel")


def _reais_para_campo(centavos):
    return f"{centavos // 100},{centavos % 100:02d}" if centavos else ""


# ---------- lista ----------

@bp.route("/contratos")
@login_obrigatorio
def lista():
    return render_template("contratos/lista.html", contratos=contratos.contratos_do_usuario(get_db(), g.usuario["id"]))


# ---------- propor ----------

def _origem():
    """Quem é o produtor, quem é o comércio e o que já dá para preencher, a partir de onde a pessoa veio.

    ?loja=<id>      um produtor propõe a uma loja (página da loja)
    ?produto=<id>   uma loja propõe ao produtor daquele produto (página do produto)
    ?proposta=<id>  uma das partes transforma uma proposta aceita em contrato
    """
    db = get_db()
    eu = g.usuario["id"]
    sugestao = {"itens": []}
    if request.args.get("proposta", type=int):
        proposta = servicos.buscar_proposta(db, request.args.get("proposta", type=int))
        if proposta is None or eu not in (proposta["comprador_id"], proposta["vendedor_id"]):
            abort(404)
        if proposta["status"] != "aceita":
            raise RegraNegocio("Só uma proposta aceita pode virar contrato.")
        produtor, comercio = proposta["vendedor_id"], proposta["comprador_id"]
        titulo = db.execute(
            "SELECT COALESCE(e.titulo, pd.titulo) FROM proposta p LEFT JOIN encomenda e ON e.id = p.encomenda_id "
            "LEFT JOIN produto pd ON pd.id = p.produto_id WHERE p.id = ?", (proposta["id"],),
        ).fetchone()[0]
        sugestao.update(transporte=proposta["transporte"], origem_proposta_id=proposta["id"])
        sugestao["itens"].append({
            "produto_id": proposta["produto_id"], "descricao": titulo, "quantidade": proposta["quantidade"],
            "unidade_id": proposta["unidade_id"], "preco": proposta["preco_unitario_centavos"],
        })
    elif request.args.get("produto", type=int):
        produto = servicos.buscar_produto(db, request.args.get("produto", type=int))
        if produto is None or produto["status"] == "oculto":
            abort(404)
        if not g.usuario["tem_comercio"]:
            raise RegraNegocio("Para propor um contrato de fornecimento, cadastre primeiro a sua loja.")
        produtor, comercio = produto["vendedor_id"], eu
        verificado = bool(g.usuario["comercio_verificado"])
        preco = produto["preco_lojista_centavos"] if produto["para_lojista"] and (
            not produto["so_verificados"] or verificado) else None
        sugestao["itens"].append({
            "produto_id": produto["id"], "descricao": produto["titulo"], "quantidade": produto["pedido_minimo_lojista"],
            "unidade_id": produto["unidade_id"], "preco": preco,
        })
    elif request.args.get("loja", type=int):
        if not g.usuario["tem_produtor"]:
            raise RegraNegocio("Para propor um contrato de fornecimento a uma loja, crie primeiro a sua vitrine.")
        produtor, comercio = eu, request.args.get("loja", type=int)
    else:
        abort(404)
    contratos.conferir_partes(db, produtor, comercio)
    return produtor, comercio, sugestao


def _preencher(db, form, sugestao, comercio_id):
    form.inicio.data = hoje()
    form.termino.data = hoje() + DURACAO_SUGERIDA
    if sugestao.get("transporte"):
        form.transporte.data = sugestao["transporte"]
    municipio = db.execute("SELECT municipio_id FROM perfil_comercio WHERE usuario_id = ?", (comercio_id,)).fetchone()
    form.municipio_entrega.data = rotulo_do_codigo(db, municipio["municipio_id"] if municipio else None)
    for linha, item in zip(form.itens, sugestao["itens"]):
        linha.produto_id.data = item["produto_id"]
        linha.descricao.data = item["descricao"]
        linha.quantidade.data = formatar_numero(item["quantidade"]) if item["quantidade"] else ""
        linha.unidade_id.data = item["unidade_id"]
        linha.preco.data = _reais_para_campo(item["preco"])


def _nomes_das_partes(db, produtor_id, comercio_id):
    return db.execute(
        """SELECT pp.nome_vitrine, pc.nome_fantasia FROM perfil_produtor pp, perfil_comercio pc
            WHERE pp.usuario_id = ? AND pc.usuario_id = ?""",
        (produtor_id, comercio_id),
    ).fetchone()


@bp.route("/contratos/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo():
    db = get_db()
    try:
        produtor, comercio, sugestao = _origem()
    except RegraNegocio as erro:
        flash(str(erro), "erro")
        return redirect(_voltar())
    form = ContratoForm(produtor)
    if request.method == "GET":
        _preencher(db, form, sugestao, comercio)
    if form.validate_on_submit():
        try:
            contrato_id = contratos.criar_contrato(
                db, g.usuario["id"], produtor, comercio, form.termos(), form.lista_de_itens(),
                sugestao.get("origem_proposta_id"),
            )
        except RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Rascunho salvo. Confira os termos e envie para a outra parte.", "sucesso")
            return redirect(url_for("contratos.detalhe", contrato_id=contrato_id))
    return render_template(
        "contratos/form.html", form=form, contrato=None, partes=_nomes_das_partes(db, produtor, comercio),
        municipios=municipios_para_lista(db), acao=request.full_path,
    )


@bp.route("/contratos/<int:contrato_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar(contrato_id):
    db = get_db()
    contrato = _contrato_ou_404(contrato_id)
    pode_editar = (contrato["status"] == "rascunho" and contrato["autor_id"] == g.usuario["id"]) or (
        contrato["status"] == "enviado" and contrato["aguardando_id"] == g.usuario["id"])
    if not pode_editar:
        flash("Este contrato não pode ser alterado por você agora.", "erro")
        return redirect(url_for("contratos.detalhe", contrato_id=contrato_id))
    form = ContratoForm(contrato["produtor_id"])
    if request.method == "GET":
        for campo in ("frequencia", "dia_entrega", "transporte", "local_entrega", "condicoes_pagamento",
                      "padrao_qualidade", "reajuste", "aviso_previo_dias", "observacoes"):
            getattr(form, campo).data = contrato[campo]
        form.inicio.data = date.fromisoformat(contrato["inicio"])
        form.termino.data = date.fromisoformat(contrato["termino"])
        form.municipio_entrega.data = rotulo_do_codigo(db, contrato["municipio_entrega_id"])
        itens = contratos.itens_do_contrato(db, contrato_id)
        _preencher_itens(form, itens)
    if form.validate_on_submit():
        try:
            contratos.editar_contrato(db, contrato, g.usuario["id"], form.termos(), form.lista_de_itens())
        except PermissionError:
            abort(404)
        except RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Alterações enviadas para a outra parte." if contrato["status"] == "enviado" else "Rascunho salvo.",
                  "sucesso")
            return redirect(url_for("contratos.detalhe", contrato_id=contrato_id))
    return render_template(
        "contratos/form.html", form=form, contrato=contrato,
        partes={"nome_vitrine": contrato["produtor_vitrine"], "nome_fantasia": contrato["comercio_loja"]},
        municipios=municipios_para_lista(db), acao=url_for("contratos.editar", contrato_id=contrato_id),
    )


def _preencher_itens(form, itens):
    for linha, item in zip(form.itens, itens):
        linha.produto_id.data = item["produto_id"]
        linha.descricao.data = item["descricao"]
        linha.quantidade.data = formatar_numero(item["quantidade_por_entrega"])
        linha.unidade_id.data = item["unidade_id"]
        linha.preco.data = _reais_para_campo(item["preco_unitario_centavos"])


# ---------- detalhe e impressão ----------

def _contexto_do_contrato(db, contrato):
    versao = contratos.versao_atual(db, contrato)
    return {
        "contrato": contrato,
        "itens": contratos.itens_do_contrato(db, contrato["id"]),
        "versoes": contratos.versoes_do_contrato(db, contrato["id"]),
        "aceites": contratos.aceites_do_contrato(db, contrato["id"]),
        "versao": versao,
        "integridade": contratos.integridade_ok(versao) if versao else None,
        "sou_produtor": g.usuario["id"] == contrato["produtor_id"],
    }


@bp.route("/contratos/<int:contrato_id>")
@login_obrigatorio
def detalhe(contrato_id):
    contrato = _contrato_ou_404(contrato_id)
    return render_template("contratos/detalhe.html", **_contexto_do_contrato(get_db(), contrato))


@bp.route("/contratos/<int:contrato_id>/imprimir")
@login_obrigatorio
def imprimir(contrato_id):
    contrato = _contrato_ou_404(contrato_id)
    return render_template("contratos/imprimir.html", agora=agora_utc_texto(), **_contexto_do_contrato(get_db(), contrato))


# ---------- ações ----------

ACOES = {
    "enviar": ("Contrato enviado. A outra parte foi avisada.", "sucesso"),
    "aceitar": ("Contrato aceito pelas duas partes. Ele está ativo.", "sucesso"),
    "recusar": ("Contrato recusado. A outra parte foi avisada.", "info"),
    "cancelar": ("Contrato cancelado.", "info"),
    "rescindir": ("Contrato rescindido. A outra parte foi avisada.", "info"),
}


@bp.route("/contratos/<int:contrato_id>/<any(enviar, aceitar, recusar, cancelar, rescindir):acao>", methods=["POST"])
@login_obrigatorio
def agir(contrato_id, acao):
    db = get_db()
    contrato = _contrato_ou_404(contrato_id)
    usuario = g.usuario["id"]
    try:
        if acao == "enviar":
            contratos.enviar_contrato(db, contrato, usuario)
        elif acao == "aceitar":
            contratos.aceitar_contrato(db, contrato, usuario, request.form.get("hash", ""))
        elif acao == "recusar":
            contratos.recusar_contrato(db, contrato, usuario, (request.form.get("motivo") or "").strip()[:500])
        elif acao == "cancelar":
            if contratos.cancelar_contrato(db, contrato, usuario) == "descartado":
                flash("Rascunho descartado.", "info")
                return redirect(url_for("contratos.lista"))
        else:
            contratos.rescindir_contrato(db, contrato, usuario, request.form.get("motivo"))
    except RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash(*ACOES[acao])
    return redirect(url_for("contratos.detalhe", contrato_id=contrato_id))


@bp.route("/contratos/<int:contrato_id>/parceria", methods=["POST"])
@login_obrigatorio
def parceria(contrato_id):
    contrato = _contrato_ou_404(contrato_id)
    mostrar = request.form.get("mostrar") == "1"
    try:
        contratos.alterar_parceria(get_db(), contrato, g.usuario["id"], mostrar)
    except RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Pronto. A parceria aparece quando as duas partes autorizam." if mostrar
              else "A parceria deixou de aparecer publicamente.", "info")
    return redirect(url_for("contratos.detalhe", contrato_id=contrato_id))
