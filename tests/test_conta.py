"""Iteração 7: direitos do titular (RF21; LGPD, art. 18) e recuperação de acesso (RF02)."""
import json
import os
import re
from datetime import date, timedelta
from io import BytesIO

import pytest

from app import servicos
from app.db import get_db
from app.servicos import contratos

from .conftest import SENHA_VALIDA, cadastrar, cliente_logado, criar_comercio, entrar, token_csrf
from .test_produtos import jpeg

NOVA_SENHA = "colheita de cafe no fim de maio"


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


@pytest.fixture
def ana(app, client):
    """Conta criada pelo formulário (com senha de verdade), com vitrine, produto com foto e contrato ativo."""
    cadastrar(client, email="ana@exemplo.com", nome="Ana Ribeiro")
    ana_id = consultar(app, "SELECT id FROM usuario WHERE email = 'ana@exemplo.com'")[0]
    client.post("/minha-vitrine", data={
        "csrf_token": token_csrf(client, "/minha-vitrine"), "nome_vitrine": "Sítio Boa Vista", "municipio": "Uberaba/MG",
        "vende_retirada": "y", "organico": "nao", "telefone": "(34) 99876-5432",
    })
    client.post("/produtos/novo", data={
        "csrf_token": token_csrf(client, "/produtos/novo"), "titulo": "Alface crespa", "categoria_id": "12",
        "unidade_id": "12", "municipio": "Uberaba/MG", "para_consumidor": "y", "preco_consumidor": "3,50",
        "para_lojista": "y", "preco_lojista": "2,40", "disponibilidade": "ano_todo",
        "fotos": [(BytesIO(jpeg(300, 200)), "alface.jpg")],
    }, content_type="multipart/form-data")
    return {"id": ana_id, "cliente": client}


def _com_loja_e_contrato(app, ana_id):
    from .conftest import criar_usuario
    loja = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    criar_comercio(app, loja, "Mercado Bom Preço")
    with app.app_context():
        db = get_db()
        produto = db.execute("SELECT id FROM produto").fetchone()[0]
        contrato_id = contratos.criar_contrato(db, ana_id, ana_id, loja, {
            "inicio": date.today().isoformat(), "termino": (date.today() + timedelta(days=90)).isoformat(),
            "frequencia": "semanal", "dia_entrega": "", "transporte": "vendedor_entrega", "municipio_entrega_id": 3170107,
            "local_entrega": "", "condicoes_pagamento": "Pix", "padrao_qualidade": "", "reajuste": "",
            "aviso_previo_dias": 15, "observacoes": "",
        }, [{"produto_id": produto, "descricao": "Alface", "quantidade": 50, "unidade_id": 12, "preco_centavos": 240}])
        contratos.enviar_contrato(db, contratos.buscar_contrato(db, contrato_id, ana_id), ana_id)
        contrato = contratos.buscar_contrato(db, contrato_id, loja)
        contratos.aceitar_contrato(db, contrato, loja, contratos.versao_atual(db, contrato)["hash"])
        remetente = {"id": loja, "nome": "Rita Souza", "tem_produtor": False}
        conversa = servicos.conversas.iniciar_conversa(db, "produto", produto, remetente, "Oi, Ana!")
        servicos.conversas.responder(db, servicos.conversas.buscar_conversa(db, conversa, ana_id), ana_id, "Oi, Rita!")
    return loja, contrato_id, conversa


# ---------- exportar (LGPD, art. 18, II e V) ----------

def test_baixar_meus_dados(app, ana):
    resposta = ana["cliente"].get("/minha-conta/meus-dados.json")
    assert resposta.status_code == 200 and resposta.mimetype == "application/json"
    assert "attachment" in resposta.headers["Content-Disposition"]
    dados = json.loads(resposta.get_data(as_text=True))
    assert dados["conta"]["email"] == "ana@exemplo.com"
    assert dados["vitrine"][0]["telefone_publico"] == "34998765432"
    assert dados["produtos"][0]["titulo"] == "Alface crespa"
    assert "senha_hash" not in json.dumps(dados)


def test_baixar_dados_exige_login(client):
    assert client.get("/minha-conta/meus-dados.json").status_code == 302


# ---------- excluir (LGPD, art. 18, VI) ----------

def excluir(cliente, senha=SENHA_VALIDA, entendi="y"):
    dados = {"csrf_token": token_csrf(cliente, "/minha-conta/excluir"), "senha": senha}
    if entendi:
        dados["entendi"] = entendi
    return cliente.post("/minha-conta/excluir", data=dados)


def test_exclusao_pede_senha_e_confirmacao(app, ana):
    assert "Senha incorreta." in excluir(ana["cliente"], senha="senha errada de proposito").get_data(as_text=True)
    assert "Marque a confirmação" in excluir(ana["cliente"], entendi=None).get_data(as_text=True)
    assert consultar(app, "SELECT status FROM usuario WHERE id = ?", ana["id"])[0] == "ativo"
    assert consultar(app, "SELECT falhas FROM bloqueio_login WHERE email = 'ana@exemplo.com'")[0] == 1


def test_exclusao_anonimiza_e_preserva_o_historico_da_outra_parte(app, ana, client):
    loja, contrato_id, conversa = _com_loja_e_contrato(app, ana["id"])
    fotos = [linha[0] for linha in get_db_all(app, "SELECT arquivo FROM foto_produto")]
    assert fotos

    resposta = excluir(ana["cliente"])
    assert resposta.status_code == 302 and resposta.headers["Location"] == "/"
    usuario = consultar(app, "SELECT nome, email, status, senha_hash, telefone FROM usuario WHERE id = ?", ana["id"])
    assert tuple(usuario) == ("Usuário removido", f"removido-{ana['id']}@invalido.example", "excluido", "!", None)
    vitrine = consultar(app, "SELECT nome_vitrine, telefone_publico, status FROM perfil_produtor")
    assert tuple(vitrine) == ("Vitrine removida", None, "oculto")
    assert consultar(app, "SELECT status FROM produto")[0] == "encerrado"
    assert consultar(app, "SELECT COUNT(*) FROM foto_produto")[0] == 0
    assert not any(os.path.exists(os.path.join(app.config["PASTA_FOTOS"], nome)) for nome in fotos)
    assert ana["cliente"].get("/painel").status_code == 302  # sessão encerrada

    # Contrato ativo: rescindido, com aviso para a loja. O texto aceito continua guardado.
    contrato = consultar(app, "SELECT status, motivo_encerramento FROM contrato WHERE id = ?", contrato_id)
    assert tuple(contrato) == ("rescindido", "Conta excluída")
    assert consultar(app, "SELECT COUNT(*) FROM contrato_versao")[0] == 1
    assert "excluiu a conta" in consultar(app, "SELECT texto FROM notificacao WHERE usuario_id = ? ORDER BY id DESC",
                                          loja)[0]
    # A conversa continua para a loja, com o autor anonimizado.
    tela = cliente_logado(app, loja).get(f"/mensagens/{conversa}").get_data(as_text=True)
    assert "Oi, Rita!" in tela and "Usuário · Vitrine removida" in tela
    assert "Ribeiro" not in tela and "Sítio Boa Vista" not in tela

    # O e-mail fica livre para uma conta nova, e a senha antiga não entra mais.
    assert entrar(client, "ana@exemplo.com").headers.get("Location") != "/painel"
    assert cadastrar(client, email="ana@exemplo.com").status_code == 302


def get_db_all(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


def test_admin_nao_se_exclui_por_aqui(app, ana):
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET papel = 'admin' WHERE id = ?", (ana["id"],))
    resposta = excluir(ana["cliente"])
    assert consultar(app, "SELECT status FROM usuario WHERE id = ?", ana["id"])[0] == "ativo"
    assert resposta.status_code == 200


# ---------- recuperar a senha (RF02) ----------

@pytest.fixture
def links(monkeypatch):
    enviados = []
    monkeypatch.setattr("app.auth.routes.enviar_link_de_redefinicao", lambda email, link: enviados.append((email, link)))
    return enviados


def pedir_link(client, email):
    return client.post("/esqueci-a-senha", data={"csrf_token": token_csrf(client, "/esqueci-a-senha"), "email": email})


def test_esqueci_a_senha_responde_igual_para_email_desconhecido(app, ana, links):
    ana["cliente"].post("/sair", data={"csrf_token": token_csrf(ana["cliente"], "/painel")})
    cliente = app.test_client()
    desconhecido = pedir_link(cliente, "ninguem@exemplo.com")
    conhecido = pedir_link(cliente, "ana@exemplo.com")
    assert desconhecido.status_code == conhecido.status_code == 302
    mensagem = "Se houver uma conta com este e-mail"
    assert mensagem in cliente.get("/entrar").get_data(as_text=True)
    assert [email for email, _ in links] == ["ana@exemplo.com"]
    assert consultar(app, "SELECT COUNT(*) FROM redefinicao_senha")[0] == 1
    codigo = re.search(r"/redefinir-senha/(.+)$", links[0][1]).group(1)
    assert consultar(app, "SELECT codigo_hash FROM redefinicao_senha")[0] != codigo  # só o hash fica guardado


def test_redefinir_senha_uma_vez_e_entrar_com_a_nova(app, ana, links):
    cliente = app.test_client()
    pedir_link(cliente, "ana@exemplo.com")
    url = re.search(r"(/redefinir-senha/.+)$", links[0][1]).group(1)
    pagina = cliente.get(url)
    assert pagina.status_code == 200 and pagina.headers["Cache-Control"] == "no-store"

    fraca = cliente.post(url, data={"csrf_token": token_csrf(cliente, url), "senha": "curta", "confirmar": "curta"})
    assert "Use pelo menos 15 caracteres" in fraca.get_data(as_text=True)
    resposta = cliente.post(url, data={"csrf_token": token_csrf(cliente, url), "senha": NOVA_SENHA, "confirmar": NOVA_SENHA})
    assert resposta.headers["Location"] == "/entrar"

    assert cliente.get(url).status_code == 404  # o link não vale de novo
    assert entrar(app.test_client(), "ana@exemplo.com", SENHA_VALIDA).headers.get("Location") != "/painel"
    assert entrar(app.test_client(), "ana@exemplo.com", NOVA_SENHA).headers["Location"] == "/painel"


def test_link_vencido_nao_vale(app, ana, links):
    cliente = app.test_client()
    pedir_link(cliente, "ana@exemplo.com")
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE redefinicao_senha SET expira_em = '2000-01-01 00:00:00'")
    url = re.search(r"(/redefinir-senha/.+)$", links[0][1]).group(1)
    assert cliente.get(url).status_code == 404
    assert cliente.get("/redefinir-senha/codigo-inventado").status_code == 404


def test_limite_de_pedidos_de_link(app, ana, links):
    cliente = app.test_client()
    for _ in range(5):
        pedir_link(cliente, "ana@exemplo.com")
    assert len(links) == 3  # no máximo 3 por hora
