"""Anúncios de venda (RF04–RF06, RF16) e propostas de compra sobre anúncio (RF18)."""
import json
from datetime import date
from math import ceil

from flask import abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for

from .. import servicos
from ..atributos import atributos_por_principal, ler_atributos, valores_salvos
from ..auth.routes import login_obrigatorio
from ..db import get_db
from ..encomendas.forms import PropostaForm
from ..inspecao import aviso_inspecao
from ..formularios import escolhas_categorias
from ..fotos import NOME_VALIDO, FotoInvalida, apagar_fotos, arquivos_enviados, pasta_fotos, processar_foto
from ..localidades import municipios_para_lista, rotulo_do_codigo, ufs_carregadas
from ..util import formatar_numero, normalizar_busca, reais_para_centavos
from . import bp
from .forms import AnuncioForm

ORDENACOES = {
    "recentes": ("Mais recentes", "a.criado_em DESC, a.id DESC"),
    "menor_preco": ("Menor preço", "a.preco_centavos IS NULL, a.preco_centavos ASC, a.id DESC"),
    "maior_preco": ("Maior preço", "a.preco_centavos IS NULL, a.preco_centavos DESC, a.id DESC"),
}


def _usuario_id():
    return g.usuario["id"] if g.usuario else None


def _eh_admin():
    return bool(g.usuario) and g.usuario["papel"] == "admin"


def _anuncio_visivel_ou_404(anuncio_id):
    anuncio = servicos.buscar_anuncio(get_db(), anuncio_id)
    if anuncio is None:
        abort(404)
    if anuncio["status"] == "oculto" and anuncio["vendedor_id"] != _usuario_id() and not _eh_admin():
        abort(404)
    return anuncio


def _proposta_de_anuncio_ou_404(proposta_id):
    proposta = servicos.buscar_proposta(get_db(), proposta_id)
    if proposta is None or proposta["anuncio_id"] is None:
        abort(404)
    return proposta


def _data(texto):
    return date.fromisoformat(texto) if texto else None


def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _reais_do_filtro(texto):
    try:
        return reais_para_centavos(texto) if texto else None
    except ValueError:
        return None


# ---------- fotos ----------

@bp.route("/fotos/<nome>")
def foto(nome):
    """Serve a foto só se o nome for válido e o anúncio (ou a vitrine) puder ser visto.

    Fotos de anúncio ou vitrine oculta pela moderação não vazam pelo link direto.
    """
    if not NOME_VALIDO.match(nome):
        abort(404)
    linha = get_db().execute(
        """SELECT a.status, a.vendedor_id AS dono FROM foto_anuncio f JOIN anuncio a ON a.id = f.anuncio_id
            WHERE f.arquivo = ?
           UNION ALL
           SELECT status, usuario_id FROM perfil_produtor WHERE foto = ?""",
        (nome, nome),
    ).fetchone()
    if linha is None or (linha["status"] == "oculto" and linha["dono"] != _usuario_id() and not _eh_admin()):
        abort(404)
    return send_from_directory(pasta_fotos(), nome, mimetype="image/jpeg", max_age=86400)


# ---------- lista e busca (RF06) ----------

@bp.route("/anuncios")
def lista():
    db = get_db()
    termo = (request.args.get("q") or "").strip()[:100]
    categoria = request.args.get("categoria", type=int)
    uf = (request.args.get("uf") or "").upper()[:2]
    preco_min_texto = (request.args.get("preco_min") or "").strip()[:20]
    preco_max_texto = (request.args.get("preco_max") or "").strip()[:20]
    preco_min, preco_max = _reais_do_filtro(preco_min_texto), _reais_do_filtro(preco_max_texto)
    ordem = request.args.get("ordem") if request.args.get("ordem") in ORDENACOES else "recentes"
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    por_pagina = current_app.config["ITENS_POR_PAGINA"]

    condicoes, parametros = ["a.status = 'ativo'"], []
    for palavra in normalizar_busca(termo).split():
        condicoes.append("a.titulo_busca LIKE ? ESCAPE '\\'")
        parametros.append(f"%{_escapar_like(palavra)}%")
    if categoria:
        condicoes.append("(a.categoria_id = ? OR c.categoria_pai_id = ?)")
        parametros += [categoria, categoria]
    if uf:
        condicoes.append("m.uf = ?")
        parametros.append(uf)
    if preco_min is not None:
        condicoes.append("a.preco_centavos >= ?")
        parametros.append(preco_min)
    if preco_max is not None:
        condicoes.append("a.preco_centavos <= ?")
        parametros.append(preco_max)
    onde = " AND ".join(condicoes)

    total = db.execute(
        f"""SELECT COUNT(*) FROM anuncio a
              JOIN municipio m ON m.codigo_ibge = a.municipio_id
              JOIN categoria c ON c.id = a.categoria_id
             WHERE {onde}""",
        parametros,
    ).fetchone()[0]
    paginas = max(ceil(total / por_pagina), 1)
    pagina = min(pagina, paginas)
    anuncios = db.execute(
        servicos.SQL_ANUNCIO + f" WHERE {onde} ORDER BY {ORDENACOES[ordem][1]} LIMIT ? OFFSET ?",
        parametros + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()

    filtros_ativos = bool(termo or categoria or uf or preco_min_texto or preco_max_texto)
    return render_template(
        "anuncios/lista.html",
        anuncios=anuncios, total=total, pagina=pagina, paginas=paginas,
        inicio=(pagina - 1) * por_pagina + 1 if total else 0, fim=(pagina - 1) * por_pagina + len(anuncios),
        termo=termo, categoria=categoria, uf=uf, ordem=ordem, ordenacoes=ORDENACOES,
        preco_min=preco_min_texto, preco_max=preco_max_texto,
        categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"), ufs=ufs_carregadas(db),
        filtros_ativos=filtros_ativos,
    )


# ---------- publicar e editar (RF04, RF05, RF16) ----------

def _contexto_formulario(db, form, valores_atributos, erros_atributos, erro_fotos, anuncio=None, fotos=()):
    mapa = {
        str(linha["id"]): linha["categoria_pai_id"] or linha["id"]
        for linha in db.execute("SELECT id, categoria_pai_id FROM categoria")
    }
    return {
        "form": form,
        "municipios": municipios_para_lista(db),
        "grupos_atributos": atributos_por_principal(db),
        "mapa_categorias": json.dumps(mapa),
        "valores_atributos": valores_atributos,
        "erros_atributos": erros_atributos,
        "erro_fotos": erro_fotos,
        "anuncio": anuncio,
        "fotos": fotos,
        "limite_fotos": current_app.config["FOTOS_POR_ANUNCIO"],
        "tamanho_foto_mb": current_app.config["FOTO_TAMANHO_MAXIMO"] // (1024 * 1024),
    }


def _salvar_fotos(arquivos):
    """Processa todas as fotos. Se uma falhar, apaga as já gravadas e repassa o erro."""
    nomes = []
    try:
        for arquivo in arquivos:
            nomes.append(processar_foto(arquivo))
    except FotoInvalida:
        apagar_fotos(nomes)
        raise
    return nomes


@bp.route("/anuncios/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo():
    if not g.usuario["tem_produtor"]:
        flash("Para anunciar, crie primeiro a sua vitrine de produtor. Leva um minuto.", "info")
        return redirect(url_for("perfis.editar_produtor", next=request.path))
    db = get_db()
    form = AnuncioForm()
    valores, erros, erro_fotos = {}, {}, None
    if request.method == "GET":
        linha = db.execute("SELECT municipio_id FROM perfil_produtor WHERE usuario_id = ?", (g.usuario["id"],)).fetchone()
        form.municipio.data = rotulo_do_codigo(db, linha["municipio_id"] if linha else None)

    if request.method == "POST":
        formulario_ok = form.validate_on_submit()
        if form.categoria_id.data:
            valores, erros = ler_atributos(db, form.categoria_id.data, request.form)
        arquivos = arquivos_enviados(request.files.getlist("fotos"))
        if len(arquivos) > current_app.config["FOTOS_POR_ANUNCIO"]:
            erro_fotos = f"Envie no máximo {current_app.config['FOTOS_POR_ANUNCIO']} fotos."
        if formulario_ok and not erros and not erro_fotos:
            try:
                nomes = _salvar_fotos(arquivos)
            except FotoInvalida as erro:
                erro_fotos = str(erro)
            else:
                try:
                    anuncio_id = servicos.criar_anuncio(db, g.usuario["id"], form.dados(), valores, nomes)
                except Exception:
                    apagar_fotos(nomes)
                    raise
                flash("Anúncio publicado.", "sucesso")
                return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))
        if arquivos:
            flash("Por segurança, escolha as fotos de novo antes de enviar.", "info")

    return render_template("anuncios/form.html", editando=False, **_contexto_formulario(db, form, valores, erros, erro_fotos))


@bp.route("/anuncios/<int:anuncio_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar(anuncio_id):
    db = get_db()
    anuncio = _anuncio_visivel_ou_404(anuncio_id)
    if anuncio["vendedor_id"] != g.usuario["id"]:
        abort(403)
    if anuncio["status"] not in ("ativo", "pausado"):
        flash("Anúncios encerrados ou ocultos pela moderação não podem ser editados.", "erro")
        return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))

    form = AnuncioForm()
    fotos = servicos.fotos_do_anuncio(db, anuncio_id)
    valores = {linha["id"]: linha["valor"] for linha in valores_salvos(db, anuncio_id)}
    erros, erro_fotos = {}, None
    if request.method == "GET":
        form.titulo.data = anuncio["titulo"]
        form.categoria_id.data = anuncio["categoria_id"]
        form.descricao.data = anuncio["descricao"]
        form.preco.data = (
            f"{anuncio['preco_centavos'] // 100},{anuncio['preco_centavos'] % 100:02d}" if anuncio["preco_centavos"] else ""
        )
        form.unidade_id.data = anuncio["unidade_id"]
        form.quantidade.data = formatar_numero(anuncio["quantidade_disponivel"])
        form.municipio.data = rotulo_do_codigo(db, anuncio["municipio_id"])

    if request.method == "POST":
        formulario_ok = form.validate_on_submit()
        if form.categoria_id.data:
            valores, erros = ler_atributos(db, form.categoria_id.data, request.form)
        arquivos = arquivos_enviados(request.files.getlist("fotos"))
        remover = [int(valor) for valor in request.form.getlist("remover_foto") if valor.isdigit()]
        if formulario_ok and not erros:
            try:
                nomes = _salvar_fotos(arquivos)
            except FotoInvalida as erro:
                erro_fotos = str(erro)
            else:
                try:
                    removidas = servicos.editar_anuncio(db, anuncio, g.usuario["id"], form.dados(), valores, nomes, remover)
                except servicos.RegraNegocio as erro:
                    apagar_fotos(nomes)
                    erro_fotos = str(erro)
                else:
                    apagar_fotos(removidas)
                    flash("Anúncio atualizado.", "sucesso")
                    return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))

    return render_template(
        "anuncios/form.html", editando=True,
        **_contexto_formulario(db, form, valores, erros, erro_fotos, anuncio=anuncio, fotos=fotos),
    )


@bp.route("/anuncios/<int:anuncio_id>/<any(pausar, reativar, encerrar):acao>", methods=["POST"])
@login_obrigatorio
def mudar_status(anuncio_id, acao):
    anuncio = _anuncio_visivel_ou_404(anuncio_id)
    try:
        servicos.mudar_status_anuncio(get_db(), anuncio, g.usuario["id"], acao)
    except PermissionError:
        abort(403)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        mensagens = {
            "pausar": "Anúncio pausado. Ele não aparece na busca até você reativar.",
            "reativar": "Anúncio reativado.",
            "encerrar": "Anúncio encerrado.",
        }
        flash(mensagens[acao], "info")
    return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))


# ---------- detalhe ----------

@bp.route("/anuncios/<int:anuncio_id>")
def detalhe(anuncio_id):
    db = get_db()
    anuncio = _anuncio_visivel_ou_404(anuncio_id)
    usuario_id = _usuario_id()
    sou_vendedor = usuario_id == anuncio["vendedor_id"]
    if sou_vendedor:
        propostas = servicos.propostas_do_anuncio(db, anuncio_id)
    elif usuario_id:
        propostas = [p for p in servicos.propostas_do_anuncio(db, anuncio_id) if p["comprador_id"] == usuario_id]
    else:
        propostas = []
    minha_pendente = next((p for p in propostas if p["status"] == "pendente" and p["comprador_id"] == usuario_id), None)
    negocio_fechado = any(p["status"] == "aceita" for p in propostas) and not sou_vendedor
    vendedor_municipio = db.execute(
        "SELECT m.nome, m.uf FROM usuario u LEFT JOIN municipio m ON m.codigo_ibge = u.municipio_id WHERE u.id = ?",
        (anuncio["vendedor_id"],),
    ).fetchone()

    atributos = valores_salvos(db, anuncio_id)
    return render_template(
        "anuncios/detalhe.html",
        anuncio=anuncio, fotos=servicos.fotos_do_anuncio(db, anuncio_id), atributos=atributos,
        aviso_inspecao=aviso_inspecao(atributos, anuncio["municipio_nome"], anuncio["municipio_uf"]),
        propostas=propostas, minha_pendente=minha_pendente, sou_vendedor=sou_vendedor,
        negocio_fechado=negocio_fechado, vendedor_municipio=vendedor_municipio,
        pode_propor=bool(usuario_id) and not sou_vendedor and anuncio["status"] == "ativo" and minha_pendente is None,
    )


# ---------- propostas de compra (RF18) ----------

@bp.route("/anuncios/<int:anuncio_id>/proposta", methods=["GET", "POST"])
@login_obrigatorio
def proposta(anuncio_id):
    db = get_db()
    anuncio = _anuncio_visivel_ou_404(anuncio_id)
    if anuncio["vendedor_id"] == g.usuario["id"]:
        flash("Você não pode fazer proposta no seu próprio anúncio.", "erro")
        return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))
    existente = servicos.proposta_pendente_do_comprador(db, anuncio_id, g.usuario["id"])

    form = PropostaForm()
    form.preco.label.text = "Preço que você oferece"
    form.quantidade.label.text = "Quantidade que você quer comprar"
    form.prazo_entrega.label.text = "Data de entrega desejada"
    if request.method == "GET":
        if existente:
            centavos = existente["preco_unitario_centavos"]
            form.preco.data = f"{centavos // 100},{centavos % 100:02d}"
            form.quantidade.data = formatar_numero(existente["quantidade"])
            form.prazo_entrega.data = _data(existente["prazo_entrega"])
            form.transporte.data = existente["transporte"]
            form.validade.data = _data(existente["validade"])
            form.observacao.data = existente["observacao"]
        elif anuncio["preco_centavos"]:
            form.preco.data = f"{anuncio['preco_centavos'] // 100},{anuncio['preco_centavos'] % 100:02d}"
    if form.validate_on_submit():
        try:
            if existente:
                servicos.editar_proposta_anuncio(db, existente, anuncio, g.usuario["id"], form.dados())
                flash("Proposta atualizada.", "sucesso")
            else:
                servicos.enviar_proposta_anuncio(db, anuncio, g.usuario["id"], form.dados())
                flash("Proposta enviada. O vendedor foi avisado.", "sucesso")
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio_id))
    return render_template("anuncios/proposta_form.html", form=form, anuncio=anuncio, existente=existente)


@bp.route("/anuncios/propostas/<int:proposta_id>/retirar", methods=["POST"])
@login_obrigatorio
def retirar(proposta_id):
    proposta = _proposta_de_anuncio_ou_404(proposta_id)
    try:
        servicos.retirar_proposta_anuncio(get_db(), proposta, g.usuario["id"])
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Proposta retirada.", "info")
    return redirect(url_for("anuncios.detalhe", anuncio_id=proposta["anuncio_id"]))


@bp.route("/anuncios/propostas/<int:proposta_id>/<any(aceitar, recusar):acao>", methods=["POST"])
@login_obrigatorio
def responder(proposta_id, acao):
    proposta = _proposta_de_anuncio_ou_404(proposta_id)
    anuncio = _anuncio_visivel_ou_404(proposta["anuncio_id"])
    try:
        servicos.responder_proposta_anuncio(get_db(), proposta, anuncio, g.usuario["id"], aceitar=acao == "aceitar")
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        if acao == "aceitar":
            flash("Proposta aceita. O comprador foi avisado e o contato de vocês dois foi liberado.", "sucesso")
        else:
            flash("Proposta recusada. O comprador foi avisado.", "info")
    return redirect(url_for("anuncios.detalhe", anuncio_id=anuncio["id"]))
