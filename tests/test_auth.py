from flask import Blueprint

from app.auth.routes import admin_obrigatorio, destino_seguro
from app.db import get_db

from .conftest import SENHA_VALIDA, cadastrar, entrar, sair, token_csrf


def test_cadastro_cria_usuario_com_hash_e_aceite(client, app):
    resposta = cadastrar(client)
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/painel")
    with app.app_context():
        usuario = get_db().execute("SELECT * FROM usuario WHERE email = 'produtor@exemplo.com'").fetchone()
    assert usuario["senha_hash"].startswith("pbkdf2:sha256:600000$")
    assert SENHA_VALIDA not in usuario["senha_hash"]
    assert usuario["termos_versao"] == app.config["TERMOS_VERSAO"]
    assert usuario["papel"] == "usuario"


def test_email_e_normalizado(client, app):
    cadastrar(client, email="  Produtor@Exemplo.COM ")
    with app.app_context():
        assert get_db().execute("SELECT email FROM usuario").fetchone()[0] == "produtor@exemplo.com"


def test_senha_curta_e_rejeitada(client, app):
    resposta = cadastrar(client, senha="curta123")
    assert resposta.status_code == 200
    assert "Use pelo menos 15 caracteres" in resposta.get_data(as_text=True)
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM usuario").fetchone()[0] == 0


def test_senha_comum_e_rejeitada(client):
    resposta = cadastrar(client, senha="123456789012345")
    assert "Essa senha é muito comum" in resposta.get_data(as_text=True)


def test_senha_sem_regras_de_composicao(client):
    # NIST SP 800-63B-4: não exigir maiúscula, número ou símbolo.
    assert cadastrar(client, senha="so letras minusculas aqui").status_code == 302


def test_cadastro_exige_aceite_dos_termos(client):
    resposta = cadastrar(client, aceite=False)
    assert "aceite os Termos de Uso" in resposta.get_data(as_text=True)


def test_email_duplicado(client):
    cadastrar(client)
    sair(client)
    resposta = cadastrar(client)
    assert "Já existe uma conta com este e-mail" in resposta.get_data(as_text=True)


def test_login_e_logout(client):
    cadastrar(client)
    sair(client)
    assert client.get("/painel").status_code == 302
    resposta = entrar(client)
    assert resposta.headers["Location"].endswith("/painel")
    assert "Meus dados" in client.get("/painel").get_data(as_text=True)
    sair(client)
    assert client.get("/painel").status_code == 302


def test_mensagem_de_erro_generica(client):
    # Senha errada e e-mail inexistente recebem a mesma mensagem (não revela quem tem conta).
    cadastrar(client)
    sair(client)
    senha_errada = entrar(client, senha="senha errada mas bem comprida").get_data(as_text=True)
    email_inexistente = entrar(client, email="naoexiste@exemplo.com").get_data(as_text=True)
    assert "E-mail ou senha incorretos." in senha_errada
    assert "E-mail ou senha incorretos." in email_inexistente


def test_bloqueio_apos_muitas_falhas(client, app):
    cadastrar(client)
    sair(client)
    for _ in range(app.config["LOGIN_MAX_FALHAS"]):
        entrar(client, senha="senha errada mas bem comprida")
    resposta = entrar(client)  # senha certa, mas o e-mail está temporariamente bloqueado
    assert resposta.status_code == 200
    assert "Muitas tentativas" in resposta.get_data(as_text=True)
    assert client.get("/painel").status_code == 302


def test_login_certo_zera_as_falhas(client, app):
    cadastrar(client)
    sair(client)
    for _ in range(app.config["LOGIN_MAX_FALHAS"] - 1):
        entrar(client, senha="senha errada mas bem comprida")
    assert entrar(client).status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM bloqueio_login").fetchone()[0] == 0


def test_post_sem_token_csrf_e_rejeitado(client):
    resposta = client.post("/entrar", data={"email": "a@b.com", "senha": "x" * 20})
    assert resposta.status_code == 400
    assert "Formulário expirado" in resposta.get_data(as_text=True)


def test_sair_nao_aceita_get(client):
    assert client.get("/sair").status_code == 405


def test_painel_exige_login(client):
    resposta = client.get("/painel")
    assert resposta.status_code == 302
    assert "/entrar?next=/painel" in resposta.headers["Location"]


def test_redirecionamento_apos_login_respeita_next_interno(client):
    cadastrar(client)
    sair(client)
    resposta = entrar(client, url="/entrar?next=/painel")
    assert resposta.headers["Location"].endswith("/painel")


def test_redirecionamento_externo_e_bloqueado(client):
    cadastrar(client)
    sair(client)
    resposta = entrar(client, url="/entrar?next=//site-malicioso.com")
    assert "site-malicioso" not in resposta.headers["Location"]


def test_destino_seguro():
    assert destino_seguro("/painel") == "/painel"
    for alvo in ("//evil.com", "https://evil.com", "/\\evil.com", "painel", "", None):
        assert destino_seguro(alvo) is None


def test_admin_obrigatorio(app, client):
    bp = Blueprint("teste_admin", __name__)

    @bp.route("/area-admin")
    @admin_obrigatorio
    def area_admin():
        return "ok"

    app.register_blueprint(bp)
    assert client.get("/area-admin").status_code == 302  # sem login
    cadastrar(client)
    assert client.get("/area-admin").status_code == 403  # usuário comum
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET papel = 'admin'")
    assert client.get("/area-admin").get_data(as_text=True) == "ok"


def test_usuario_bloqueado_perde_a_sessao(app, client):
    cadastrar(client)
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET status = 'bloqueado'")
    assert client.get("/painel").status_code == 302


def test_formulario_de_cadastro_tem_token(client):
    assert token_csrf(client, "/cadastro")
