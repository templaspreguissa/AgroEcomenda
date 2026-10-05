"""Páginas públicas e painel do usuário."""
from flask import g, render_template

from ..auth.routes import login_obrigatorio
from ..db import get_db
from . import bp


def categorias_com_subcategorias():
    linhas = get_db().execute(
        "SELECT id, categoria_pai_id, nome FROM categoria WHERE ativa = 1 ORDER BY categoria_pai_id, nome"
    ).fetchall()
    principais = [dict(linha, subcategorias=[]) for linha in linhas if linha["categoria_pai_id"] is None]
    por_id = {categoria["id"]: categoria for categoria in principais}
    for linha in linhas:
        pai = por_id.get(linha["categoria_pai_id"])
        if pai is not None:
            pai["subcategorias"].append(linha["nome"])
    return sorted(principais, key=lambda categoria: categoria["id"])


@bp.route("/")
def index():
    return render_template("main/index.html", categorias=categorias_com_subcategorias())


@bp.route("/termos")
def termos():
    return render_template("main/termos.html")


@bp.route("/privacidade")
def privacidade():
    return render_template("main/privacidade.html")


@bp.route("/painel")
@login_obrigatorio
def painel():
    return render_template("main/painel.html", usuario=g.usuario)
