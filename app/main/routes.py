"""Páginas públicas e painel do usuário."""
from flask import g, render_template

from .. import servicos
from ..auth.routes import login_obrigatorio
from ..db import get_db
from ..perfis import dados as perfis
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
    recentes = get_db().execute(
        servicos.SQL_ANUNCIO + " WHERE a.status = 'ativo' ORDER BY a.criado_em DESC, a.id DESC LIMIT 6"
    ).fetchall()
    return render_template("main/index.html", categorias=categorias_com_subcategorias(), anuncios_recentes=recentes)


@bp.route("/termos")
def termos():
    return render_template("main/termos.html")


@bp.route("/privacidade")
def privacidade():
    return render_template("main/privacidade.html")


@bp.route("/painel")
@login_obrigatorio
def painel():
    db = get_db()
    servicos.expirar_encomendas_vencidas(db)
    usuario_id = g.usuario["id"]
    minhas_encomendas = db.execute(
        """SELECT e.id, e.titulo, e.status, e.prazo_limite, e.quantidade, u.sigla AS unidade_sigla,
                  (SELECT COUNT(*) FROM proposta p WHERE p.encomenda_id = e.id AND p.status = 'pendente') AS pendentes
             FROM encomenda e JOIN unidade_medida u ON u.id = e.unidade_id
            WHERE e.comprador_id = ?
            ORDER BY CASE WHEN e.status IN ('aberta', 'em_negociacao') THEN 0 ELSE 1 END, e.prazo_limite, e.id DESC""",
        (usuario_id,),
    ).fetchall()
    # Propostas que o usuário fez: como vendedor (em encomendas) ou como comprador (em anúncios).
    propostas_enviadas = db.execute(
        """SELECT p.id, p.status, p.preco_unitario_centavos, p.quantidade, p.prazo_entrega, u.sigla AS unidade_sigla,
                  p.encomenda_id, p.anuncio_id, COALESCE(e.titulo, a.titulo) AS titulo
             FROM proposta p
             LEFT JOIN encomenda e ON e.id = p.encomenda_id
             LEFT JOIN anuncio a   ON a.id = p.anuncio_id
             JOIN unidade_medida u ON u.id = p.unidade_id
            WHERE p.autor_id = ?
            ORDER BY CASE p.status WHEN 'pendente' THEN 0 WHEN 'aceita' THEN 1 ELSE 2 END, p.criado_em DESC""",
        (usuario_id,),
    ).fetchall()
    meus_anuncios = db.execute(
        """SELECT a.id, a.titulo, a.status, a.preco_centavos, u.sigla AS unidade_sigla,
                  (SELECT COUNT(*) FROM proposta p WHERE p.anuncio_id = a.id AND p.status = 'pendente') AS pendentes
             FROM anuncio a JOIN unidade_medida u ON u.id = a.unidade_id
            WHERE a.vendedor_id = ?
            ORDER BY CASE a.status WHEN 'ativo' THEN 0 WHEN 'pausado' THEN 1 ELSE 2 END, a.criado_em DESC""",
        (usuario_id,),
    ).fetchall()
    dados = db.execute(
        """SELECT u.nome, u.email, u.tipo_pessoa, u.criado_em, m.nome AS municipio_nome, m.uf AS municipio_uf
             FROM usuario u LEFT JOIN municipio m ON m.codigo_ibge = u.municipio_id WHERE u.id = ?""",
        (usuario_id,),
    ).fetchone()
    return render_template(
        "main/painel.html", usuario=dados, minhas_encomendas=minhas_encomendas,
        propostas_enviadas=propostas_enviadas, meus_anuncios=meus_anuncios,
        vitrine=perfis.perfil_produtor(db, usuario_id), loja=perfis.perfil_comercio(db, usuario_id),
    )
