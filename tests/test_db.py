import sqlite3

import pytest

from app.db import get_db, salvar_municipios


def test_chaves_estrangeiras_ativas(app):
    with app.app_context():
        assert get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_carga_inicial(app):
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM categoria WHERE categoria_pai_id IS NULL").fetchone()[0] == 5
        siglas = {linha[0] for linha in db.execute("SELECT sigla FROM unidade_medida")}
        assert {"sc60", "@", "cab", "ha"} <= siglas


def test_chave_estrangeira_invalida_e_rejeitada(app):
    with app.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO usuario (nome, email, senha_hash, tipo_pessoa, municipio_id, termos_versao, termos_aceitos_em) "
                "VALUES ('A', 'a@x.com', 'h', 'PF', 999999, 'v', '2026-01-01 00:00:00')"
            )


def test_tabela_strict_rejeita_tipo_errado(app):
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            get_db().execute("INSERT INTO unidade_medida (id, sigla, nome) VALUES ('abc', 'x', 'y')")


def test_comando_carregar_municipios(app, monkeypatch):
    monkeypatch.setattr(
        "app.db.buscar_municipios_ibge", lambda uf: [(3106200, "Belo Horizonte"), (3170206, "Uberlândia")]
    )
    resultado = app.test_cli_runner().invoke(args=["carregar-municipios", "mg"])
    assert "2 municípios de MG carregados" in resultado.output
    with app.app_context():
        nomes = [linha[0] for linha in get_db().execute("SELECT nome FROM municipio WHERE uf = 'MG' ORDER BY nome")]
    # Belo Horizonte já existia na base de teste e não foi duplicado.
    assert nomes == ["Belo Horizonte", "Sacramento", "Uberaba", "Uberlândia"]


def test_comando_carregar_municipios_rejeita_uf_invalida(app):
    resultado = app.test_cli_runner().invoke(args=["carregar-municipios", "XX"])
    assert resultado.exit_code != 0
    assert "UF inválida" in resultado.output


def test_salvar_municipios_nao_duplica(app):
    with app.app_context():
        antes = get_db().execute("SELECT COUNT(*) FROM municipio").fetchone()[0]
        salvar_municipios("MG", [(3106200, "Belo Horizonte")])
        salvar_municipios("MG", [(3106200, "Belo Horizonte")])
        assert get_db().execute("SELECT COUNT(*) FROM municipio").fetchone()[0] == antes


def test_comando_carregar_demo(app):
    from app.cnpj import valido
    from app.demo import DEMO_SENHA

    executor = app.test_cli_runner()
    resultado = executor.invoke(args=["carregar-demo", "--senha-fixa"])
    assert "Dados de demonstração carregados" in resultado.output
    assert DEMO_SENHA not in resultado.output
    with app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM perfil_produtor").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM perfil_comercio WHERE verificado_em IS NOT NULL").fetchone()[0] == 1
        assert all(valido(linha[0]) for linha in db.execute("SELECT cnpj FROM perfil_comercio"))
        contrato = db.execute("SELECT status, parceria_produtor, parceria_comercio FROM contrato").fetchone()
        assert tuple(contrato) == ("ativo", 1, 1)
        assert db.execute("SELECT COUNT(*) FROM contrato_aceite").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM usuario WHERE papel = 'admin'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM denuncia WHERE status = 'aberta'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM usuario WHERE telefone IS NOT NULL").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM perfil_produtor WHERE telefone_publico IS NOT NULL").fetchone()[0] == 0

    cliente = app.test_client()
    from .conftest import entrar
    assert entrar(cliente, "ana.demo@example.com", DEMO_SENHA).headers["Location"] == "/painel"

    de_novo = executor.invoke(args=["carregar-demo"])
    assert de_novo.exit_code != 0 and "já foram carregados" in de_novo.output


def test_carregar_demo_sem_senha_fixa_sorteia_senhas(app):
    """No site publicado a senha de app/demo.py é pública: sem --senha-fixa, ninguém entra com ela."""
    import re

    from app.demo import DEMO_SENHA

    from .conftest import entrar

    resultado = app.test_cli_runner().invoke(args=["carregar-demo"])
    assert resultado.exit_code == 0
    senha = re.search(r"marina: (\S+)", resultado.output).group(1)
    senha_admin = re.search(r"admin\.demo@example\.com: (\S+)", resultado.output).group(1)
    assert len(senha) >= 15 and len(senha_admin) >= 15 and senha != senha_admin

    assert entrar(app.test_client(), "ana.demo@example.com", DEMO_SENHA).status_code == 200  # recusado
    assert entrar(app.test_client(), "admin.demo@example.com", senha).status_code == 200  # a da história não serve
    assert entrar(app.test_client(), "ana.demo@example.com", senha).headers["Location"] == "/painel"
    assert entrar(app.test_client(), "admin.demo@example.com", senha_admin).headers["Location"] == "/painel"


def test_init_db_apaga_tabelas_de_versoes_antigas(app):
    """Quem vem da Iteração 3 tem a tabela 'anuncio' apontando para 'usuario'. O init-db precisa funcionar."""
    from app.db import init_db
    with app.app_context():
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO usuario (nome, email, senha_hash, tipo_pessoa, termos_versao, termos_aceitos_em) "
                "VALUES ('A', 'a@x.com', 'h', 'PF', 'v', '2026-01-01 00:00:00')"
            )
            db.execute("CREATE TABLE anuncio (id INTEGER PRIMARY KEY, vendedor_id INTEGER REFERENCES usuario(id))")
            db.execute("INSERT INTO anuncio (vendedor_id) VALUES (1)")
        init_db()
        nomes = {linha[0] for linha in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "anuncio" not in nomes and "produto" in nomes
        assert db.execute("SELECT COUNT(*) FROM usuario").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
