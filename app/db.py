"""Acesso ao banco SQLite e comandos de linha de comando do banco."""
import gzip
import json
import sqlite3
import urllib.request

import click
from flask import current_app, g
from flask.cli import with_appcontext

UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}

URL_MUNICIPIOS_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"


def get_db():
    """Conexão da requisição atual, com chaves estrangeiras ativadas.

    O SQLite vem com as chaves estrangeiras desligadas e exige ativação
    em cada conexão (https://sqlite.org/foreignkeys.html).
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as arquivo:
        db.executescript(arquivo.read().decode("utf-8"))
    with current_app.open_resource("seed.sql") as arquivo:
        db.executescript(arquivo.read().decode("utf-8"))


def buscar_municipios_ibge(uf):
    """Municípios de uma UF pela API de Localidades do IBGE.

    Devolve (código IBGE, nome, id da região imediata, nome da região imediata).
    """
    pedido = urllib.request.Request(URL_MUNICIPIOS_IBGE.format(uf=uf), headers={"Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        corpo = resposta.read()
    if corpo[:2] == b"\x1f\x8b":  # a API do IBGE pode responder compactada em gzip
        corpo = gzip.decompress(corpo)
    dados = json.loads(corpo.decode("utf-8"))
    municipios = []
    for item in dados:
        regiao = item.get("regiao-imediata") or {}
        municipios.append((item["id"], item["nome"], regiao.get("id"), regiao.get("nome")))
    return municipios


def salvar_municipios(uf, municipios):
    """Grava ou atualiza municípios. Cada item: (código, nome) ou (código, nome, id_regiao, nome_regiao)."""
    db = get_db()
    linhas = [tuple(item) + (None, None) if len(item) == 2 else tuple(item) for item in municipios]
    with db:
        db.executemany(
            """INSERT INTO regiao_imediata (id, nome, uf) VALUES (?, ?, ?)
               ON CONFLICT (id) DO UPDATE SET nome = excluded.nome, uf = excluded.uf""",
            {(regiao_id, regiao_nome, uf) for _, _, regiao_id, regiao_nome in linhas if regiao_id},
        )
        db.executemany(
            """INSERT INTO municipio (codigo_ibge, nome, uf, regiao_imediata_id) VALUES (?, ?, ?, ?)
               ON CONFLICT (codigo_ibge) DO UPDATE SET
                   nome = excluded.nome, uf = excluded.uf,
                   regiao_imediata_id = COALESCE(excluded.regiao_imediata_id, municipio.regiao_imediata_id)""",
            [(codigo, nome, uf, regiao_id) for codigo, nome, regiao_id, _ in linhas],
        )


@click.command("init-db")
@click.confirmation_option(prompt="Isso apaga todos os dados do banco. Continuar?")
@with_appcontext
def init_db_command():
    """Cria (ou recria) as tabelas e carrega categorias e unidades de medida."""
    init_db()
    click.echo("Banco criado e dados iniciais carregados.")


@click.command("carregar-municipios")
@click.argument("uf")
@with_appcontext
def carregar_municipios_command(uf):
    """Carrega os municípios de uma UF a partir da API do IBGE (ex.: MG)."""
    uf = uf.upper()
    if uf not in UFS:
        raise click.BadParameter(f"UF inválida: {uf}")
    municipios = buscar_municipios_ibge(uf)
    salvar_municipios(uf, municipios)
    click.echo(f"{len(municipios)} municípios de {uf} carregados.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(carregar_municipios_command)
