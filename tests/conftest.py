import re

import pytest

from app import create_app
from app.db import init_db

SENHA_VALIDA = "milho verde na safra de março"


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "chave-de-teste",
        "DATABASE": str(tmp_path / "teste.db"),
    })
    with app.app_context():
        init_db()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def token_csrf(client, url):
    """Abre a página e devolve o token CSRF do formulário (os testes usam a proteção real)."""
    html = client.get(url).get_data(as_text=True)
    achado = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html) or re.search(
        r'name="csrf_token" value="([^"]+)"', html
    )
    assert achado, f"token CSRF não encontrado em {url}"
    return achado.group(1)


def cadastrar(client, email="produtor@exemplo.com", senha=SENHA_VALIDA, aceite=True, **extra):
    dados = {
        "csrf_token": token_csrf(client, "/cadastro"),
        "nome": "Sítio Boa Vista",
        "email": email,
        "tipo_pessoa": "PF",
        "senha": senha,
        "confirmar": senha,
    }
    if aceite:
        dados["aceite"] = "y"
    dados.update(extra)
    return client.post("/cadastro", data=dados)


def entrar(client, email="produtor@exemplo.com", senha=SENHA_VALIDA, url="/entrar"):
    return client.post(url, data={
        "csrf_token": token_csrf(client, "/entrar"),
        "email": email,
        "senha": senha,
    })


def sair(client):
    return client.post("/sair", data={"csrf_token": token_csrf(client, "/painel")})
