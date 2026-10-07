"""Mensagens entre produtor, loja e consumidor (RF33) e avisos do sistema (RF13, RF37)."""
from math import ceil

from flask import abort, flash, g, redirect, render_template, request, url_for
from wtforms import HiddenField, TextAreaField
from wtforms.validators import DataRequired, Length

from .. import servicos
from ..auth.routes import carregar_usuario, destino_seguro, login_obrigatorio
from ..db import get_db
from ..formularios import Formulario, texto_limpo
from ..servicos.conversas import CONTEXTOS, TAMANHO_MAXIMO, AssuntoInexistente, SoProdutores, nome_publico
from . import bp

AVISOS_POR_PAGINA = 30


class MensagemForm(Formulario):
    texto = TextAreaField(
        "Mensagem",
        filters=[texto_limpo],
        validators=[
            DataRequired("Escreva a mensagem."),
            Length(max=TAMANHO_MAXIMO, message=f"Use no máximo {TAMANHO_MAXIMO} caracteres."),
        ],
    )


class NovaConversaForm(MensagemForm):
    sobre = HiddenField()
    id = HiddenField()


def _assunto_da_requisicao(fonte):
    """Lê ?sobre=produto&id=3 (ou os campos ocultos do formulário). Assunto inválido vira 404."""
    tipo = fonte.get("sobre", "")
    contexto_id = fonte.get("id", "")
    if tipo not in CONTEXTOS or not contexto_id.isdigit():
        abort(404)
    return tipo, int(contexto_id)


# ---------- mensagens ----------

@bp.route("/mensagens")
@login_obrigatorio
def caixa():
    db = get_db()
    conversas = servicos.conversas.conversas_do_usuario(db, g.usuario["id"])
    assuntos = {c["id"]: servicos.conversas.assunto(db, c["contexto_tipo"], c["contexto_id"])[0] for c in conversas}
    return render_template("comunicacao/caixa.html", conversas=conversas, assuntos=assuntos, nome_publico=nome_publico)


@bp.route("/mensagens/nova", methods=["GET", "POST"])
@login_obrigatorio
def nova():
    """Começar conversa sobre um assunto. Se ela já existe, vai direto para ela."""
    db = get_db()
    tipo, contexto_id = _assunto_da_requisicao(request.args if request.method == "GET" else request.form)
    try:
        outro = servicos.conversas.destinatario(db, tipo, contexto_id, g.usuario["id"], bool(g.usuario["tem_produtor"]))
    except AssuntoInexistente:
        abort(404)
    except SoProdutores:
        return render_template("perfis/so_produtores.html"), 403
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
        return redirect(servicos.conversas.assunto(db, tipo, contexto_id)[1])

    existente = servicos.conversas.conversa_existente(db, tipo, contexto_id, g.usuario["id"], outro)
    if existente and request.method == "GET":
        return redirect(url_for("comunicacao.conversa", conversa_id=existente))

    form = NovaConversaForm()
    if request.method == "GET":
        form.sobre.data, form.id.data = tipo, str(contexto_id)
    if form.validate_on_submit():
        try:
            conversa_id = servicos.conversas.iniciar_conversa(db, tipo, contexto_id, g.usuario, form.texto.data)
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            flash("Mensagem enviada.", "sucesso")
            return redirect(url_for("comunicacao.conversa", conversa_id=conversa_id))

    pessoa = db.execute(
        """SELECT u.nome, pp.nome_vitrine, pc.nome_fantasia FROM usuario u
             LEFT JOIN perfil_produtor pp ON pp.usuario_id = u.id
             LEFT JOIN perfil_comercio pc ON pc.usuario_id = u.id WHERE u.id = ?""",
        (outro,),
    ).fetchone()
    titulo, link = servicos.conversas.assunto(db, tipo, contexto_id)
    return render_template(
        "comunicacao/nova.html", form=form, titulo=titulo, link=link,
        destinatario=nome_publico(pessoa["nome"], pessoa["nome_vitrine"], pessoa["nome_fantasia"]),
    )


@bp.route("/mensagens/<int:conversa_id>", methods=["GET", "POST"])
@login_obrigatorio
def conversa(conversa_id):
    db = get_db()
    atual = servicos.conversas.buscar_conversa(db, conversa_id, g.usuario["id"])
    if atual is None:
        abort(404)  # quem não participa nem fica sabendo que a conversa existe
    form = MensagemForm()
    if form.validate_on_submit():
        try:
            servicos.conversas.responder(db, atual, g.usuario["id"], form.texto.data)
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            return redirect(url_for("comunicacao.conversa", conversa_id=conversa_id, _anchor="ultima"))
    servicos.conversas.marcar_lidas(db, conversa_id, g.usuario["id"])
    carregar_usuario()  # atualiza o contador de mensagens do topo, que foi calculado antes de marcar como lidas
    titulo, link = servicos.conversas.assunto(db, atual["contexto_tipo"], atual["contexto_id"])
    return render_template(
        "comunicacao/conversa.html", conversa=atual, form=form, titulo=titulo, link=link,
        mensagens=servicos.conversas.mensagens_da_conversa(db, conversa_id),
        outro=nome_publico(atual["outro_nome"], atual["outro_vitrine"], atual["outro_loja"]),
    )


# ---------- avisos ----------

@bp.route("/avisos")
@login_obrigatorio
def avisos():
    db = get_db()
    total = servicos.total_de_avisos(db, g.usuario["id"])
    paginas = max(ceil(total / AVISOS_POR_PAGINA), 1)
    pagina = min(max(request.args.get("pagina", 1, type=int), 1), paginas)
    lista = servicos.avisos_do_usuario(db, g.usuario["id"], AVISOS_POR_PAGINA, (pagina - 1) * AVISOS_POR_PAGINA)
    return render_template("comunicacao/avisos.html", avisos=lista, total=total, pagina=pagina, paginas=paginas)


@bp.route("/avisos/<int:aviso_id>")
@login_obrigatorio
def abrir_aviso(aviso_id):
    link = servicos.abrir_aviso(get_db(), aviso_id, g.usuario["id"])
    if link is None:
        abort(404)
    return redirect(destino_seguro(link) or url_for("comunicacao.avisos"))


@bp.route("/avisos/lidos", methods=["POST"])
@login_obrigatorio
def marcar_lidos():
    marcados = servicos.marcar_todos_lidos(get_db(), g.usuario["id"])
    flash("Todos os avisos foram marcados como lidos." if marcados else "Não havia avisos novos.", "info")
    return redirect(url_for("comunicacao.avisos"))
