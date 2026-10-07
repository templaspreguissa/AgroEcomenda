"""Iteração 7: revisão de segurança automatizada (RNF10).

Percorre todas as rotas do sistema, inclusive as que forem criadas depois, e confere:
- o que não é página pública exige login;
- a área de administração recusa quem não é administrador;
- todo formulário (POST) sem token CSRF é recusado.
"""
import pytest
from werkzeug.routing import AnyConverter, IntegerConverter

from app.db import get_db

from .conftest import cliente_logado, criar_usuario

# Páginas que qualquer visitante pode abrir. Uma rota nova fora desta lista precisa exigir login.
PUBLICAS = {
    "static", "main.index", "main.termos", "main.privacidade", "auth.cadastro", "auth.entrar", "auth.esqueci_senha",
    "auth.redefinir_senha", "produtos.lista", "produtos.detalhe", "produtos.foto", "perfis.produtores", "perfis.vitrine",
    "encomendas.lista", "encomendas.detalhe",
}


def _url(app, regra):
    valores = {}
    for nome in regra.arguments:
        conversor = regra._converters[nome]
        if isinstance(conversor, AnyConverter):
            valores[nome] = sorted(conversor.items)[0]
        elif isinstance(conversor, IntegerConverter):
            valores[nome] = 1
        else:
            valores[nome] = "x"
    with app.test_request_context():
        from flask import url_for
        return url_for(regra.endpoint, **valores)


def _regras(app, metodo):
    return [regra for regra in app.url_map.iter_rules() if metodo in regra.methods and regra.endpoint != "static"]


def test_toda_pagina_nao_publica_exige_login(app):
    cliente = app.test_client()
    abertas = []
    for regra in _regras(app, "GET"):
        if regra.endpoint in PUBLICAS:
            continue
        resposta = cliente.get(_url(app, regra))
        if not (resposta.status_code == 302 and "/entrar" in resposta.headers["Location"]):
            abertas.append((regra.endpoint, resposta.status_code))
    assert abertas == []


def test_administracao_recusa_quem_nao_e_admin(app):
    comum = cliente_logado(app, criar_usuario(app, "Comum", "comum@exemplo.com"))
    for regra in app.url_map.iter_rules():
        if regra.endpoint.startswith("admin."):
            metodo = "GET" if "GET" in regra.methods else "POST"
            if metodo == "GET":
                resposta = comum.get(_url(app, regra))
            else:
                app.config["WTF_CSRF_ENABLED"] = False  # para chegar até a checagem de papel
                resposta = comum.post(_url(app, regra), data={"motivo": "teste"})
                app.config["WTF_CSRF_ENABLED"] = True
            assert resposta.status_code == 403, regra.endpoint


def test_todo_post_sem_token_csrf_e_recusado(app):
    usuario = criar_usuario(app, "Comum", "comum@exemplo.com")
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET papel = 'admin' WHERE id = ?", (usuario,))  # passa por qualquer porta
    cliente = cliente_logado(app, usuario)
    aceitos = []
    for regra in _regras(app, "POST"):
        resposta = cliente.post(_url(app, regra), data={"motivo": "teste", "texto": "teste"})
        if resposta.status_code != 400:
            aceitos.append((regra.endpoint, resposta.status_code))
    assert aceitos == []


@pytest.mark.parametrize("url", ["/", "/produtos", "/entrar"])
def test_cabecalhos_de_seguranca_em_todas_as_respostas(client, url):
    resposta = client.get(url)
    assert "default-src 'self'" in resposta.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self'" in resposta.headers["Content-Security-Policy"]
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
