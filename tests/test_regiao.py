"""Busca por região: município, região imediata do IBGE e UF (RF30)."""
from datetime import date, timedelta

import pytest

from app import servicos
from app.db import get_db, salvar_municipios

from .conftest import (
    BELO_HORIZONTE, GOIANIA, SACRAMENTO, UBERABA, cliente_logado, criar_produtor, criar_usuario,
)


@pytest.fixture
def produtores(app):
    """Um produtor em cada cidade de teste."""
    for nome, municipio in [("Goiânia Hortas", GOIANIA), ("BH Orgânicos", BELO_HORIZONTE),
                            ("Sacramento Queijos", SACRAMENTO), ("Uberaba Verde", UBERABA)]:
        usuario = criar_usuario(app, nome, f"{municipio}@exemplo.com")
        criar_produtor(app, usuario, nome, municipio_id=municipio)


def ordem(html, nomes):
    return sorted(nomes, key=html.index)


NOMES = ["Uberaba Verde", "Sacramento Queijos", "BH Orgânicos", "Goiânia Hortas"]


def test_mais_perto_primeiro(produtores, client):
    html = client.get("/produtores?perto=Uberaba/MG").get_data(as_text=True)
    # Mesmo município, depois a mesma região imediata (Sacramento), depois a mesma UF, depois o resto.
    assert ordem(html, NOMES) == NOMES
    assert "dos mais perto de Uberaba para os mais longe" in html


def test_so_a_minha_regiao(produtores, client):
    html = client.get("/produtores?perto=Uberaba/MG&regiao=1").get_data(as_text=True)
    assert "Uberaba Verde" in html and "Sacramento Queijos" in html
    assert "BH Orgânicos" not in html and "Goiânia Hortas" not in html
    assert "Só a região de Uberaba" in html


def test_cidade_fica_guardada_na_sessao(produtores, client):
    client.get("/produtores?perto=Goiânia/GO")
    html = client.get("/produtores").get_data(as_text=True)
    assert html.index("Goiânia Hortas") < html.index("Uberaba Verde")
    client.get("/produtores?perto=")  # limpar
    html = client.get("/produtores").get_data(as_text=True)
    assert "dos mais perto" not in html


def test_cidade_da_conta_e_o_padrao(app, produtores):
    usuario = criar_usuario(app, "Morador de BH", "bh@exemplo.com")
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET municipio_id = ? WHERE id = ?", (BELO_HORIZONTE, usuario))
    html = cliente_logado(app, usuario).get("/produtores").get_data(as_text=True)
    assert html.index("BH Orgânicos") < html.index("Uberaba Verde") < html.index("Goiânia Hortas")


def test_cidade_invalida_avisa(produtores, client):
    html = client.get("/produtores?perto=Atlântida/MG").get_data(as_text=True)
    assert "Não encontramos “Atlântida/MG”" in html


def test_carregar_municipios_grava_a_regiao_imediata(app, monkeypatch):
    monkeypatch.setattr(
        "app.db.buscar_municipios_ibge",
        lambda uf: [(3170206, "Uberlândia", 310054, "Uberlândia"), (3170107, "Uberaba", 310055, "Uberaba")],
    )
    resultado = app.test_cli_runner().invoke(args=["carregar-municipios", "MG"])
    assert "2 municípios de MG carregados" in resultado.output
    with app.app_context():
        db = get_db()
        linha = db.execute(
            "SELECT r.nome FROM municipio m JOIN regiao_imediata r ON r.id = m.regiao_imediata_id WHERE m.codigo_ibge = 3170206"
        ).fetchone()
        assert linha["nome"] == "Uberlândia"
        assert db.execute("SELECT COUNT(*) FROM municipio WHERE codigo_ibge = 3170107").fetchone()[0] == 1


def test_recarregar_sem_regiao_nao_apaga_a_regiao(app):
    with app.app_context():
        salvar_municipios("MG", [(UBERABA, "Uberaba")])
        regiao = get_db().execute("SELECT regiao_imediata_id FROM municipio WHERE codigo_ibge = ?", (UBERABA,)).fetchone()
        assert regiao[0] == 310055


def test_produtos_mais_perto_primeiro_por_padrao(app, client):
    for nome, municipio in [("Alface de Goiânia", GOIANIA), ("Alface de BH", BELO_HORIZONTE),
                            ("Alface de Sacramento", SACRAMENTO), ("Alface de Uberaba", UBERABA)]:
        usuario = criar_usuario(app, nome, f"p{municipio}@exemplo.com")
        criar_produtor(app, usuario, nome, municipio_id=municipio)
        with app.app_context():
            servicos.criar_produto(get_db(), usuario, {
                "titulo": nome, "categoria_id": 12, "descricao": "", "unidade_id": 12, "quantidade_disponivel": None,
                "municipio_id": municipio, "para_consumidor": True, "preco_consumidor_centavos": 300,
                "para_lojista": False, "preco_lojista_centavos": None, "pedido_minimo_lojista": None,
                "so_verificados": False, "disponibilidade": "ano_todo", "meses_safra": 0,
            }, {}, [])
    nomes = ["Alface de Uberaba", "Alface de Sacramento", "Alface de BH", "Alface de Goiânia"]
    html = client.get("/produtos?perto=Uberaba/MG").get_data(as_text=True)
    assert ordem(html, nomes) == nomes
    so_regiao = client.get("/produtos?regiao=1").get_data(as_text=True)
    assert "Alface de Sacramento" in so_regiao and "Alface de BH" not in so_regiao


def test_encomendas_da_minha_regiao(app, client):
    comprador = criar_usuario(app, "Mercado", "mercado@exemplo.com")
    with app.app_context():
        for titulo, municipio in [("Tomate para Sacramento", SACRAMENTO), ("Tomate para Goiânia", GOIANIA)]:
            servicos.criar_encomenda(get_db(), comprador, {
                "titulo": titulo, "categoria_id": 12, "descricao": "", "quantidade": 100, "unidade_id": 1,
                "municipio_id": municipio, "prazo_limite": date.today() + timedelta(days=10),
                "transporte": "a_combinar", "condicoes_pagamento": "",
            })
    perto = client.get("/encomendas?perto=Uberaba/MG&ordem=perto").get_data(as_text=True)
    assert perto.index("Tomate para Sacramento") < perto.index("Tomate para Goiânia")
    so_regiao = client.get("/encomendas?regiao=1").get_data(as_text=True)
    assert "Tomate para Sacramento" in so_regiao and "Tomate para Goiânia" not in so_regiao
