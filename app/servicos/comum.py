"""Partes das regras de negócio usadas por encomendas e por produtos."""


class RegraNegocio(Exception):
    """Ação não permitida pelas regras do sistema. A mensagem é mostrada ao usuário."""


# Proposta com os dados das duas partes. A loja (perfil de comércio) do comprador e a vitrine do
# vendedor são dados de empresa e podem aparecer antes do aceite; nome completo e e-mail, não (D13).
SQL_PROPOSTA = """
    SELECT p.*, v.nome AS vendedor_nome, v.email AS vendedor_email,
           vm.nome AS vendedor_municipio, vm.uf AS vendedor_uf, pv.nome_vitrine AS vendedor_vitrine,
           c.nome AS comprador_nome, c.email AS comprador_email,
           cm.nome AS comprador_municipio, cm.uf AS comprador_uf,
           pc.nome_fantasia AS comprador_loja, pc.verificado_em IS NOT NULL AS comprador_loja_verificada,
           u.sigla AS unidade_sigla
      FROM proposta p
      JOIN usuario v                ON v.id = p.vendedor_id
      LEFT JOIN municipio vm        ON vm.codigo_ibge = v.municipio_id
      LEFT JOIN perfil_produtor pv  ON pv.usuario_id = p.vendedor_id
      JOIN usuario c                ON c.id = p.comprador_id
      LEFT JOIN municipio cm        ON cm.codigo_ibge = c.municipio_id
      LEFT JOIN perfil_comercio pc  ON pc.usuario_id = p.comprador_id
      JOIN unidade_medida u         ON u.id = p.unidade_id
"""


def buscar_proposta(db, proposta_id):
    return db.execute(SQL_PROPOSTA + " WHERE p.id = ?", (proposta_id,)).fetchone()


def notificar(db, usuario_id, tipo, texto, link):
    """Grava um aviso para o usuário. `link` é sempre um caminho interno ("/produtos/3")."""
    db.execute(
        "INSERT INTO notificacao (usuario_id, tipo, texto, link) VALUES (?, ?, ?, ?)",
        (usuario_id, tipo, texto, link),
    )


# ---------- avisos (RF13) ----------

def avisos_do_usuario(db, usuario_id, limite, deslocamento=0):
    return db.execute(
        "SELECT id, tipo, texto, link, criada_em, lida_em FROM notificacao WHERE usuario_id = ? "
        "ORDER BY lida_em IS NOT NULL, criada_em DESC, id DESC LIMIT ? OFFSET ?",
        (usuario_id, limite, deslocamento),
    ).fetchall()


def total_de_avisos(db, usuario_id):
    return db.execute("SELECT COUNT(*) FROM notificacao WHERE usuario_id = ?", (usuario_id,)).fetchone()[0]


def abrir_aviso(db, aviso_id, usuario_id):
    """Marca o aviso como lido e devolve o link dele. None se o aviso não é deste usuário."""
    aviso = db.execute(
        "SELECT link FROM notificacao WHERE id = ? AND usuario_id = ?", (aviso_id, usuario_id)
    ).fetchone()
    if aviso is None:
        return None
    with db:
        db.execute(
            "UPDATE notificacao SET lida_em = CURRENT_TIMESTAMP WHERE id = ? AND lida_em IS NULL", (aviso_id,)
        )
    return aviso["link"]


def marcar_todos_lidos(db, usuario_id):
    with db:
        return db.execute(
            "UPDATE notificacao SET lida_em = CURRENT_TIMESTAMP WHERE usuario_id = ? AND lida_em IS NULL", (usuario_id,)
        ).rowcount
