"""Conversas entre produtor, loja e consumidor (RF33).

Uma conversa liga duas pessoas e um assunto: um produto, uma vitrine, uma loja, uma encomenda ou uma
proposta. Quem é a outra pessoa sai sempre do assunto, consultado no servidor (nunca do formulário).

Regras:
- só os dois participantes leem e escrevem;
- a página e o contato de lojas são só para produtores (RN06), então só produtor começa conversa com loja;
- limite de conversas novas por dia e de mensagens por hora, contra spam;
- antes do aceite de uma proposta, cada lado vê o primeiro nome e os nomes de vitrine ou loja (D13).
"""
from flask import current_app

from ..util import primeiro_nome
from .comum import RegraNegocio, notificar

CONTEXTOS = ("produto", "vitrine", "loja", "encomenda", "proposta", "contrato")
TAMANHO_MAXIMO = 2000


class AssuntoInexistente(Exception):
    """O assunto não existe ou não pode ser visto (a rota responde 404)."""


class SoProdutores(Exception):
    """Só quem tem vitrine de produtor pode falar com lojas (a rota responde 403)."""


SQL_CONVERSA = """
    SELECT c.*, o.id AS outro_id, o.nome AS outro_nome,
           pp.nome_vitrine AS outro_vitrine, pc.nome_fantasia AS outro_loja,
           pc.verificado_em IS NOT NULL AS outro_loja_verificada,
           (SELECT conteudo FROM mensagem m WHERE m.conversa_id = c.id ORDER BY m.id DESC LIMIT 1) AS ultima,
           (SELECT remetente_id FROM mensagem m WHERE m.conversa_id = c.id ORDER BY m.id DESC LIMIT 1) AS ultima_de,
           (SELECT COUNT(*) FROM mensagem m
             WHERE m.conversa_id = c.id AND m.remetente_id <> ? AND m.lida_em IS NULL) AS nao_lidas
      FROM conversa c
      JOIN usuario o               ON o.id = CASE WHEN c.usuario_a_id = ? THEN c.usuario_b_id ELSE c.usuario_a_id END
      LEFT JOIN perfil_produtor pp ON pp.usuario_id = o.id
      LEFT JOIN perfil_comercio pc ON pc.usuario_id = o.id
"""


def nome_publico(nome, vitrine=None, loja=None):
    """Primeiro nome e, se houver, os nomes de vitrine e loja: "Ana · Sítio Boa Vista"."""
    return " · ".join(parte for parte in (primeiro_nome(nome), vitrine, loja) if parte)


def conversas_do_usuario(db, usuario_id, limite=50):
    return db.execute(
        SQL_CONVERSA + " WHERE ? IN (c.usuario_a_id, c.usuario_b_id) ORDER BY c.ultima_mensagem_em DESC, c.id DESC LIMIT ?",
        (usuario_id, usuario_id, usuario_id, limite),
    ).fetchall()


def buscar_conversa(db, conversa_id, usuario_id):
    """A conversa, vista por um participante. None se não existe ou se a pessoa não participa dela."""
    return db.execute(
        SQL_CONVERSA + " WHERE c.id = ? AND ? IN (c.usuario_a_id, c.usuario_b_id)",
        (usuario_id, usuario_id, conversa_id, usuario_id),
    ).fetchone()


def mensagens_da_conversa(db, conversa_id):
    return db.execute(
        "SELECT id, remetente_id, conteudo, enviada_em, lida_em FROM mensagem WHERE conversa_id = ? ORDER BY id",
        (conversa_id,),
    ).fetchall()


def marcar_lidas(db, conversa_id, leitor_id):
    with db:
        db.execute(
            "UPDATE mensagem SET lida_em = CURRENT_TIMESTAMP "
            "WHERE conversa_id = ? AND remetente_id <> ? AND lida_em IS NULL",
            (conversa_id, leitor_id),
        )


# ---------- assunto da conversa ----------

def assunto(db, tipo, contexto_id):
    """(título, link) do assunto, para mostrar no topo da conversa. Ex.: ('Alface crespa', '/produtos/1')."""
    if tipo == "produto":
        linha = db.execute("SELECT titulo FROM produto WHERE id = ?", (contexto_id,)).fetchone()
        return (linha["titulo"] if linha else "Produto removido"), f"/produtos/{contexto_id}"
    if tipo == "vitrine":
        linha = db.execute("SELECT nome_vitrine FROM perfil_produtor WHERE usuario_id = ?", (contexto_id,)).fetchone()
        return (f"Vitrine {linha['nome_vitrine']}" if linha else "Vitrine"), f"/produtores/{contexto_id}"
    if tipo == "loja":
        linha = db.execute("SELECT nome_fantasia FROM perfil_comercio WHERE usuario_id = ?", (contexto_id,)).fetchone()
        return (f"Loja {linha['nome_fantasia']}" if linha else "Loja"), f"/comercios/{contexto_id}"
    if tipo == "encomenda":
        linha = db.execute("SELECT titulo FROM encomenda WHERE id = ?", (contexto_id,)).fetchone()
        return (f"Encomenda: {linha['titulo']}" if linha else "Encomenda"), f"/encomendas/{contexto_id}"
    if tipo == "contrato":
        return f"Contrato de fornecimento nº {contexto_id}", f"/contratos/{contexto_id}"
    if tipo == "proposta":
        linha = db.execute(
            """SELECT p.encomenda_id, p.produto_id, COALESCE(e.titulo, pd.titulo) AS titulo
                 FROM proposta p LEFT JOIN encomenda e ON e.id = p.encomenda_id
                 LEFT JOIN produto pd ON pd.id = p.produto_id WHERE p.id = ?""",
            (contexto_id,),
        ).fetchone()
        if linha is None:
            return "Proposta", "/painel"
        link = f"/encomendas/{linha['encomenda_id']}" if linha["encomenda_id"] else f"/produtos/{linha['produto_id']}"
        return f"Proposta: {linha['titulo']}", link
    return "Conversa", "/mensagens"


def destinatario(db, tipo, contexto_id, remetente_id, remetente_e_produtor):
    """Com quem a pessoa vai conversar sobre este assunto. Levanta AssuntoInexistente ou SoProdutores."""
    if tipo == "produto":
        linha = db.execute("SELECT vendedor_id FROM produto WHERE id = ? AND status <> 'oculto'", (contexto_id,)).fetchone()
        outro = linha["vendedor_id"] if linha else None
    elif tipo == "vitrine":
        linha = db.execute(
            "SELECT usuario_id FROM perfil_produtor WHERE usuario_id = ? AND status = 'ativo'", (contexto_id,)
        ).fetchone()
        outro = linha["usuario_id"] if linha else None
    elif tipo == "loja":
        if not remetente_e_produtor:
            raise SoProdutores
        linha = db.execute(
            "SELECT usuario_id FROM perfil_comercio WHERE usuario_id = ? AND status = 'ativo'", (contexto_id,)
        ).fetchone()
        outro = linha["usuario_id"] if linha else None
    elif tipo == "encomenda":
        linha = db.execute("SELECT comprador_id FROM encomenda WHERE id = ?", (contexto_id,)).fetchone()
        outro = linha["comprador_id"] if linha else None
    elif tipo == "proposta":
        linha = db.execute("SELECT comprador_id, vendedor_id FROM proposta WHERE id = ?", (contexto_id,)).fetchone()
        if linha is None or remetente_id not in (linha["comprador_id"], linha["vendedor_id"]):
            raise AssuntoInexistente  # quem não é parte da proposta nem fica sabendo que ela existe
        outro = linha["vendedor_id"] if remetente_id == linha["comprador_id"] else linha["comprador_id"]
    elif tipo == "contrato":
        linha = db.execute("SELECT produtor_id, comercio_id, autor_id, status FROM contrato WHERE id = ?",
                           (contexto_id,)).fetchone()
        partes = (linha["produtor_id"], linha["comercio_id"]) if linha else ()
        if remetente_id not in partes or linha["status"] == "rascunho":
            raise AssuntoInexistente  # rascunho só existe para o autor e ainda não tem com quem conversar
        outro = linha["comercio_id"] if remetente_id == linha["produtor_id"] else linha["produtor_id"]
    else:
        outro = None
    if outro is None:
        raise AssuntoInexistente
    ativo = db.execute("SELECT 1 FROM usuario WHERE id = ? AND status = 'ativo'", (outro,)).fetchone()
    if not ativo:
        raise AssuntoInexistente
    if outro == remetente_id:
        raise RegraNegocio("Este assunto é seu. Não dá para mandar mensagem para você mesmo.")
    return outro


def conversa_existente(db, tipo, contexto_id, usuario_1, usuario_2):
    a, b = sorted((usuario_1, usuario_2))
    linha = db.execute(
        "SELECT id FROM conversa WHERE contexto_tipo = ? AND contexto_id = ? AND usuario_a_id = ? AND usuario_b_id = ?",
        (tipo, contexto_id, a, b),
    ).fetchone()
    return linha["id"] if linha else None


# ---------- enviar ----------

def _limpar(texto):
    texto = (texto or "").strip()
    if not texto:
        raise RegraNegocio("Escreva a mensagem.")
    if len(texto) > TAMANHO_MAXIMO:
        raise RegraNegocio(f"Use no máximo {TAMANHO_MAXIMO} caracteres.")
    return texto


def _conferir_ritmo(db, usuario_id, conversa_nova):
    limite_hora = current_app.config["MENSAGENS_POR_HORA"]
    na_hora = db.execute(
        "SELECT COUNT(*) FROM mensagem WHERE remetente_id = ? AND enviada_em >= datetime('now', '-1 hour')",
        (usuario_id,),
    ).fetchone()[0]
    if na_hora >= limite_hora:
        raise RegraNegocio("Você mandou muitas mensagens na última hora. Espere um pouco e tente de novo.")
    if conversa_nova:
        limite_dia = current_app.config["CONVERSAS_NOVAS_POR_DIA"]
        no_dia = db.execute(
            "SELECT COUNT(*) FROM conversa WHERE iniciada_por = ? AND criada_em >= datetime('now', '-1 day')",
            (usuario_id,),
        ).fetchone()[0]
        if no_dia >= limite_dia:
            raise RegraNegocio(f"Você já começou {limite_dia} conversas nas últimas 24 horas. Tente de novo amanhã.")


def _gravar_mensagem(db, conversa_id, remetente_id, texto):
    db.execute(
        "INSERT INTO mensagem (conversa_id, remetente_id, conteudo) VALUES (?, ?, ?)", (conversa_id, remetente_id, texto)
    )
    db.execute("UPDATE conversa SET ultima_mensagem_em = CURRENT_TIMESTAMP WHERE id = ?", (conversa_id,))


def iniciar_conversa(db, tipo, contexto_id, remetente, texto):
    """Começa (ou continua, se já existe) a conversa sobre o assunto. Devolve o id da conversa.

    `remetente` é a linha de g.usuario (precisa de id, nome e tem_produtor).
    """
    if tipo not in CONTEXTOS:
        raise AssuntoInexistente
    texto = _limpar(texto)
    outro = destinatario(db, tipo, contexto_id, remetente["id"], bool(remetente["tem_produtor"]))
    existente = conversa_existente(db, tipo, contexto_id, remetente["id"], outro)
    _conferir_ritmo(db, remetente["id"], conversa_nova=existente is None)
    with db:
        if existente:
            conversa_id = existente
        else:
            a, b = sorted((remetente["id"], outro))
            conversa_id = db.execute(
                "INSERT INTO conversa (contexto_tipo, contexto_id, usuario_a_id, usuario_b_id, iniciada_por) "
                "VALUES (?, ?, ?, ?, ?)",
                (tipo, contexto_id, a, b, remetente["id"]),
            ).lastrowid
            titulo, _ = assunto(db, tipo, contexto_id)
            notificar(
                db, outro, "nova_mensagem",
                f"{primeiro_nome(remetente['nome'])} mandou uma mensagem sobre {titulo}.", f"/mensagens/{conversa_id}",
            )
        _gravar_mensagem(db, conversa_id, remetente["id"], texto)
    return conversa_id


def responder(db, conversa, remetente_id, texto):
    """Nova mensagem numa conversa existente. `conversa` vem de buscar_conversa (já confere o participante)."""
    if remetente_id not in (conversa["usuario_a_id"], conversa["usuario_b_id"]):
        raise PermissionError
    texto = _limpar(texto)
    _conferir_ritmo(db, remetente_id, conversa_nova=False)
    with db:
        _gravar_mensagem(db, conversa["id"], remetente_id, texto)
