def test_home_mostra_escolhas_e_categorias(client):
    html = client.get("/").get_data(as_text=True)
    assert "Sou produtor" in html and "Tenho um comércio" in html and "Quero comprar do produtor" in html
    assert "Produtos de origem animal" in html
    assert "Queijos e laticínios" in html
    assert "Máquinas" not in html  # fora do escopo desde outubro de 2026


def test_cabecalhos_de_seguranca(client):
    resposta = client.get("/")
    assert "default-src 'self'" in resposta.headers["Content-Security-Policy"]
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "SAMEORIGIN"


def test_sem_script_inline(client):
    # A CSP bloqueia <script> inline, então nenhuma página pode depender disso.
    for url in ("/", "/entrar", "/cadastro", "/termos", "/privacidade", "/produtores"):
        html = client.get(url).get_data(as_text=True)
        assert "<script>" not in html


def test_paginas_institucionais(client):
    assert "Termos de Uso" in client.get("/termos").get_data(as_text=True)
    assert "Política de Privacidade" in client.get("/privacidade").get_data(as_text=True)


def test_pagina_inexistente(client):
    resposta = client.get("/nao-existe")
    assert resposta.status_code == 404
    assert "Página não encontrada" in resposta.get_data(as_text=True)


def test_escape_automatico_de_html(client, app):
    from .conftest import cadastrar
    cadastrar(client, nome="<script>alert(1)</script>")
    html = client.get("/painel").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
