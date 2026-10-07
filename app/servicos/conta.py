"""Direitos do titular e acesso à conta (RF02, RF21; LGPD, art. 18).

- Exportar os próprios dados em JSON (acesso e portabilidade).
- Excluir a conta: os dados pessoais são apagados ou anonimizados. O que a outra parte precisa para o
  próprio histórico (mensagens recebidas, propostas, contratos e o registro de aceite) continua, mas com o
  autor como "Usuário removido". Contratos assinados guardam o texto aceito, que serve de prova para as
  duas partes (LGPD, art. 16, II: cumprimento de obrigação e exercício regular de direitos).
- Recuperar a senha: código de uso único, guardado só como hash SHA-256, que vale 1 hora.
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from ..util import agora_utc_texto, hoje
from .comum import RegraNegocio, notificar

VALIDADE_DO_CODIGO = timedelta(hours=1)
PEDIDOS_DE_CODIGO_POR_HORA = 3


# ---------- exportar (LGPD, art. 18, II e V) ----------

def _linhas(db, sql, *parametros):
    return [dict(linha) for linha in db.execute(sql, parametros).fetchall()]


def exportar_dados(db, usuario_id):
    conta = db.execute(
        """SELECT u.nome, u.email, u.tipo_pessoa, u.criado_em, u.termos_versao, u.termos_aceitos_em,
                  m.nome AS municipio, m.uf FROM usuario u LEFT JOIN municipio m ON m.codigo_ibge = u.municipio_id
            WHERE u.id = ?""",
        (usuario_id,),
    ).fetchone()
    dados = {
        "gerado_em_utc": agora_utc_texto(),
        "conta": dict(conta),
        "vitrine": _linhas(db, "SELECT * FROM perfil_produtor WHERE usuario_id = ?", usuario_id),
        "loja": _linhas(db, "SELECT * FROM perfil_comercio WHERE usuario_id = ?", usuario_id),
        "produtos": _linhas(db, "SELECT * FROM produto WHERE vendedor_id = ?", usuario_id),
        "encomendas": _linhas(db, "SELECT * FROM encomenda WHERE comprador_id = ?", usuario_id),
        "propostas": _linhas(db, "SELECT * FROM proposta WHERE comprador_id = ? OR vendedor_id = ?", usuario_id, usuario_id),
        "mensagens_enviadas": _linhas(
            db, "SELECT conversa_id, conteudo, enviada_em FROM mensagem WHERE remetente_id = ? ORDER BY id", usuario_id
        ),
        "contratos": _linhas(
            db, """SELECT c.id, c.status, v.versao, v.termos, v.hash FROM contrato c
                    LEFT JOIN contrato_versao v ON v.contrato_id = c.id AND v.versao = c.versao_atual
                   WHERE ? IN (c.produtor_id, c.comercio_id)""", usuario_id,
        ),
        "avisos": _linhas(db, "SELECT tipo, texto, criada_em, lida_em FROM notificacao WHERE usuario_id = ?", usuario_id),
        "denuncias_feitas": _linhas(
            db, "SELECT alvo_tipo, alvo_id, motivo, descricao, status, criada_em FROM denuncia WHERE denunciante_id = ?",
            usuario_id,
        ),
    }
    dados["vitrine"] = [{k: v for k, v in linha.items() if k != "nome_busca"} for linha in dados["vitrine"]]
    return json.dumps(dados, ensure_ascii=False, indent=2, default=str)


# ---------- excluir (LGPD, art. 18, VI) ----------

def excluir_conta(db, usuario_id):
    """Apaga ou anonimiza os dados da pessoa. Devolve os nomes das fotos para apagar do disco."""
    usuario = db.execute("SELECT email, papel, status FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
    if usuario is None or usuario["status"] == "excluido":
        raise LookupError
    if usuario["papel"] == "admin":
        raise RegraNegocio("Contas de administração não são excluídas por aqui.")
    fotos = [linha[0] for linha in db.execute(
        "SELECT f.arquivo FROM foto_produto f JOIN produto p ON p.id = f.produto_id WHERE p.vendedor_id = ?", (usuario_id,)
    )]
    vitrine = db.execute("SELECT foto FROM perfil_produtor WHERE usuario_id = ?", (usuario_id,)).fetchone()
    if vitrine and vitrine["foto"]:
        fotos.append(vitrine["foto"])
    agora = agora_utc_texto()

    with db:
        # Negociações em andamento terminam, com aviso para a outra parte.
        db.execute("UPDATE proposta SET status = 'retirada', respondida_em = ? WHERE autor_id = ? AND status = 'pendente'",
                   (agora, usuario_id))
        db.execute("""UPDATE proposta SET status = 'nao_selecionada', respondida_em = ?
                       WHERE (comprador_id = ? OR vendedor_id = ?) AND status = 'pendente'""", (agora, usuario_id, usuario_id))
        db.execute("UPDATE produto SET status = 'encerrado', atualizado_em = ? WHERE vendedor_id = ? AND status IN ('ativo', 'pausado')",
                   (agora, usuario_id))
        db.execute("DELETE FROM foto_produto WHERE produto_id IN (SELECT id FROM produto WHERE vendedor_id = ?)", (usuario_id,))
        db.execute("""UPDATE encomenda SET status = 'cancelada', encerrada_em = ?
                       WHERE comprador_id = ? AND status IN ('aberta', 'em_negociacao')""", (agora, usuario_id))
        _encerrar_contratos(db, usuario_id, agora)

        # Perfis saem do ar e perdem os dados pessoais.
        db.execute(
            """UPDATE perfil_produtor SET status = 'oculto', nome_vitrine = 'Vitrine removida', nome_busca = 'vitrine removida',
                      descricao = '', onde_encontrar = '', organico_registro = '', telefone_publico = NULL,
                      telefone_whatsapp = 0, foto = NULL, atualizado_em = ?
                WHERE usuario_id = ?""", (agora, usuario_id))
        db.execute(
            """UPDATE perfil_comercio SET status = 'oculto', nome_fantasia = 'Loja removida', nome_busca = 'loja removida',
                      descricao = '', volume_compra = '', telefone_publico = NULL, telefone_whatsapp = 0,
                      cnpj = ?, verificado_em = NULL, verificado_por = NULL, atualizado_em = ?
                WHERE usuario_id = ?""",
            (f"{usuario_id:012d}XX", agora, usuario_id),  # termina em letras: nunca coincide com um CNPJ válido
        )
        db.execute("DELETE FROM comercio_interesse WHERE usuario_id = ?", (usuario_id,))
        db.execute("DELETE FROM notificacao WHERE usuario_id = ?", (usuario_id,))
        db.execute("DELETE FROM redefinicao_senha WHERE usuario_id = ?", (usuario_id,))
        db.execute("DELETE FROM bloqueio_login WHERE email = ?", (usuario["email"],))
        db.execute(
            """UPDATE usuario SET nome = 'Usuário removido', email = ?, senha_hash = '!', telefone = NULL,
                      municipio_id = NULL, status = 'excluido', atualizado_em = ?
                WHERE id = ?""",
            (f"removido-{usuario_id}@invalido.example", agora, usuario_id),
        )
    return fotos


def _encerrar_contratos(db, usuario_id, agora):
    contratos = db.execute(
        "SELECT * FROM contrato WHERE ? IN (produtor_id, comercio_id) AND status IN ('rascunho', 'enviado', 'ativo')",
        (usuario_id,),
    ).fetchall()
    for contrato in contratos:
        outro = contrato["comercio_id"] if usuario_id == contrato["produtor_id"] else contrato["produtor_id"]
        if contrato["status"] == "rascunho":
            if contrato["autor_id"] == usuario_id:
                db.execute("DELETE FROM contrato_item WHERE contrato_id = ?", (contrato["id"],))
                db.execute("DELETE FROM contrato WHERE id = ?", (contrato["id"],))
            continue
        if contrato["status"] == "enviado":
            db.execute("""UPDATE contrato SET status = 'cancelado', aguardando_id = NULL, encerrado_em = ?,
                                 motivo_encerramento = 'Conta excluída' WHERE id = ?""", (agora, contrato["id"]))
            texto = f"A proposta de contrato nº {contrato['id']} foi cancelada: a outra parte excluiu a conta."
        else:
            efetiva = (hoje() + timedelta(days=contrato["aviso_previo_dias"])).isoformat()
            db.execute("""UPDATE contrato SET status = 'rescindido', encerrado_em = ?, rescisao_efetiva_em = ?,
                                 motivo_encerramento = 'Conta excluída' WHERE id = ?""", (agora, efetiva, contrato["id"]))
            texto = (f"O contrato nº {contrato['id']} foi rescindido porque a outra parte excluiu a conta. "
                     f"Combinem as entregas do aviso prévio pelo contato que vocês já têm.")
        notificar(db, outro, "contrato", texto, f"/contratos/{contrato['id']}")


# ---------- recuperar a senha (RF02) ----------

def _hash(codigo):
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def _agora():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _texto(momento):
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def criar_codigo_de_redefinicao(db, email):
    """Cria o código para a conta deste e-mail. Devolve o código ou None (e-mail desconhecido ou limite).

    A tela responde sempre a mesma coisa, para não revelar quais e-mails têm conta.
    """
    usuario = db.execute("SELECT id FROM usuario WHERE email = ? AND status = 'ativo'", (email,)).fetchone()
    if usuario is None:
        return None
    recentes = db.execute(
        "SELECT COUNT(*) FROM redefinicao_senha WHERE usuario_id = ? AND criado_em >= datetime('now', '-1 hour')",
        (usuario["id"],),
    ).fetchone()[0]
    if recentes >= PEDIDOS_DE_CODIGO_POR_HORA:
        return None
    codigo = secrets.token_urlsafe(32)
    with db:
        db.execute(
            "INSERT INTO redefinicao_senha (usuario_id, codigo_hash, expira_em) VALUES (?, ?, ?)",
            (usuario["id"], _hash(codigo), _texto(_agora() + VALIDADE_DO_CODIGO)),
        )
    return codigo


def conta_do_codigo(db, codigo):
    """A conta dona do código, se ele ainda vale (não usado, não vencido). Senão, None."""
    return db.execute(
        """SELECT r.id AS pedido_id, u.id, u.email FROM redefinicao_senha r JOIN usuario u ON u.id = r.usuario_id
            WHERE r.codigo_hash = ? AND r.usado_em IS NULL AND r.expira_em > ? AND u.status = 'ativo'""",
        (_hash(codigo or ""), _texto(_agora())),
    ).fetchone()


def redefinir_senha(db, codigo, novo_hash):
    conta = conta_do_codigo(db, codigo)
    if conta is None:
        raise RegraNegocio("Este link não vale mais. Peça um novo.")
    agora = _texto(_agora())
    with db:
        usado = db.execute(
            "UPDATE redefinicao_senha SET usado_em = ? WHERE id = ? AND usado_em IS NULL", (agora, conta["pedido_id"])
        ).rowcount
        if not usado:
            raise RegraNegocio("Este link não vale mais. Peça um novo.")
        # Os outros códigos pendentes da mesma conta deixam de valer.
        db.execute("UPDATE redefinicao_senha SET usado_em = ? WHERE usuario_id = ? AND usado_em IS NULL", (agora, conta["id"]))
        db.execute("UPDATE usuario SET senha_hash = ?, atualizado_em = ? WHERE id = ?", (novo_hash, agora, conta["id"]))
        db.execute("DELETE FROM bloqueio_login WHERE email = ?", (conta["email"],))
    return conta["id"]
