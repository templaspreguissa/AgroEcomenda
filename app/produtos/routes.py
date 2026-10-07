"""Produtos do catálogo do produtor (RF04–RF06, RF16, RF28–RF32) e propostas de compra (RF18, RF31)."""
import json
from datetime import date
from math import ceil

from flask import abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for

from .. import servicos, visibilidade
from ..atributos import atributos_por_principal, ler_atributos
from ..auth.routes import login_obrigatorio
from ..db import get_db
from ..encomendas.forms import PropostaForm
from ..formularios import escolhas_categorias
from ..fotos import NOME_VALIDO, FotoInvalida, apagar_fotos, arquivos_enviados, pasta_fotos, processar_foto
from ..inspecao import ATRIBUTO_INSPECAO, SEM_REGISTRO, aviso_inspecao
from ..localidades import (
    dados_municipio, municipio_de_referencia, municipios_para_lista, proximidade_sql, rotulo_do_codigo,
    ufs_carregadas,
)
from ..util import bit_do_mes, formatar_numero, normalizar_busca, reais_para_centavos
from . import bp
from .forms import ProdutoForm


def _usuario_id():
    return g.usuario["id"] if g.usuario else None


def _eh_admin():
    return bool(g.usuario) and g.usuario["papel"] == "admin"


def _produto_visivel_ou_404(produto_id):
    produto = servicos.buscar_produto(get_db(), produto_id)
    if produto is None:
        abort(404)
    escondido = produto["status"] == "oculto" or produto["vendedor_status"] != "ativo"
    if escondido and produto["vendedor_id"] != _usuario_id() and not _eh_admin():
        abort(404)
    return produto


def _proposta_de_produto_ou_404(proposta_id):
    proposta = servicos.buscar_proposta(get_db(), proposta_id)
    if proposta is None or proposta["produto_id"] is None:
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


def _reais_para_campo(centavos):
    return f"{centavos // 100},{centavos % 100:02d}" if centavos else ""


def _local_do_comprador(db, canal):
    """Município de quem compra: o da loja, numa compra como loja; senão, o da conta."""
    if canal == "lojista":
        linha = db.execute("SELECT municipio_id FROM perfil_comercio WHERE usuario_id = ?", (g.usuario["id"],)).fetchone()
        if linha:
            return dados_municipio(db, linha["municipio_id"])
    return dados_municipio(db, g.usuario["municipio_id"])


# ---------- fotos ----------

@bp.route("/fotos/<nome>")
def foto(nome):
    """Serve a foto só se o nome for válido e o produto (ou a vitrine) puder ser visto.

    Fotos de produto ou vitrine oculta pela moderação não vazam pelo link direto.
    """
    if not NOME_VALIDO.match(nome):
        abort(404)
    linha = get_db().execute(
        """SELECT pd.status, pd.vendedor_id AS dono FROM foto_produto f JOIN produto pd ON pd.id = f.produto_id
            WHERE f.arquivo = ?
           UNION ALL
           SELECT status, usuario_id FROM perfil_produtor WHERE foto = ?""",
        (nome, nome),
    ).fetchone()
    if linha is None or (linha["status"] == "oculto" and linha["dono"] != _usuario_id() and not _eh_admin()):
        abort(404)
    return send_from_directory(pasta_fotos(), nome, mimetype="image/jpeg", max_age=86400)


# ---------- lista e busca (RF06, RF29, RF30, RF32) ----------

def _ordenacoes(referencia):
    preco = visibilidade.preco_sql("pd")
    opcoes = {}
    if referencia is not None:
        opcoes["perto"] = "Mais perto de você"
    opcoes.update({
        "recentes": "Mais recentes",
        "menor_preco": "Menor preço",
        "maior_preco": "Maior preço",
    })
    sql = {
        "recentes": ("pd.criado_em DESC, pd.id DESC", []),
        "menor_preco": (f"{preco} IS NULL, {preco} ASC, pd.id DESC", []),
        "maior_preco": (f"{preco} IS NULL, {preco} DESC, pd.id DESC", []),
    }
    if referencia is not None:
        expressao, parametros = proximidade_sql("m", referencia)
        sql["perto"] = (f"{expressao}, pd.criado_em DESC, pd.id DESC", parametros)
    return opcoes, sql


@bp.route("/produtos")
def lista():
    db = get_db()
    referencia, erro_perto = municipio_de_referencia(db)
    termo = (request.args.get("q") or "").strip()[:100]
    categoria = request.args.get("categoria", type=int)
    uf = (request.args.get("uf") or "").upper()[:2]
    so_regiao = request.args.get("regiao") == "1" and referencia is not None and referencia["regiao_imediata_id"]
    agora = request.args.get("agora") == "1"
    preco_min_texto = (request.args.get("preco_min") or "").strip()[:20]
    preco_max_texto = (request.args.get("preco_max") or "").strip()[:20]
    preco_min, preco_max = _reais_do_filtro(preco_min_texto), _reais_do_filtro(preco_max_texto)
    ordenacoes, ordens_sql = _ordenacoes(referencia)
    padrao = "perto" if referencia is not None else "recentes"
    ordem = request.args.get("ordem") if request.args.get("ordem") in ordenacoes else padrao
    pagina = max(request.args.get("pagina", 1, type=int), 1)
    por_pagina = current_app.config["ITENS_POR_PAGINA"]

    preco = visibilidade.preco_sql("pd")
    condicoes, parametros = ["pd.status = 'ativo'", "v.status = 'ativo'", visibilidade.publico_sql("pd")], []
    for palavra in normalizar_busca(termo).split():
        condicoes.append("pd.titulo_busca LIKE ? ESCAPE '\\'")
        parametros.append(f"%{_escapar_like(palavra)}%")
    if categoria:
        condicoes.append("(pd.categoria_id = ? OR c.categoria_pai_id = ?)")
        parametros += [categoria, categoria]
    if uf:
        condicoes.append("m.uf = ?")
        parametros.append(uf)
    if so_regiao:
        condicoes.append("m.regiao_imediata_id = ?")
        parametros.append(referencia["regiao_imediata_id"])
    if agora:
        condicoes.append("(pd.disponibilidade <> 'safra' OR (pd.meses_safra & ?) <> 0)")
        parametros.append(bit_do_mes())
    if preco_min is not None:
        condicoes.append(f"{preco} >= ?")
        parametros.append(preco_min)
    if preco_max is not None:
        condicoes.append(f"{preco} <= ?")
        parametros.append(preco_max)
    onde = " AND ".join(condicoes)

    total = db.execute(
        f"""SELECT COUNT(*) FROM produto pd
              JOIN usuario v   ON v.id = pd.vendedor_id
              JOIN municipio m ON m.codigo_ibge = pd.municipio_id
              JOIN categoria c ON c.id = pd.categoria_id
             WHERE {onde}""",
        parametros,
    ).fetchone()[0]
    paginas = max(ceil(total / por_pagina), 1)
    pagina = min(pagina, paginas)
    ordem_sql, parametros_ordem = ordens_sql[ordem]
    produtos = db.execute(
        servicos.SQL_PRODUTO + f" WHERE {onde} ORDER BY {ordem_sql} LIMIT ? OFFSET ?",
        parametros + parametros_ordem + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()

    filtros_ativos = bool(termo or categoria or uf or so_regiao or agora or preco_min_texto or preco_max_texto)
    return render_template(
        "produtos/lista.html",
        produtos=produtos, total=total, pagina=pagina, paginas=paginas,
        inicio=(pagina - 1) * por_pagina + 1 if total else 0, fim=(pagina - 1) * por_pagina + len(produtos),
        termo=termo, categoria=categoria, uf=uf, so_regiao=bool(so_regiao), agora=agora, ordem=ordem,
        ordenacoes=ordenacoes, preco_min=preco_min_texto, preco_max=preco_max_texto,
        referencia=referencia, erro_perto=erro_perto, municipios=municipios_para_lista(db),
        categorias=escolhas_categorias(db, rotulo_geral="Tudo em {nome}"), ufs=ufs_carregadas(db),
        filtros_ativos=filtros_ativos,
    )


# ---------- cadastrar e editar (RF04, RF05, RF16, RF28, RF32) ----------

def _contexto_formulario(db, form, valores_atributos, erros_atributos, erro_fotos, produto=None, fotos=()):
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
        "produto": produto,
        "fotos": fotos,
        "limite_fotos": current_app.config["FOTOS_POR_PRODUTO"],
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


def _conferir_publico_com_inspecao(form, valores):
    """Produto de origem animal sem registro de inspeção não pode ir para o consumidor final."""
    if valores.get(ATRIBUTO_INSPECAO) == SEM_REGISTRO and form.para_consumidor.data:
        form.erro_publico = (
            "Produto sem registro de inspeção só pode ser vendido para lojas e outros estabelecimentos. "
            "Desmarque “Vender para o consumidor final”."
        )
        return False
    return True


def _ler_formulario(db, form):
    """Valida o formulário, os campos da categoria e as fotos. Devolve (ok, valores, erros, arquivos, erro_fotos)."""
    formulario_ok = form.validate_on_submit()
    valores, erros = {}, {}
    if form.categoria_id.data:
        valores, erros = ler_atributos(db, form.categoria_id.data, request.form)
    publico_ok = _conferir_publico_com_inspecao(form, valores)
    arquivos = arquivos_enviados(request.files.getlist("fotos"))
    erro_fotos = None
    if len(arquivos) > current_app.config["FOTOS_POR_PRODUTO"]:
        erro_fotos = f"Envie no máximo {current_app.config['FOTOS_POR_PRODUTO']} fotos."
    return formulario_ok and publico_ok and not erros and not erro_fotos, valores, erros, arquivos, erro_fotos


@bp.route("/produtos/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo():
    if not g.usuario["tem_produtor"]:
        flash("Para cadastrar produtos, crie primeiro a sua vitrine de produtor. Leva um minuto.", "info")
        return redirect(url_for("perfis.editar_produtor", next=request.path))
    db = get_db()
    form = ProdutoForm()
    valores, erros, erro_fotos = {}, {}, None
    if request.method == "GET":
        linha = db.execute("SELECT municipio_id FROM perfil_produtor WHERE usuario_id = ?", (g.usuario["id"],)).fetchone()
        form.municipio.data = rotulo_do_codigo(db, linha["municipio_id"] if linha else None)
        form.para_consumidor.data = True

    if request.method == "POST":
        ok, valores, erros, arquivos, erro_fotos = _ler_formulario(db, form)
        if ok:
            try:
                nomes = _salvar_fotos(arquivos)
            except FotoInvalida as erro:
                erro_fotos = str(erro)
            else:
                try:
                    produto_id = servicos.criar_produto(db, g.usuario["id"], form.dados(), valores, nomes)
                except Exception:
                    apagar_fotos(nomes)
                    raise
                flash("Produto cadastrado.", "sucesso")
                return redirect(url_for("produtos.detalhe", produto_id=produto_id))
        if arquivos:
            flash("Por segurança, escolha as fotos de novo antes de enviar.", "info")

    return render_template("produtos/form.html", editando=False, **_contexto_formulario(db, form, valores, erros, erro_fotos))


@bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar(produto_id):
    db = get_db()
    produto = _produto_visivel_ou_404(produto_id)
    if produto["vendedor_id"] != g.usuario["id"]:
        abort(403)
    if produto["status"] not in ("ativo", "pausado"):
        flash("Produtos encerrados ou ocultos pela moderação não podem ser editados.", "erro")
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    form = ProdutoForm()
    fotos = servicos.fotos_do_produto(db, produto_id)
    valores = {linha["id"]: linha["valor"] for linha in servicos.atributos_do_produto(db, produto_id)}
    erros, erro_fotos = {}, None
    if request.method == "GET":
        form.titulo.data = produto["titulo"]
        form.categoria_id.data = produto["categoria_id"]
        form.descricao.data = produto["descricao"]
        form.unidade_id.data = produto["unidade_id"]
        form.quantidade.data = formatar_numero(produto["quantidade_disponivel"])
        form.municipio.data = rotulo_do_codigo(db, produto["municipio_id"])
        form.para_consumidor.data = bool(produto["para_consumidor"])
        form.preco_consumidor.data = _reais_para_campo(produto["preco_consumidor_centavos"])
        form.para_lojista.data = bool(produto["para_lojista"])
        form.preco_lojista.data = _reais_para_campo(produto["preco_lojista_centavos"])
        form.pedido_minimo.data = formatar_numero(produto["pedido_minimo_lojista"])
        form.so_verificados.data = bool(produto["so_verificados"])
        form.disponibilidade.data = produto["disponibilidade"]
        form.meses.data = [mes for mes in range(1, 13) if produto["meses_safra"] >> (mes - 1) & 1]

    if request.method == "POST":
        ok, valores, erros, arquivos, erro_fotos = _ler_formulario(db, form)
        remover = [int(valor) for valor in request.form.getlist("remover_foto") if valor.isdigit()]
        if ok:
            try:
                nomes = _salvar_fotos(arquivos)
            except FotoInvalida as erro:
                erro_fotos = str(erro)
            else:
                try:
                    removidas = servicos.editar_produto(db, produto, g.usuario["id"], form.dados(), valores, nomes, remover)
                except servicos.RegraNegocio as erro:
                    apagar_fotos(nomes)
                    erro_fotos = str(erro)
                else:
                    apagar_fotos(removidas)
                    flash("Produto atualizado.", "sucesso")
                    return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    return render_template(
        "produtos/form.html", editando=True,
        **_contexto_formulario(db, form, valores, erros, erro_fotos, produto=produto, fotos=fotos),
    )


@bp.route("/produtos/<int:produto_id>/<any(pausar, reativar, encerrar):acao>", methods=["POST"])
@login_obrigatorio
def mudar_status(produto_id, acao):
    produto = _produto_visivel_ou_404(produto_id)
    try:
        servicos.mudar_status_produto(get_db(), produto, g.usuario["id"], acao)
    except PermissionError:
        abort(403)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        mensagens = {
            "pausar": "Produto pausado. Ele não aparece na busca até você reativar.",
            "reativar": "Produto reativado.",
            "encerrar": "Produto encerrado.",
        }
        flash(mensagens[acao], "info")
    return redirect(url_for("produtos.detalhe", produto_id=produto_id))


# ---------- detalhe ----------

@bp.route("/produtos/<int:produto_id>")
def detalhe(produto_id):
    db = get_db()
    produto = _produto_visivel_ou_404(produto_id)
    usuario_id = _usuario_id()
    sou_vendedor = usuario_id == produto["vendedor_id"]
    if sou_vendedor:
        propostas = servicos.propostas_do_produto(db, produto_id)
    elif usuario_id:
        propostas = [p for p in servicos.propostas_do_produto(db, produto_id) if p["comprador_id"] == usuario_id]
    else:
        propostas = []
    minha_pendente = next((p for p in propostas if p["status"] == "pendente" and p["comprador_id"] == usuario_id), None)
    negocio_fechado = any(p["status"] == "aceita" for p in propostas) and not sou_vendedor
    vendedor_municipio = db.execute(
        "SELECT m.nome, m.uf FROM usuario u LEFT JOIN municipio m ON m.codigo_ibge = u.municipio_id WHERE u.id = ?",
        (produto["vendedor_id"],),
    ).fetchone()
    atributos = servicos.atributos_do_produto(db, produto_id)
    canal = visibilidade.canal_de_compra(produto)

    return render_template(
        "produtos/detalhe.html",
        produto=produto, fotos=servicos.fotos_do_produto(db, produto_id), atributos=atributos,
        aviso_inspecao=aviso_inspecao(atributos, produto["municipio_nome"], produto["municipio_uf"]),
        propostas=propostas, minha_pendente=minha_pendente, sou_vendedor=sou_vendedor,
        negocio_fechado=negocio_fechado, vendedor_municipio=vendedor_municipio,
        canal=canal, motivo_sem_compra=None if canal else visibilidade.motivo_sem_compra(produto),
        ve_tudo=visibilidade.ve_tudo(produto),
        lojas_que_vendem=servicos.contratos.lojas_que_vendem_o_produto(db, produto_id),
        pode_propor=bool(usuario_id) and not sou_vendedor and produto["status"] == "ativo"
        and minha_pendente is None and canal is not None,
    )


# ---------- propostas de compra (RF18, RF31) ----------

ROTULOS_CANAL = {
    "consumidor": {
        "titulo": "Fazer pedido", "editar": "Editar pedido", "botao": "Enviar pedido",
        "preco": "Preço que você oferece", "quantidade": "Quantidade que você quer",
    },
    "lojista": {
        "titulo": "Pedir cotação para a loja", "editar": "Editar cotação", "botao": "Enviar cotação",
        "preco": "Preço que a loja oferece", "quantidade": "Quantidade para a loja",
    },
}


@bp.route("/produtos/<int:produto_id>/proposta", methods=["GET", "POST"])
@login_obrigatorio
def proposta(produto_id):
    db = get_db()
    produto = _produto_visivel_ou_404(produto_id)
    if produto["vendedor_id"] == g.usuario["id"]:
        flash("Você não pode fazer proposta no seu próprio produto.", "erro")
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))
    existente = servicos.proposta_pendente_do_comprador(db, produto_id, g.usuario["id"])
    canal = existente["canal"] if existente else visibilidade.canal_de_compra(produto)
    if canal is None:
        flash(visibilidade.motivo_sem_compra(produto), "erro")
        return redirect(url_for("produtos.detalhe", produto_id=produto_id))

    rotulos = ROTULOS_CANAL[canal]
    form = PropostaForm()
    form.preco.label.text = rotulos["preco"]
    form.quantidade.label.text = rotulos["quantidade"]
    form.prazo_entrega.label.text = "Data de entrega ou retirada desejada"
    preco_tabela = produto["preco_lojista_centavos"] if canal == "lojista" else produto["preco_consumidor_centavos"]
    if request.method == "GET":
        if existente:
            form.preco.data = _reais_para_campo(existente["preco_unitario_centavos"])
            form.quantidade.data = formatar_numero(existente["quantidade"])
            form.prazo_entrega.data = _data(existente["prazo_entrega"])
            form.transporte.data = existente["transporte"]
            form.validade.data = _data(existente["validade"])
            form.observacao.data = existente["observacao"]
        else:
            form.preco.data = _reais_para_campo(preco_tabela)
            if canal == "lojista" and produto["pedido_minimo_lojista"]:
                form.quantidade.data = formatar_numero(produto["pedido_minimo_lojista"])
    if form.validate_on_submit():
        comprador = _local_do_comprador(db, canal)
        try:
            if existente:
                servicos.editar_proposta_produto(db, existente, produto, g.usuario["id"], form.dados(), comprador)
                flash("Proposta atualizada.", "sucesso")
            else:
                servicos.enviar_proposta_produto(db, produto, g.usuario["id"], form.dados(), canal, comprador)
                flash("Proposta enviada. O produtor foi avisado.", "sucesso")
        except servicos.RegraNegocio as erro:
            flash(str(erro), "erro")
        else:
            return redirect(url_for("produtos.detalhe", produto_id=produto_id))
    return render_template(
        "produtos/proposta_form.html", form=form, produto=produto, existente=existente, canal=canal,
        rotulos=rotulos, preco_tabela=preco_tabela,
    )


@bp.route("/produtos/propostas/<int:proposta_id>/retirar", methods=["POST"])
@login_obrigatorio
def retirar(proposta_id):
    proposta = _proposta_de_produto_ou_404(proposta_id)
    try:
        servicos.retirar_proposta_produto(get_db(), proposta, g.usuario["id"])
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        flash("Proposta retirada.", "info")
    return redirect(url_for("produtos.detalhe", produto_id=proposta["produto_id"]))


@bp.route("/produtos/propostas/<int:proposta_id>/<any(aceitar, recusar):acao>", methods=["POST"])
@login_obrigatorio
def responder(proposta_id, acao):
    proposta = _proposta_de_produto_ou_404(proposta_id)
    produto = _produto_visivel_ou_404(proposta["produto_id"])
    try:
        servicos.responder_proposta_produto(get_db(), proposta, produto, g.usuario["id"], aceitar=acao == "aceitar")
    except PermissionError:
        abort(404)
    except servicos.RegraNegocio as erro:
        flash(str(erro), "erro")
    else:
        if acao == "aceitar":
            flash("Proposta aceita. O comprador foi avisado e o contato de vocês dois foi liberado.", "sucesso")
        else:
            flash("Proposta recusada. O comprador foi avisado.", "info")
    return redirect(url_for("produtos.detalhe", produto_id=produto["id"]))
