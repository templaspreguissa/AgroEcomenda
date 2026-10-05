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
    """Lista de (código IBGE, nome) dos municípios de uma UF, pela API de Localidades do IBGE."""
    pedido = urllib.request.Request(URL_MUNICIPIOS_IBGE.format(uf=uf), headers={"Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        corpo = resposta.read()
    if corpo[:2] == b"\x1f\x8b":  # a API do IBGE pode responder compactada em gzip
        corpo = gzip.decompress(corpo)
    dados = json.loads(corpo.decode("utf-8"))
    return [(item["id"], item["nome"]) for item in dados]


def salvar_municipios(uf, municipios):
    db = get_db()
    with db:
        db.executemany(
            "INSERT OR IGNORE INTO municipio (codigo_ibge, nome, uf) VALUES (?, ?, ?)",
            [(codigo, nome, uf) for codigo, nome in municipios],
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
