"""Vitrines de produtores, perfis de comércio, diretórios regionais e dados da conta (RF02, RF26, RF27, RF30)."""
import functools
from math import ceil

from flask import abort, current_app, flash, g, redirect, render_template, request, session, url_for

from .. import cnpj, visibilidade
from ..auth.routes import destino_seguro, login_obrigatorio
from ..db import get_db
from ..formularios import escolhas_categorias
from ..fotos import FotoInvalida, apagar_fotos, arquivos_enviados, processar_foto
from ..localidades import (
    municipio_de_referencia, municipios_para_lista, proximidade_sql, rotulo_do_codigo, ufs_carregadas,
)
from ..servicos import SQL_ENCOMENDA, SQL_PRODUTO, expirar_encomendas_vencidas
from ..util import FORMAS_VENDA, TIPOS_COMERCIO, formatar_telefone, normalizar_busca
from . import bp, dados
from .forms import ContaForm, PerfilComercioForm, PerfilProdutorForm


def _eh_admin():
    return bool(g.usuario) and g.usuario["papel"] == "admin"


def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def produtor_obrigatorio(view):
    """Para áreas de produtor: sem vitrine, manda criar a vitrine e depois volta."""
    @functools.wraps(view)
    def envoltorio(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.entrar", next=request.path))
        if not g.usuario["tem_produtor"] and not _eh_admin():
            return render_template("perfis/so_produtores.html"), 403
        return view(*args, **kwargs)
    return envoltorio


def _ids_de_interesse(db):
    """Categorias marcadas no formulário (só ids que existem)."""
    validos = {linha["id"] for linha in db.execute("SELECT id FROM categoria WHERE ativa = 1")}
    return sorted({int(valor) for valor in request.form.getlist("interesse") if valor.isdigit()} & validos)


def _paginar(total):
    por_pagina = current_app.config["ITENS_POR_PAGINA"]
    paginas = max(ceil(total / por_pagina), 1)
    pagina = min(max(request.args.get("pagina", 1, type=int), 1), paginas)
    return pagina, paginas, por_pagina


# ---------- vitrine do produtor (RF26) ----------

@bp.route("/minha-vitrine", methods=["GET", "POST"])
@login_obrigatorio
def editar_produtor():
    db = get_db()
    usuario_id = g.usuario["id"]
    perfil = dados.perfil_produtor(db, usuario_id)
    form = PerfilProdutorForm()
    erro_foto = None

    if request.method == "GET":
        if perfil:
            for campo in ("nome_vitrine", "descricao", "onde_encontrar", "organico", "organico_registro"):
                getattr(form, campo).data = perfil[campo]
            for chave in FORMAS_VENDA:
                getattr(form, chave).data = bool(perfil[chave])
            form.telefone.data = formatar_telefone(perfil["telefone_publico"])
            form.whatsapp.data = bool(perfil["telefone_whatsapp"])
            form.municipio.data = rotulo_do_codigo(db, perfil["municipio_id"])
        else:
            form.municipio.data = rotulo_do_codigo(db, g.usuario["municipio_id"])

    if form.validate_on_submit():
        arquivos = arquivos_enviados(request.files.getlist("foto"))
        try:
            nova_foto = processar_foto(arquivos[0]) if arquivos else None
        except FotoInvalida as erro:
            erro_foto = str(erro)
        else:
            try:
                antiga = dados.salvar_perfil_produtor(
                    db, usuario_id, form.dados(), nova_foto, remover_foto=request.form.get("remover_foto") == "1"
                )
            except Exception:
                apagar_fotos([nova_foto] if nova_foto else [])
                raise
            apagar_fotos([antiga] if antiga else [])
            flash("Vitrine salva." if perfil else "Vitrine criada. Agora cadastre o que você produz.", "sucesso")
            destino = destino_seguro(request.args.get("next"))
            return redirect(destino or url_for("perfis.vitrine", usuario_id=usuario_id))

    return render_template(
        "perfis/produtor_form.html", form=form, perfil=perfil, erro_foto=erro_foto,
        municipios=municipios_para_lista(db),
    )


@bp.route("/produtores/<int:usuario_id>")
def vitrine(usuario_id):
    db = get_db()
    perfil = dados.perfil_produtor(db, usuario_id)
    sou_dono = bool(g.usuario) and g.usuario["id"] == usuario_id
    if perfil is None or (perfil["status"] != "ativo" and not sou_dono and not _eh_admin()):
        abort(404)
    # O dono vê todos os seus produtos. Os outros veem os do seu público (consumidor ou loja).
    publico = "1 = 1" if sou_dono or _eh_admin() else visibilidade.publico_sql("pd")
    produtos = db.execute(
        SQL_PRODUTO + f" WHERE pd.vendedor_id = ? AND pd.status = 'ativo' AND {publico}"
        " ORDER BY pd.criado_em DESC, pd.id DESC",
        (usuario_id,),
    ).fetchall()
    return render_template(
        "perfis/vitrine.html", perfil=perfil, produtos=produtos, sou_dono=sou_dono,
        categorias=dados.categorias_dos_produtores(db, [usuario_id], publico).get(usuario_id, []),
    )


@bp.route("/produtores")
def produtores():
    """Diretório público de produtores, do mais perto para o mais longe (RF30)."""
    db = get_db()
    referencia, erro_perto = municipio_de_referencia(db)
    termo = (request.args.get("q") or "").strip()[:100]
    categoria = request.args.get("categoria", type=int)
    uf = (request.args.get("uf") or "").upper()[:2]
    so_regiao = request.args.get("regiao") == "1" and referencia is not None and referencia["regiao_imediata_id"]

    publico = visibilidade.publico_sql("pd")
    condicoes, parametros = ["pp.status = 'ativo'"], []
    for palavra in normalizar_busca(termo).split():
        condicoes.append(
            "(pp.nome_busca LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM produto pd WHERE pd.vendedor_id = pp.usuario_id "
            f"AND pd.status = 'ativo' AND {publico} AND pd.titulo_busca LIKE ? ESCAPE '\\'))"
        )
        parametros += [f"%{_escapar_like(palavra)}%"] * 2
    if categoria:
        condicoes.append(
            "EXISTS (SELECT 1 FROM produto pd JOIN categoria c ON c.id = pd.categoria_id WHERE pd.vendedor_id = pp.usuario_id "
            f"AND pd.status = 'ativo' AND {publico} AND (pd.categoria_id = ? OR c.categoria_pai_id = ?))"
        )
        parametros += [categoria, categoria]
    if uf:
        condicoes.append("m.uf = ?")
        parametros.append(uf)
    if so_regiao:
        condicoes.append("m.regiao_imediata_id = ?")
        parametros.append(referencia["regiao_imediata_id"])
    onde = " AND ".join(condicoes)
    ordem, parametros_ordem = proximidade_sql("m", referencia)

    total = db.execute(
        f"SELECT COUNT(*) FROM perfil_produtor pp JOIN municipio m ON m.codigo_ibge = pp.municipio_id WHERE {onde}",
        parametros,
    ).fetchone()[0]
    pagina, paginas, por_pagina = _paginar(total)
    visiveis = f"(SELECT COUNT(*) FROM produto pd WHERE pd.vendedor_id = pp.usuario_id AND pd.status = 'ativo' AND {publico})"
    lista = db.execute(
        dados.SQL_PRODUTOR + f" WHERE {onde} ORDER BY {ordem}, {visiveis} DESC, pp.nome_busca LIMIT ? OFFSET ?",
        parametros + parametros_ordem + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()
    ids = [p["usuario_id"] for p in lista]

    return render_template(
        "perfis/produtores.html", produtores=lista, total=total, pagina=pagina, paginas=paginas,
        categorias_por_produtor=dados.categorias_dos_produtores(db, ids, publico),
        produtos_por_produtor=dados.produtos_por_produtor(db, ids, publico),
        termo=termo, categoria=categoria, uf=uf, so_regiao=bool(so_regiao), referencia=referencia,
        erro_perto=erro_perto, categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"),
        ufs=ufs_carregadas(db), municipios=municipios_para_lista(db),
        filtros_ativos=bool(termo or categoria or uf or so_regiao),
    )


# ---------- perfil de comércio (RF27) ----------

@bp.route("/minha-loja", methods=["GET", "POST"])
@login_obrigatorio
def editar_comercio():
    db = get_db()
    usuario_id = g.usuario["id"]
    perfil = dados.perfil_comercio(db, usuario_id)
    form = PerfilComercioForm()
    interesses = [linha["id"] for linha in dados.interesses_do_comercio(db, usuario_id)]

    if request.method == "GET":
        if perfil:
            for campo in ("nome_fantasia", "tipo", "descricao", "volume_compra"):
                getattr(form, campo).data = perfil[campo]
            form.cnpj.data = cnpj.formatar(perfil["cnpj"])
            form.telefone.data = formatar_telefone(perfil["telefone_publico"])
            form.whatsapp.data = bool(perfil["telefone_whatsapp"])
            form.municipio.data = rotulo_do_codigo(db, perfil["municipio_id"])
        else:
            form.municipio.data = rotulo_do_codigo(db, g.usuario["municipio_id"])
    else:
        interesses = _ids_de_interesse(db)

    if form.validate_on_submit():
        try:
            dados.salvar_perfil_comercio(db, usuario_id, form.dados(), interesses)
        except dados.CnpjEmUso:
            form.cnpj.errors.append("Este CNPJ já está cadastrado em outra conta. Se ele é seu, fale com a equipe.")
        else:
            if perfil and perfil["verificado_em"] and perfil["cnpj"] != form.dados()["cnpj"]:
                flash("Dados salvos. Como o CNPJ mudou, o selo de verificado saiu até uma nova conferência.", "info")
            else:
                flash("Dados da loja salvos." if perfil else "Loja cadastrada. Os produtores da região já podem encontrar você.", "sucesso")
            destino = destino_seguro(request.args.get("next"))
            return redirect(destino or url_for("perfis.comercio", usuario_id=usuario_id))

    return render_template(
        "perfis/comercio_form.html", form=form, perfil=perfil, interesses=set(interesses),
        categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"), municipios=municipios_para_lista(db),
    )


def _pode_ver_comercio(usuario_id):
    return bool(g.usuario) and (g.usuario["id"] == usuario_id or g.usuario["tem_produtor"] or _eh_admin())


@bp.route("/comercios/<int:usuario_id>")
@login_obrigatorio
def comercio(usuario_id):
    """Página da loja: para produtores (que querem vender para ela), a própria loja e a administração."""
    db = get_db()
    perfil = dados.perfil_comercio(db, usuario_id)
    sou_dono = g.usuario["id"] == usuario_id
    if perfil is None or (perfil["status"] != "ativo" and not sou_dono and not _eh_admin()):
        abort(404)
    if not _pode_ver_comercio(usuario_id):
        return render_template("perfis/so_produtores.html"), 403
    expirar_encomendas_vencidas(db)
    encomendas = db.execute(
        SQL_ENCOMENDA + " WHERE e.comprador_id = ? AND e.status IN ('aberta', 'em_negociacao') ORDER BY e.prazo_limite",
        (usuario_id,),
    ).fetchall()
    return render_template(
        "perfis/comercio.html", perfil=perfil, sou_dono=sou_dono, encomendas=encomendas,
        interesses=dados.interesses_do_comercio(db, usuario_id), cnpj_formatado=cnpj.formatar(perfil["cnpj"]),
    )


@bp.route("/comercios")
@produtor_obrigatorio
def comercios():
    """Diretório de comércios para produtores, do mais perto para o mais longe (RF27, RF30)."""
    db = get_db()
    referencia, erro_perto = municipio_de_referencia(db)
    termo = (request.args.get("q") or "").strip()[:100]
    tipo = request.args.get("tipo") if request.args.get("tipo") in TIPOS_COMERCIO else ""
    categoria = request.args.get("categoria", type=int)
    uf = (request.args.get("uf") or "").upper()[:2]
    so_regiao = request.args.get("regiao") == "1" and referencia is not None and referencia["regiao_imediata_id"]

    condicoes, parametros = ["pc.status = 'ativo'"], []
    for palavra in normalizar_busca(termo).split():
        condicoes.append("pc.nome_busca LIKE ? ESCAPE '\\'")
        parametros.append(f"%{_escapar_like(palavra)}%")
    if tipo:
        condicoes.append("pc.tipo = ?")
        parametros.append(tipo)
    if categoria:
        # Interesse na própria categoria, numa subcategoria dela ou na categoria principal dela.
        condicoes.append(
            "EXISTS (SELECT 1 FROM comercio_interesse ci JOIN categoria c ON c.id = ci.categoria_id "
            "WHERE ci.usuario_id = pc.usuario_id AND (ci.categoria_id = ? OR c.categoria_pai_id = ? "
            "OR ci.categoria_id = (SELECT categoria_pai_id FROM categoria WHERE id = ?)))"
        )
        parametros += [categoria, categoria, categoria]
    if uf:
        condicoes.append("m.uf = ?")
        parametros.append(uf)
    if so_regiao:
        condicoes.append("m.regiao_imediata_id = ?")
        parametros.append(referencia["regiao_imediata_id"])
    onde = " AND ".join(condicoes)
    ordem, parametros_ordem = proximidade_sql("m", referencia)

    total = db.execute(
        f"SELECT COUNT(*) FROM perfil_comercio pc JOIN municipio m ON m.codigo_ibge = pc.municipio_id WHERE {onde}",
        parametros,
    ).fetchone()[0]
    pagina, paginas, por_pagina = _paginar(total)
    lista = db.execute(
        dados.SQL_COMERCIO + f" WHERE {onde} ORDER BY {ordem}, pc.verificado_em IS NULL, pc.nome_busca LIMIT ? OFFSET ?",
        parametros + parametros_ordem + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()

    return render_template(
        "perfis/comercios.html", comercios=lista, total=total, pagina=pagina, paginas=paginas,
        interesses_por_comercio=dados.interesses_dos_comercios(db, [c["usuario_id"] for c in lista]),
        termo=termo, tipo=tipo, categoria=categoria, uf=uf, so_regiao=bool(so_regiao), referencia=referencia,
        erro_perto=erro_perto, categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"),
        ufs=ufs_carregadas(db), municipios=municipios_para_lista(db),
        filtros_ativos=bool(termo or tipo or categoria or uf or so_regiao),
    )


# ---------- dados da conta (RF02) ----------

@bp.route("/minha-conta", methods=["GET", "POST"])
@login_obrigatorio
def editar_conta():
    db = get_db()
    usuario_id = g.usuario["id"]
    form = ContaForm()
    if request.method == "GET":
        linha = db.execute("SELECT nome, tipo_pessoa, municipio_id FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
        form.nome.data = linha["nome"]
        form.tipo_pessoa.data = linha["tipo_pessoa"]
        form.municipio.data = rotulo_do_codigo(db, linha["municipio_id"])
    if form.validate_on_submit():
        dados.salvar_conta(db, usuario_id, form.nome.data, form.tipo_pessoa.data, form.municipio.codigo)
        flash("Seus dados foram salvos.", "sucesso")
        return redirect(url_for("main.painel"))
    return render_template("perfis/conta_form.html", form=form, municipios=municipios_para_lista(db))



# ---------- ver preços como loja ou como consumidor (RF29) ----------

@bp.route("/ver-como", methods=["POST"])
@login_obrigatorio
def ver_como():
    """Quem tem loja pode ver o site como consumidor (preço de varejo) e voltar para o modo loja."""
    if request.form.get("modo") == visibilidade.MODO_CONSUMIDOR:
        session["ver_como"] = visibilidade.MODO_CONSUMIDOR
    else:
        session.pop("ver_como", None)
    return redirect(destino_seguro(request.form.get("voltar")) or url_for("produtos.lista"))
