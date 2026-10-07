"""Denúncias (RF19) e administração (RF15, RF20, RF25, RF38).

Toda ação do administrador fica registrada em acao_moderacao com quem, quando, sobre o quê e por quê.
Conteúdo oculto some para o público, mas continua visível para o dono e para a administração.
Conta bloqueada (ou excluída) perde a sessão e o que ela publicou deixa de aparecer nas listas.

Base: Marco Civil da Internet e a tese do STF de 2025 sobre o art. 19, que pede "sistema de notificações,
devido processo e relatórios" (pesquisa, seção 10.2.8).
"""
from ..util import agora_utc_texto, normalizar_busca
from .comum import RegraNegocio, notificar

MOTIVOS = {
    "golpe": "Golpe ou tentativa de fraude",
    "proibido": "Produto proibido, sem inspeção ou sem registro exigido",
    "falso": "Informação falsa ou enganosa",
    "ofensivo": "Conteúdo ofensivo ou discriminatório",
    "spam": "Spam ou propaganda indesejada",
    "outro": "Outro motivo",
}
ALVOS = ("produto", "vitrine", "loja", "encomenda", "conversa")
DENUNCIAS_POR_DIA = 10


def alvo(db, tipo, alvo_id):
    """Resumo do que foi denunciado: dono, título, link e situação. None se não existe."""
    if tipo == "produto":
        linha = db.execute("SELECT vendedor_id AS dono, titulo, status FROM produto WHERE id = ?", (alvo_id,)).fetchone()
        link = f"/produtos/{alvo_id}"
    elif tipo == "vitrine":
        linha = db.execute("SELECT usuario_id AS dono, nome_vitrine AS titulo, status FROM perfil_produtor WHERE usuario_id = ?",
                           (alvo_id,)).fetchone()
        link = f"/produtores/{alvo_id}"
    elif tipo == "loja":
        linha = db.execute("SELECT usuario_id AS dono, nome_fantasia AS titulo, status FROM perfil_comercio WHERE usuario_id = ?",
                           (alvo_id,)).fetchone()
        link = f"/comercios/{alvo_id}"
    elif tipo == "encomenda":
        linha = db.execute("SELECT comprador_id AS dono, titulo, status FROM encomenda WHERE id = ?", (alvo_id,)).fetchone()
        link = f"/encomendas/{alvo_id}"
    elif tipo == "conversa":
        linha = db.execute("SELECT usuario_a_id, usuario_b_id, contexto_tipo FROM conversa WHERE id = ?", (alvo_id,)).fetchone()
        if linha is None:
            return None
        return {"tipo": tipo, "id": alvo_id, "dono": None, "participantes": (linha["usuario_a_id"], linha["usuario_b_id"]),
                "titulo": f"Conversa nº {alvo_id}", "status": "", "link": f"/admin/conversas/{alvo_id}"}
    else:
        return None
    if linha is None:
        return None
    return {"tipo": tipo, "id": alvo_id, "dono": linha["dono"], "participantes": (), "titulo": linha["titulo"],
            "status": linha["status"], "link": link}


def _registrar(db, admin_id, alvo_tipo, alvo_id, acao, motivo):
    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise RegraNegocio("Escreva o motivo da decisão. Ele fica registrado.")
    db.execute(
        "INSERT INTO acao_moderacao (admin_id, alvo_tipo, alvo_id, acao, motivo) VALUES (?, ?, ?, ?, ?)",
        (admin_id, alvo_tipo, alvo_id, acao, motivo[:500]),
    )


# ---------- denúncias (RF19) ----------

def denunciar(db, denunciante_id, tipo, alvo_id, motivo, descricao=""):
    if tipo not in ALVOS or motivo not in MOTIVOS:
        raise RegraNegocio("Escolha o motivo da denúncia.")
    resumo = alvo(db, tipo, alvo_id)
    if resumo is None:
        raise LookupError
    if tipo == "conversa" and denunciante_id not in resumo["participantes"]:
        raise LookupError  # só quem participa da conversa pode denunciá-la
    if resumo["dono"] == denunciante_id:
        raise RegraNegocio("Você não pode denunciar o seu próprio conteúdo.")
    repetida = db.execute(
        "SELECT 1 FROM denuncia WHERE denunciante_id = ? AND alvo_tipo = ? AND alvo_id = ? AND status = 'aberta'",
        (denunciante_id, tipo, alvo_id),
    ).fetchone()
    if repetida:
        raise RegraNegocio("Você já denunciou isto. A moderação vai analisar.")
    no_dia = db.execute(
        "SELECT COUNT(*) FROM denuncia WHERE denunciante_id = ? AND criada_em >= datetime('now', '-1 day')",
        (denunciante_id,),
    ).fetchone()[0]
    if no_dia >= DENUNCIAS_POR_DIA:
        raise RegraNegocio("Você fez muitas denúncias nas últimas 24 horas. Tente de novo amanhã.")
    with db:
        return db.execute(
            "INSERT INTO denuncia (denunciante_id, alvo_tipo, alvo_id, motivo, descricao) VALUES (?, ?, ?, ?, ?)",
            (denunciante_id, tipo, alvo_id, motivo, (descricao or "").strip()[:1000]),
        ).lastrowid


def denuncias(db, abertas=True, limite=100):
    """Fila da moderação (mais antigas primeiro) ou histórico (mais recentes primeiro)."""
    if abertas:
        return db.execute(
            """SELECT d.*, u.nome AS denunciante_nome,
                      (SELECT COUNT(*) FROM denuncia o WHERE o.alvo_tipo = d.alvo_tipo AND o.alvo_id = d.alvo_id
                          AND o.status = 'aberta') AS denuncias_do_alvo
                 FROM denuncia d JOIN usuario u ON u.id = d.denunciante_id
                WHERE d.status = 'aberta' ORDER BY d.criada_em, d.id LIMIT ?""",
            (limite,),
        ).fetchall()
    return db.execute(
        """SELECT d.*, u.nome AS denunciante_nome, 1 AS denuncias_do_alvo
             FROM denuncia d JOIN usuario u ON u.id = d.denunciante_id
            WHERE d.status <> 'aberta' ORDER BY d.resolvida_em DESC, d.id DESC LIMIT ?""",
        (limite,),
    ).fetchall()


def buscar_denuncia(db, denuncia_id):
    return db.execute(
        "SELECT d.*, u.nome AS denunciante_nome FROM denuncia d JOIN usuario u ON u.id = d.denunciante_id WHERE d.id = ?",
        (denuncia_id,),
    ).fetchone()


def resolver_denuncia(db, admin_id, denuncia, procedente, decisao, ocultar=False, bloquear=False):
    """Fecha a denúncia (e as outras abertas sobre o mesmo alvo) e, se for o caso, oculta e bloqueia."""
    if denuncia["status"] != "aberta":
        raise RegraNegocio("Esta denúncia já foi resolvida.")
    resumo = alvo(db, denuncia["alvo_tipo"], denuncia["alvo_id"])
    situacao = "procedente" if procedente else "improcedente"
    with db:
        _registrar(db, admin_id, "denuncia", denuncia["id"], "resolver_denuncia", f"{situacao}: {decisao}")
        db.execute(
            """UPDATE denuncia SET status = ?, moderador_id = ?, decisao = ?, resolvida_em = ?
                WHERE alvo_tipo = ? AND alvo_id = ? AND status = 'aberta'""",
            (situacao, admin_id, decisao.strip()[:500], agora_utc_texto(), denuncia["alvo_tipo"], denuncia["alvo_id"]),
        )
        if procedente and ocultar and resumo and resumo["tipo"] != "conversa":
            _ocultar(db, admin_id, resumo, decisao)
        if procedente and bloquear and resumo:
            alvos = resumo["participantes"] if resumo["tipo"] == "conversa" else (resumo["dono"],)
            for usuario_id in alvos:
                if usuario_id != denuncia["denunciante_id"]:
                    _bloquear(db, admin_id, usuario_id, decisao)


# ---------- ocultar e reativar conteúdo ----------

def _ocultar(db, admin_id, resumo, motivo):
    tipo, alvo_id = resumo["tipo"], resumo["id"]
    _registrar(db, admin_id, tipo, alvo_id, "ocultar", motivo)
    agora = agora_utc_texto()
    if tipo == "produto":
        db.execute("UPDATE produto SET status = 'oculto', atualizado_em = ? WHERE id = ?", (agora, alvo_id))
        db.execute("UPDATE proposta SET status = 'nao_selecionada', respondida_em = ? WHERE produto_id = ? AND status = 'pendente'",
                   (agora, alvo_id))
    elif tipo == "vitrine":
        db.execute("UPDATE perfil_produtor SET status = 'oculto' WHERE usuario_id = ?", (alvo_id,))
    elif tipo == "loja":
        db.execute("UPDATE perfil_comercio SET status = 'oculto' WHERE usuario_id = ?", (alvo_id,))
    elif tipo == "encomenda":
        db.execute("UPDATE encomenda SET status = 'cancelada', encerrada_em = ? WHERE id = ? AND status IN ('aberta', 'em_negociacao')",
                   (agora, alvo_id))
        db.execute("UPDATE proposta SET status = 'nao_selecionada', respondida_em = ? WHERE encomenda_id = ? AND status = 'pendente'",
                   (agora, alvo_id))
    notificar(
        db, resumo["dono"], "conteudo_moderado",
        f'A moderação ocultou "{resumo["titulo"]}". Motivo: {motivo.strip()[:200]}', resumo["link"],
    )


def ocultar_conteudo(db, admin_id, tipo, alvo_id, motivo):
    resumo = alvo(db, tipo, alvo_id)
    if resumo is None or tipo == "conversa":
        raise LookupError
    with db:
        _ocultar(db, admin_id, resumo, motivo)


def reativar_conteudo(db, admin_id, tipo, alvo_id, motivo):
    """Volta a mostrar. O produto volta como 'pausado', para o dono decidir quando reativar."""
    resumo = alvo(db, tipo, alvo_id)
    if resumo is None or tipo not in ("produto", "vitrine", "loja"):
        raise LookupError
    with db:
        _registrar(db, admin_id, tipo, alvo_id, "reativar", motivo)
        if tipo == "produto":
            db.execute("UPDATE produto SET status = 'pausado' WHERE id = ? AND status = 'oculto'", (alvo_id,))
        elif tipo == "vitrine":
            db.execute("UPDATE perfil_produtor SET status = 'ativo' WHERE usuario_id = ?", (alvo_id,))
        else:
            db.execute("UPDATE perfil_comercio SET status = 'ativo' WHERE usuario_id = ?", (alvo_id,))
        notificar(db, resumo["dono"], "conteudo_moderado", f'A moderação voltou a mostrar "{resumo["titulo"]}".',
                  resumo["link"])


# ---------- usuários (RF25) ----------

def _bloquear(db, admin_id, usuario_id, motivo):
    alvo_usuario = db.execute("SELECT papel, status FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
    if alvo_usuario is None:
        raise LookupError
    if alvo_usuario["papel"] == "admin" or usuario_id == admin_id:
        raise RegraNegocio("Contas de administração não podem ser bloqueadas por aqui.")
    if alvo_usuario["status"] != "ativo":
        return
    _registrar(db, admin_id, "usuario", usuario_id, "bloquear_usuario", motivo)
    db.execute("UPDATE usuario SET status = 'bloqueado', atualizado_em = ? WHERE id = ?", (agora_utc_texto(), usuario_id))


def bloquear_usuario(db, admin_id, usuario_id, motivo):
    with db:
        _bloquear(db, admin_id, usuario_id, motivo)


def desbloquear_usuario(db, admin_id, usuario_id, motivo):
    with db:
        _registrar(db, admin_id, "usuario", usuario_id, "desbloquear_usuario", motivo)
        alterou = db.execute(
            "UPDATE usuario SET status = 'ativo', atualizado_em = ? WHERE id = ? AND status = 'bloqueado'",
            (agora_utc_texto(), usuario_id),
        ).rowcount
        if not alterou:
            raise RegraNegocio("Esta conta não está bloqueada.")


def buscar_usuarios(db, termo, limite=50):
    padrao = f"%{(termo or '').strip().lower()}%"
    return db.execute(
        """SELECT u.id, u.nome, u.email, u.papel, u.status, u.criado_em,
                  pp.nome_vitrine, pc.nome_fantasia, pc.verificado_em
             FROM usuario u
             LEFT JOIN perfil_produtor pp ON pp.usuario_id = u.id
             LEFT JOIN perfil_comercio pc ON pc.usuario_id = u.id
            WHERE lower(u.nome) LIKE ? OR lower(u.email) LIKE ? OR lower(COALESCE(pp.nome_vitrine, '')) LIKE ?
               OR lower(COALESCE(pc.nome_fantasia, '')) LIKE ?
            ORDER BY u.criado_em DESC LIMIT ?""",
        (padrao, padrao, padrao, padrao, limite),
    ).fetchall()


# ---------- lojas (RF38) ----------

def lojas(db, filtro="a_verificar"):
    condicao = {"a_verificar": "pc.verificado_em IS NULL", "verificadas": "pc.verificado_em IS NOT NULL"}.get(filtro, "1 = 1")
    return db.execute(
        f"""SELECT pc.*, u.nome AS conta_nome, u.status AS conta_status, m.nome AS municipio_nome, m.uf AS municipio_uf
              FROM perfil_comercio pc JOIN usuario u ON u.id = pc.usuario_id
              JOIN municipio m ON m.codigo_ibge = pc.municipio_id
             WHERE {condicao} ORDER BY pc.criado_em""",
    ).fetchall()


def verificar_loja(db, admin_id, usuario_id, verificar, motivo):
    with db:
        _registrar(db, admin_id, "loja", usuario_id, "verificar_loja" if verificar else "remover_verificacao", motivo)
        alterou = db.execute(
            "UPDATE perfil_comercio SET verificado_em = ?, verificado_por = ? WHERE usuario_id = ?",
            (agora_utc_texto() if verificar else None, admin_id if verificar else None, usuario_id),
        ).rowcount
        if not alterou:
            raise LookupError
        notificar(
            db, usuario_id, "conteudo_moderado",
            "Sua loja foi verificada pela equipe do AgroEncomenda." if verificar
            else f"O selo de loja verificada foi retirado. Motivo: {motivo.strip()[:200]}",
            f"/comercios/{usuario_id}",
        )


# ---------- categorias e unidades (RF20) ----------

def criar_categoria(db, admin_id, nome, pai_id):
    nome = " ".join((nome or "").split())
    if not 2 <= len(nome) <= 60:
        raise RegraNegocio("Use um nome de categoria entre 2 e 60 caracteres.")
    principal = db.execute("SELECT id FROM categoria WHERE id = ? AND categoria_pai_id IS NULL", (pai_id,)).fetchone()
    if principal is None:
        raise RegraNegocio("Escolha a categoria principal.")
    nomes = {normalizar_busca(linha[0]) for linha in db.execute("SELECT nome FROM categoria WHERE categoria_pai_id = ?", (pai_id,))}
    if normalizar_busca(nome) in nomes:
        raise RegraNegocio("Já existe uma subcategoria com esse nome.")
    with db:
        categoria_id = db.execute("INSERT INTO categoria (categoria_pai_id, nome) VALUES (?, ?)", (pai_id, nome)).lastrowid
        _registrar(db, admin_id, "categoria", categoria_id, "criar_categoria", f"Nova subcategoria: {nome}")
    return categoria_id


def alternar_categoria(db, admin_id, categoria_id, ativa, motivo):
    with db:
        alterou = db.execute("UPDATE categoria SET ativa = ? WHERE id = ?", (int(bool(ativa)), categoria_id)).rowcount
        if not alterou:
            raise LookupError
        _registrar(db, admin_id, "categoria", categoria_id, "ativar_categoria" if ativa else "desativar_categoria", motivo)


def criar_unidade(db, admin_id, sigla, nome):
    sigla, nome = (sigla or "").strip(), " ".join((nome or "").split())
    if not 1 <= len(sigla) <= 6 or not 2 <= len(nome) <= 40:
        raise RegraNegocio("Use uma sigla de até 6 caracteres e um nome entre 2 e 40 caracteres.")
    if db.execute("SELECT 1 FROM unidade_medida WHERE lower(sigla) = lower(?)", (sigla,)).fetchone():
        raise RegraNegocio("Já existe uma unidade com essa sigla.")
    with db:
        unidade_id = db.execute("INSERT INTO unidade_medida (sigla, nome) VALUES (?, ?)", (sigla, nome)).lastrowid
        _registrar(db, admin_id, "unidade", unidade_id, "criar_unidade", f"Nova unidade: {nome} ({sigla})")
    return unidade_id


# ---------- registro (RNF12) ----------

def registro(db, limite=200):
    return db.execute(
        """SELECT a.*, u.nome AS admin_nome FROM acao_moderacao a JOIN usuario u ON u.id = a.admin_id
            ORDER BY a.criada_em DESC, a.id DESC LIMIT ?""",
        (limite,),
    ).fetchall()


def resumo_do_painel(db):
    def contar(sql):
        return db.execute(sql).fetchone()[0]
    return {
        "denuncias_abertas": contar("SELECT COUNT(*) FROM denuncia WHERE status = 'aberta'"),
        "lojas_a_verificar": contar("SELECT COUNT(*) FROM perfil_comercio WHERE verificado_em IS NULL AND status = 'ativo'"),
        "usuarios": contar("SELECT COUNT(*) FROM usuario WHERE status = 'ativo'"),
        "bloqueados": contar("SELECT COUNT(*) FROM usuario WHERE status = 'bloqueado'"),
        "produtos_ativos": contar("SELECT COUNT(*) FROM produto WHERE status = 'ativo'"),
        "contratos_ativos": contar("SELECT COUNT(*) FROM contrato WHERE status = 'ativo'"),
    }
