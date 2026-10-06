"""Municípios (código IBGE) para formulários e filtros."""
import re

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
