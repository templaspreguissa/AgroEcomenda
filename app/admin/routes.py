"""Administração mínima (RF15, RF20, RF25, RF38): lojas, denúncias, conteúdo, usuários, categorias e registro.

Todas as rotas exigem papel 'admin'. Toda ação pede um motivo, que fica registrado em acao_moderacao.
"""
from flask import abort, flash, g, redirect, render_template, request, url_for

from ..auth.routes import admin_obrigatorio
from ..db import get_db
from ..servicos import conversas, moderacao
from ..servicos.comum import RegraNegocio
from . import bp


@bp.before_request
@admin_obrigatorio
def so_administracao():
    """Protege o blueprint inteiro: nenhuma rota nova fica aberta por esquecimento."""


def _motivo():
    return (request.form.get("motivo") or "").strip()


def _voltar(padrao):
    destino = request.form.get("voltar", "")
    return destino if destino.startswith("/") and not destino.startswith("//") else padrao


@bp.route("")
def painel():
    db = get_db()
    return render_template(
        "admin/painel.html", resumo=moderacao.resumo_do_painel(db), denuncias=moderacao.denuncias(db)[:5],
        lojas=moderacao.lojas(db)[:5],
    )


# ---------- lojas (RF38) ----------

@bp.route("/lojas")
def lojas():
    filtro = request.args.get("filtro") if request.args.get("filtro") in ("a_verificar", "verificadas", "todas") else "a_verificar"
    return render_template("admin/lojas.html", lojas=moderacao.lojas(get_db(), filtro), filtro=filtro)


@bp.route("/lojas/<int:usuario_id>/<any(verificar, remover):acao>", methods=["POST"])
def verificar_loja(usuario_id, acao):
    try:
        moderacao.verificar_loja(get_db(), g.usuario["id"], usuario_id, acao == "verificar", _motivo())
    except LookupError:
        abort(404)
    except RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Loja verificada." if acao == "verificar" else "Selo de verificada retirado.", "sucesso")
    return redirect(_voltar(url_for("admin.lojas")))


# ---------- denúncias (RF19) ----------

@bp.route("/denuncias")
def denuncias():
    resolvidas = request.args.get("resolvidas") == "1"
    return render_template("admin/denuncias.html", denuncias=moderacao.denuncias(get_db(), abertas=not resolvidas),
                           resolvidas=resolvidas, motivos=moderacao.MOTIVOS)


@bp.route("/denuncias/<int:denuncia_id>", methods=["GET", "POST"])
def denuncia(denuncia_id):
    db = get_db()
    atual = moderacao.buscar_denuncia(db, denuncia_id)
    if atual is None:
        abort(404)
    if request.method == "POST":
        decisao = request.form.get("decisao")
        if decisao not in ("procedente", "improcedente"):
            flash("Escolha se a denúncia procede ou não.", "erro")
        else:
            try:
                moderacao.resolver_denuncia(
                    db, g.usuario["id"], atual, decisao == "procedente", _motivo(),
                    ocultar=request.form.get("ocultar") == "1", bloquear=request.form.get("bloquear") == "1",
                )
            except RegraNegocio as erro:
                flash(str(erro), "erro")
            else:
                flash("Denúncia resolvida e decisão registrada.", "sucesso")
                return redirect(url_for("admin.denuncias"))
    resumo = moderacao.alvo(db, atual["alvo_tipo"], atual["alvo_id"])
    return render_template(
        "admin/denuncia.html", denuncia=atual, resumo=resumo, motivos=moderacao.MOTIVOS,
        outras=db.execute(
            "SELECT motivo, descricao, criada_em FROM denuncia WHERE alvo_tipo = ? AND alvo_id = ? AND id <> ? ORDER BY id",
            (atual["alvo_tipo"], atual["alvo_id"], denuncia_id),
        ).fetchall(),
    )


@bp.route("/conversas/<int:conversa_id>")
def conversa(conversa_id):
    """A administração só lê uma conversa que foi denunciada (como diz a Política de Privacidade)."""
    db = get_db()
    denunciada = db.execute(
        "SELECT 1 FROM denuncia WHERE alvo_tipo = 'conversa' AND alvo_id = ?", (conversa_id,)
    ).fetchone()
    linha = db.execute("SELECT * FROM conversa WHERE id = ?", (conversa_id,)).fetchone()
    if not denunciada or linha is None:
        abort(404)
    nomes = {u["id"]: u["nome"] for u in db.execute(
        "SELECT id, nome FROM usuario WHERE id IN (?, ?)", (linha["usuario_a_id"], linha["usuario_b_id"]))}
    titulo, link = conversas.assunto(db, linha["contexto_tipo"], linha["contexto_id"])
    return render_template("admin/conversa.html", conversa=linha, nomes=nomes, titulo=titulo, link=link,
                           mensagens=conversas.mensagens_da_conversa(db, conversa_id))


# ---------- conteúdo ----------

@bp.route("/conteudo/<any(produto, vitrine, loja, encomenda):tipo>/<int:alvo_id>/<any(ocultar, reativar):acao>",
          methods=["POST"])
def conteudo(tipo, alvo_id, acao):
    try:
        if acao == "ocultar":
            moderacao.ocultar_conteudo(get_db(), g.usuario["id"], tipo, alvo_id, _motivo())
        else:
            moderacao.reativar_conteudo(get_db(), g.usuario["id"], tipo, alvo_id, _motivo())
    except LookupError:
        abort(404)
    except RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Conteúdo ocultado. O dono foi avisado." if acao == "ocultar" else "Conteúdo visível de novo.", "info")
    return redirect(_voltar(url_for("admin.painel")))


# ---------- usuários (RF25) ----------

@bp.route("/usuarios")
def usuarios():
    termo = (request.args.get("q") or "").strip()[:100]
    return render_template("admin/usuarios.html", usuarios=moderacao.buscar_usuarios(get_db(), termo), termo=termo)


@bp.route("/usuarios/<int:usuario_id>/<any(bloquear, desbloquear):acao>", methods=["POST"])
def usuario(usuario_id, acao):
    try:
        if acao == "bloquear":
            moderacao.bloquear_usuario(get_db(), g.usuario["id"], usuario_id, _motivo())
        else:
            moderacao.desbloquear_usuario(get_db(), g.usuario["id"], usuario_id, _motivo())
    except LookupError:
        abort(404)
    except RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Conta bloqueada. A sessão dela foi encerrada." if acao == "bloquear" else "Conta desbloqueada.", "info")
    return redirect(_voltar(url_for("admin.usuarios")))


# ---------- categorias e unidades (RF20) ----------

@bp.route("/categorias", methods=["GET", "POST"])
def categorias():
    db = get_db()
    if request.method == "POST":
        try:
            if request.form.get("acao") == "categoria":
                moderacao.criar_categoria(db, g.usuario["id"], request.form.get("nome"), request.form.get("pai_id", type=int))
                flash("Subcategoria criada.", "sucesso")
            elif request.form.get("acao") == "unidade":
                moderacao.criar_unidade(db, g.usuario["id"], request.form.get("sigla"), request.form.get("nome"))
                flash("Unidade criada.", "sucesso")
            elif request.form.get("acao") in ("ativar", "desativar"):
                moderacao.alternar_categoria(db, g.usuario["id"], request.form.get("categoria_id", type=int),
                                             request.form.get("acao") == "ativar", _motivo())
                flash("Categoria atualizada.", "sucesso")
        except LookupError:
            abort(404)
        except RegraNegocio as erro:
            flash(str(erro), "erro")
        return redirect(url_for("admin.categorias"))
    linhas = db.execute(
        """SELECT c.id, c.nome, c.ativa, c.categoria_pai_id,
                  (SELECT COUNT(*) FROM produto p WHERE p.categoria_id = c.id) AS produtos
             FROM categoria c ORDER BY COALESCE(c.categoria_pai_id, c.id), c.categoria_pai_id IS NOT NULL, c.nome"""
    ).fetchall()
    return render_template(
        "admin/categorias.html", categorias=linhas,
        principais=[c for c in linhas if c["categoria_pai_id"] is None],
        unidades=db.execute("SELECT id, sigla, nome FROM unidade_medida ORDER BY id").fetchall(),
    )


# ---------- registro (RNF12) ----------

@bp.route("/registro")
def registro():
    return render_template("admin/registro.html", acoes=moderacao.registro(get_db()))
