"""Consultas e gravação dos perfis de produtor e de comércio (RF26, RF27, RF30)."""
import sqlite3

from ..util import agora_utc_texto, normalizar_busca

SQL_PRODUTOR = """
    SELECT pp.*, m.nome AS municipio_nome, m.uf AS municipio_uf, m.regiao_imediata_id,
           r.nome AS regiao_nome, u.nome AS conta_nome, u.criado_em AS desde, u.status AS conta_status,
           (SELECT COUNT(*) FROM produto pd WHERE pd.vendedor_id = pp.usuario_id AND pd.status = 'ativo') AS produtos_ativos
      FROM perfil_produtor pp
      JOIN usuario u   ON u.id = pp.usuario_id
      JOIN municipio m ON m.codigo_ibge = pp.municipio_id
      LEFT JOIN regiao_imediata r ON r.id = m.regiao_imediata_id
"""

SQL_COMERCIO = """
    SELECT pc.*, m.nome AS municipio_nome, m.uf AS municipio_uf, m.regiao_imediata_id,
           r.nome AS regiao_nome, u.nome AS conta_nome, u.criado_em AS desde, u.status AS conta_status
      FROM perfil_comercio pc
      JOIN usuario u   ON u.id = pc.usuario_id
      JOIN municipio m ON m.codigo_ibge = pc.municipio_id
      LEFT JOIN regiao_imediata r ON r.id = m.regiao_imediata_id
"""

CAMPOS_PRODUTOR = (
    "nome_vitrine", "descricao", "municipio_id", "vende_retirada", "vende_entrega", "vende_feira", "vende_envio",
    "onde_encontrar", "organico", "organico_registro", "telefone_publico", "telefone_whatsapp",
)
CAMPOS_COMERCIO = (
    "nome_fantasia", "cnpj", "tipo", "descricao", "municipio_id", "volume_compra",
    "telefone_publico", "telefone_whatsapp",
)


class CnpjEmUso(Exception):
    """O CNPJ já está em outro perfil de comércio."""


def perfil_produtor(db, usuario_id):
    return db.execute(SQL_PRODUTOR + " WHERE pp.usuario_id = ?", (usuario_id,)).fetchone()


def perfil_comercio(db, usuario_id):
    return db.execute(SQL_COMERCIO + " WHERE pc.usuario_id = ?", (usuario_id,)).fetchone()


def interesses_do_comercio(db, usuario_id):
    return db.execute(
        """SELECT c.id, c.nome FROM comercio_interesse ci JOIN categoria c ON c.id = ci.categoria_id
            WHERE ci.usuario_id = ? ORDER BY c.id""",
        (usuario_id,),
    ).fetchall()


def categorias_dos_produtores(db, ids, publico="1 = 1"):
    """Categorias em que cada produtor tem produto ativo: {usuario_id: ['Hortaliças e verduras', ...]}.

    `publico` é a condição de visibilidade (visibilidade.publico_sql), para contar só o que a pessoa vê.
    """
    if not ids:
        return {}
    marcadores = ", ".join("?" * len(ids))
    resultado = {}
    for linha in db.execute(
        f"""SELECT DISTINCT pd.vendedor_id, c.nome FROM produto pd JOIN categoria c ON c.id = pd.categoria_id
             WHERE pd.status = 'ativo' AND {publico} AND pd.vendedor_id IN ({marcadores}) ORDER BY c.id""",
        list(ids),
    ):
        resultado.setdefault(linha["vendedor_id"], []).append(linha["nome"])
    return resultado


def produtos_por_produtor(db, ids, publico="1 = 1"):
    """Quantos produtos ativos cada produtor tem, contando só os que a pessoa vê: {usuario_id: n}."""
    if not ids:
        return {}
    marcadores = ", ".join("?" * len(ids))
    return {
        linha["vendedor_id"]: linha["total"]
        for linha in db.execute(
            f"""SELECT pd.vendedor_id, COUNT(*) AS total FROM produto pd
                 WHERE pd.status = 'ativo' AND {publico} AND pd.vendedor_id IN ({marcadores})
                 GROUP BY pd.vendedor_id""",
            list(ids),
        )
    }


def interesses_dos_comercios(db, ids):
    if not ids:
        return {}
    marcadores = ", ".join("?" * len(ids))
    resultado = {}
    for linha in db.execute(
        f"""SELECT ci.usuario_id, c.nome FROM comercio_interesse ci JOIN categoria c ON c.id = ci.categoria_id
             WHERE ci.usuario_id IN ({marcadores}) ORDER BY c.id""",
        list(ids),
    ):
        resultado.setdefault(linha["usuario_id"], []).append(linha["nome"])
    return resultado


def _completar_municipio_da_conta(db, usuario_id, municipio_id):
    db.execute("UPDATE usuario SET municipio_id = ? WHERE id = ? AND municipio_id IS NULL", (municipio_id, usuario_id))


def salvar_perfil_produtor(db, usuario_id, dados, nova_foto=None, remover_foto=False):
    """Cria ou atualiza a vitrine. Devolve o nome da foto antiga que saiu (para apagar do disco) ou None."""
    atual = db.execute("SELECT foto FROM perfil_produtor WHERE usuario_id = ?", (usuario_id,)).fetchone()
    foto_antiga = atual["foto"] if atual else None
    foto = nova_foto or (None if remover_foto else foto_antiga)
    valores = [dados[campo] for campo in CAMPOS_PRODUTOR]
    with db:
        if atual is None:
            db.execute(
                f"""INSERT INTO perfil_produtor (usuario_id, nome_busca, foto, {', '.join(CAMPOS_PRODUTOR)})
                    VALUES (?, ?, ?, {', '.join('?' * len(CAMPOS_PRODUTOR))})""",
                [usuario_id, normalizar_busca(dados["nome_vitrine"]), foto, *valores],
            )
        else:
            db.execute(
                f"""UPDATE perfil_produtor
                       SET nome_busca = ?, foto = ?, atualizado_em = ?, {', '.join(f'{c} = ?' for c in CAMPOS_PRODUTOR)}
                     WHERE usuario_id = ?""",
                [normalizar_busca(dados["nome_vitrine"]), foto, agora_utc_texto(), *valores, usuario_id],
            )
        _completar_municipio_da_conta(db, usuario_id, dados["municipio_id"])
    return foto_antiga if foto_antiga and foto_antiga != foto else None


def salvar_perfil_comercio(db, usuario_id, dados, interesses):
    """Cria ou atualiza o perfil de comércio e as categorias de interesse.

    Trocar o CNPJ tira o selo de verificado. Levanta CnpjEmUso se o CNPJ já tem dono.
    """
    dono = db.execute("SELECT usuario_id FROM perfil_comercio WHERE cnpj = ?", (dados["cnpj"],)).fetchone()
    if dono and dono["usuario_id"] != usuario_id:
        raise CnpjEmUso
    atual = db.execute("SELECT cnpj FROM perfil_comercio WHERE usuario_id = ?", (usuario_id,)).fetchone()
    valores = [dados[campo] for campo in CAMPOS_COMERCIO]
    try:
        _gravar_comercio(db, usuario_id, dados, interesses, atual, valores)
    except sqlite3.IntegrityError as erro:
        if "cnpj" in str(erro):  # outra pessoa cadastrou o mesmo CNPJ ao mesmo tempo
            raise CnpjEmUso from erro
        raise


def _gravar_comercio(db, usuario_id, dados, interesses, atual, valores):
    with db:
        if atual is None:
            db.execute(
                f"""INSERT INTO perfil_comercio (usuario_id, nome_busca, {', '.join(CAMPOS_COMERCIO)})
                    VALUES (?, ?, {', '.join('?' * len(CAMPOS_COMERCIO))})""",
                [usuario_id, normalizar_busca(dados["nome_fantasia"]), *valores],
            )
        else:
            db.execute(
                f"""UPDATE perfil_comercio
                       SET nome_busca = ?, atualizado_em = ?, {', '.join(f'{c} = ?' for c in CAMPOS_COMERCIO)}
                     WHERE usuario_id = ?""",
                [normalizar_busca(dados["nome_fantasia"]), agora_utc_texto(), *valores, usuario_id],
            )
            if atual["cnpj"] != dados["cnpj"]:
                db.execute(
                    "UPDATE perfil_comercio SET verificado_em = NULL, verificado_por = NULL WHERE usuario_id = ?",
                    (usuario_id,),
                )
        db.execute("DELETE FROM comercio_interesse WHERE usuario_id = ?", (usuario_id,))
        db.executemany(
            "INSERT INTO comercio_interesse (usuario_id, categoria_id) VALUES (?, ?)",
            [(usuario_id, categoria_id) for categoria_id in interesses],
        )
        _completar_municipio_da_conta(db, usuario_id, dados["municipio_id"])


def salvar_conta(db, usuario_id, nome, tipo_pessoa, municipio_id):
    with db:
        db.execute(
            "UPDATE usuario SET nome = ?, tipo_pessoa = ?, municipio_id = ?, atualizado_em = ? WHERE id = ?",
            (nome, tipo_pessoa, municipio_id, agora_utc_texto(), usuario_id),
        )


def verificar_comercio(db, usuario_id, verificado=True, admin_id=None):
    with db:
        cursor = db.execute(
            "UPDATE perfil_comercio SET verificado_em = ?, verificado_por = ? WHERE usuario_id = ?",
            (agora_utc_texto() if verificado else None, admin_id if verificado else None, usuario_id),
        )
    return cursor.rowcount == 1
