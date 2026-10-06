"""Municípios (código IBGE) para formulários e filtros."""
import re

from flask import g, request, session

from .db import UFS
from .util import normalizar_busca


def rotulo(nome, uf):
    return f"{nome}/{uf}"


def municipios_para_lista(db):
    """Valores do <datalist> de municípios, no formato 'Nome/UF'."""
    return [rotulo(linha["nome"], linha["uf"]) for linha in db.execute("SELECT nome, uf FROM municipio ORDER BY uf, nome")]


def ufs_carregadas(db):
    return [linha["uf"] for linha in db.execute("SELECT DISTINCT uf FROM municipio ORDER BY uf")]


def rotulo_do_codigo(db, codigo):
    if codigo is None:
        return ""
    linha = db.execute("SELECT nome, uf FROM municipio WHERE codigo_ibge = ?", (codigo,)).fetchone()
    return rotulo(linha["nome"], linha["uf"]) if linha else ""


def resolver_municipio(db, texto):
    """Converte 'Uberaba/MG', 'uberaba - mg' ou 'Uberaba MG' no código IBGE. Devolve None se não achar."""
    partes = re.match(r"^\s*(.+?)\s*(?:[/\-,]\s*|\s+)([A-Za-z]{2})\s*$", texto or "")
    if not partes or partes.group(2).upper() not in UFS:
        return None
    nome, uf = normalizar_busca(partes.group(1)), partes.group(2).upper()
    for linha in db.execute("SELECT codigo_ibge, nome FROM municipio WHERE uf = ?", (uf,)):
        if normalizar_busca(linha["nome"]) == nome:
            return linha["codigo_ibge"]
    return None


# ---------- região (RF30) ----------

def dados_municipio(db, codigo):
    """Município com UF e região imediata, ou None."""
    if codigo is None:
        return None
    return db.execute(
        """SELECT m.codigo_ibge, m.nome, m.uf, m.regiao_imediata_id, r.nome AS regiao_nome
             FROM municipio m LEFT JOIN regiao_imediata r ON r.id = m.regiao_imediata_id
            WHERE m.codigo_ibge = ?""",
        (codigo,),
    ).fetchone()


def proximidade_sql(alias, referencia):
    """Expressão de ordenação: 0 = mesmo município, 1 = mesma região imediata, 2 = mesma UF, 3 = resto.

    `alias` é o apelido da tabela municipio na consulta. Sem referência, todos empatam.
    """
    if referencia is None:
        return "NULL", []  # constante; "0" seria lido como "coluna 0" no ORDER BY
    return (
        f"CASE WHEN {alias}.codigo_ibge = ? THEN 0 "
        f"WHEN {alias}.regiao_imediata_id IS NOT NULL AND {alias}.regiao_imediata_id = ? THEN 1 "
        f"WHEN {alias}.uf = ? THEN 2 ELSE 3 END",
        [referencia["codigo_ibge"], referencia["regiao_imediata_id"], referencia["uf"]],
    )


def municipio_de_referencia(db):
    """Cidade usada para ordenar por proximidade. Devolve (município ou None, texto com erro ou None).

    Ordem: ?perto=Município/UF (fica guardado na sessão), cidade guardada, cidade da conta.
    Não usamos GPS: a pessoa escolhe a cidade (pesquisa, seção 10.2.4).
    """
    erro = None
    if "perto" in request.args:
        texto = request.args.get("perto", "").strip()[:80]
        if not texto:
            session.pop("perto", None)
        else:
            codigo = resolver_municipio(db, texto)
            if codigo is None:
                erro = f"Não encontramos “{texto}”. Escolha da lista, no formato Município/UF."
            else:
                session["perto"] = codigo
    codigo = session.get("perto")
    if codigo is None and g.usuario:
        codigo = g.usuario["municipio_id"]
    return dados_municipio(db, codigo), erro
