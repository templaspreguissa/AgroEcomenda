"""Iteração 1: encomendas, propostas, aceite, recusa, estados e expiração."""
from datetime import date, timedelta

import pytest

from app.db import get_db

from .conftest import cliente_logado, criar_usuario, token_csrf

AMANHA = date.today() + timedelta(days=1)
DAQUI_10 = date.today() + timedelta(days=10)
DAQUI_30 = date.today() + timedelta(days=30)
CATEGORIA_GRAOS = 10
CATEGORIA_CAFE = 11
CATEGORIA_BOVINOS = 20
PRODUCAO_AGRICOLA = 1
UNIDADE_T = 2


@pytest.fixture
def pessoas(app):
    """Comprador e dois vendedores, cada um com seu próprio navegador logado."""
    comprador = criar_usuario(app, "Maria Aparecida Souza", "maria@exemplo.com")
    vendedor_a = criar_usuario(app, "João Batista Lima", "joao@exemplo.com")
    vendedor_b = criar_usuario(app, "Ana Paula Rocha", "ana@exemplo.com")
    return {
        "comprador": (comprador, cliente_logado(app, comprador)),
        "a": (vendedor_a, cliente_logado(app, vendedor_a)),
        "b": (vendedor_b, cliente_logado(app, vendedor_b)),
    }


def publicar(cliente, **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/encomendas/nova"),
        "titulo": "Milho em grão",
        "categoria_id": CATEGORIA_GRAOS,
        "descricao": "Umidade até 14%",
        "quantidade": "30",
        "unidade_id": UNIDADE_T,
        "municipio": "Uberaba/MG",
        "prazo_limite": DAQUI_30.isoformat(),
        "transporte": "vendedor_entrega",
        "condicoes_pagamento": "À vista na entrega",
    }
    dados.update(mudancas)
    return cliente.post("/encomendas/nova", data=dados)


def id_criado(resposta):
    assert resposta.status_code == 302, resposta.get_data(as_text=True)[:500]
    return int(resposta.headers["Location"].rstrip("/").split("/")[-1])


def propor(cliente, encomenda_id, **mudancas):
    url = f"/encomendas/{encomenda_id}/proposta"
    dados = {
        "csrf_token": token_csrf(cliente, url),
        "preco": "1.450,00",
        "quantidade": "30",
        "prazo_entrega": DAQUI_10.isoformat(),
        "transporte": "vendedor_entrega",
        "validade": "",
        "observacao": "Milho seco, padrão exportação",
    }
    dados.update(mudancas)
    return cliente.post(url, data=dados)


def postar(cliente, url, pagina):
    return cliente.post(url, data={"csrf_token": token_csrf(cliente, pagina)})


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


def ids_das_propostas(app, encomenda_id):
    with app.app_context():
        linhas = get_db().execute(
            "SELECT id, vendedor_id FROM proposta WHERE encomenda_id = ? ORDER BY id", (encomenda_id,)
        ).fetchall()
    return {linha["vendedor_id"]: linha["id"] for linha in linhas}


# ---------- publicar ----------

def test_publicar_encomenda(app, pessoas):
    comprador_id, comprador = pessoas["comprador"]
    encomenda_id = id_criado(publicar(comprador))
    encomenda = consultar(app, "SELECT * FROM encomenda WHERE id = ?", encomenda_id)
    assert encomenda["titulo_busca"] == "milho em grao"
    assert encomenda["quantidade"] == 30
    assert encomenda["municipio_entrega_id"] == 3170107
    assert encomenda["status"] == "aberta"
    # O município da primeira encomenda vai para o perfil.
    assert consultar(app, "SELECT municipio_id FROM usuario WHERE id = ?", comprador_id)[0] == 3170107
    pagina = comprador.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "30 toneladas" in pagina and "Uberaba/MG" in pagina


def test_publicar_exige_login(client):
    resposta = client.get("/encomendas/nova")
    assert resposta.status_code == 302
    assert "/entrar?next=/encomendas/nova" in resposta.headers["Location"]


@pytest.mark.parametrize("campo, valor, mensagem", [
    ("quantidade", "0", "maior que zero"),
    ("quantidade", "trinta", "Use só números"),
    ("municipio", "Cidade Inventada/MG", "Escolha um município da lista"),
    ("prazo_limite", (date.today() - timedelta(days=1)).isoformat(), "já passou"),
    ("prazo_limite", "31/02/2026", "Informe uma data válida"),
    ("titulo", "", "Diga o que você precisa"),
    ("categoria_id", "", "Escolha uma categoria"),
    ("unidade_id", "", "Escolha a unidade"),
    ("categoria_id", "9999", "Escolha inválida"),
])
def test_validacoes_da_encomenda(app, pessoas, campo, valor, mensagem):
    _, comprador = pessoas["comprador"]
    resposta = publicar(comprador, **{campo: valor})
    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM encomenda")[0] == 0


# ---------- lista e filtros ----------

def test_lista_busca_e_filtros(pessoas):
    _, comprador = pessoas["comprador"]
    publicar(comprador)
    publicar(comprador, titulo="Café arábica", categoria_id=CATEGORIA_CAFE, municipio="Goiânia/GO", unidade_id=3)
    publicar(comprador, titulo="Bezerros nelore", categoria_id=CATEGORIA_BOVINOS, unidade_id=6, quantidade="20")
    _, visitante = pessoas["a"]

    def titulos(consulta):
        return visitante.get("/encomendas" + consulta).get_data(as_text=True)

    todas = titulos("")
    assert "Mostrando 1–3 de 3 encomendas" in todas
    assert "Café arábica" in titulos("?q=cafe") and "Milho em grão" not in titulos("?q=cafe")
    assert "Café arábica" in titulos("?uf=GO") and "Bezerros" not in titulos("?uf=GO")
    agricola = titulos(f"?categoria={PRODUCAO_AGRICOLA}")  # categoria principal inclui as subcategorias
    assert "Milho em grão" in agricola and "Café arábica" in agricola and "Bezerros" not in agricola
    assert "Nenhuma encomenda com esses filtros" in titulos("?q=soja")


def test_busca_trata_curingas_como_texto(pessoas):
    _, comprador = pessoas["comprador"]
    publicar(comprador)
    assert "Nenhuma encomenda" in comprador.get("/encomendas?q=%25").get_data(as_text=True)


def test_lista_mostra_so_primeiro_nome_do_comprador(pessoas):
    _, comprador = pessoas["comprador"]
    publicar(comprador)
    _, visitante = pessoas["a"]
    pagina = visitante.get("/encomendas").get_data(as_text=True)
    assert "por Maria" in pagina and "Souza" not in pagina


# ---------- propostas ----------

def test_fluxo_de_proposta_e_visibilidade(app, pessoas, client):
    comprador_id, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    _, cliente_b = pessoas["b"]
    encomenda_id = id_criado(publicar(comprador))

    assert propor(cliente_a, encomenda_id).status_code == 302
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "em_negociacao"
    notificacao = consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ?", comprador_id)
    assert notificacao["tipo"] == "nova_proposta"

    pagina_comprador = comprador.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "Propostas recebidas (1)" in pagina_comprador
    assert "R$ 1.450,00" in pagina_comprador and "R$ 43.500,00" in pagina_comprador  # total = 30 x 1.450
    assert "João" in pagina_comprador and "Batista Lima" not in pagina_comprador  # só o primeiro nome antes do aceite

    # Outro vendedor e o visitante não veem a proposta.
    assert "R$ 1.450,00" not in cliente_b.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "R$ 1.450,00" not in client.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "Sua proposta" in cliente_a.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)


def test_nao_pode_propor_para_a_propria_encomenda(app, pessoas):
    _, comprador = pessoas["comprador"]
    encomenda_id = id_criado(publicar(comprador))
    resposta = comprador.get(f"/encomendas/{encomenda_id}/proposta")
    assert resposta.status_code == 302
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


@pytest.mark.parametrize("campo, valor, mensagem", [
    ("quantidade", "31", "não pode ser maior que a quantidade pedida"),
    ("prazo_entrega", (DAQUI_30 + timedelta(days=1)).isoformat(), "até o prazo limite da encomenda"),
    ("preco", "0", "maior que zero"),
    ("validade", (date.today() - timedelta(days=1)).isoformat(), "validade"),
])
def test_regras_da_proposta(app, pessoas, campo, valor, mensagem):
    _, comprador = pessoas["comprador"]
    _, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    resposta = propor(cliente_a, encomenda_id, **{campo: valor})
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


def test_segunda_proposta_edita_a_pendente(app, pessoas):
    _, comprador = pessoas["comprador"]
    _, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    assert "Editar proposta" in cliente_a.get(f"/encomendas/{encomenda_id}/proposta").get_data(as_text=True)
    propor(cliente_a, encomenda_id, preco="1.400,00")
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 1
    assert consultar(app, "SELECT preco_unitario_centavos FROM proposta")[0] == 140000


def test_aceitar_encerra_negociacao(app, pessoas):
    comprador_id, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    vendedor_b, cliente_b = pessoas["b"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    propor(cliente_b, encomenda_id, preco="1.500,00")
    propostas = ids_das_propostas(app, encomenda_id)

    resposta = postar(comprador, f"/propostas/{propostas[vendedor_a]}/aceitar", f"/encomendas/{encomenda_id}")
    assert resposta.status_code == 302

    status = dict(consultar(app, "SELECT "
                            "(SELECT status FROM encomenda WHERE id = ?) AS encomenda, "
                            "(SELECT status FROM proposta WHERE id = ?) AS a, "
                            "(SELECT status FROM proposta WHERE id = ?) AS b",
                            encomenda_id, propostas[vendedor_a], propostas[vendedor_b]))
    assert status == {"encomenda": "concluida", "a": "aceita", "b": "nao_selecionada"}
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ? ORDER BY id DESC", vendedor_a)[0] == "proposta_aceita"
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ? ORDER BY id DESC", vendedor_b)[0] == "proposta_recusada"

    # Contato liberado só entre as partes do negócio fechado.
    assert "joao@exemplo.com" in comprador.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "maria@exemplo.com" in cliente_a.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    pagina_b = cliente_b.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)
    assert "maria@exemplo.com" not in pagina_b and "Souza" not in pagina_b

    # Aceitar de novo não muda nada.
    postar(comprador, f"/propostas/{propostas[vendedor_b]}/aceitar", f"/encomendas/{encomenda_id}")
    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", propostas[vendedor_b])[0] == "nao_selecionada"


def test_recusar_e_retirar_recalculam_o_status(app, pessoas):
    _, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    vendedor_b, cliente_b = pessoas["b"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    propor(cliente_b, encomenda_id)
    propostas = ids_das_propostas(app, encomenda_id)

    postar(comprador, f"/propostas/{propostas[vendedor_a]}/recusar", f"/encomendas/{encomenda_id}")
    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", propostas[vendedor_a])[0] == "recusada"
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "em_negociacao"

    postar(cliente_b, f"/propostas/{propostas[vendedor_b]}/retirar", f"/encomendas/{encomenda_id}")
    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", propostas[vendedor_b])[0] == "retirada"
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "aberta"


def test_cancelar_encomenda(app, pessoas):
    _, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    postar(comprador, f"/encomendas/{encomenda_id}/cancelar", f"/encomendas/{encomenda_id}")
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "cancelada"
    assert consultar(app, "SELECT status FROM proposta")[0] == "nao_selecionada"
    assert "Milho em grão" not in cliente_a.get("/encomendas").get_data(as_text=True)


def test_editar_so_sem_propostas(app, pessoas):
    _, comprador = pessoas["comprador"]
    _, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    url = f"/encomendas/{encomenda_id}/editar"
    dados = {
        "csrf_token": token_csrf(comprador, url), "titulo": "Milho em grão seco", "categoria_id": CATEGORIA_GRAOS,
        "descricao": "", "quantidade": "25", "unidade_id": UNIDADE_T, "municipio": "Uberaba/MG",
        "prazo_limite": DAQUI_30.isoformat(), "transporte": "a_combinar", "condicoes_pagamento": "",
    }
    assert comprador.post(url, data=dados).status_code == 302
    assert consultar(app, "SELECT quantidade FROM encomenda")[0] == 25

    propor(cliente_a, encomenda_id, quantidade="25")
    resposta = comprador.get(url)
    assert resposta.status_code == 302  # com proposta, a edição é bloqueada


# ---------- controle de acesso (IDOR) ----------

def test_ninguem_mexe_no_que_nao_e_seu(app, pessoas):
    _, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    _, cliente_b = pessoas["b"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    proposta_id = ids_das_propostas(app, encomenda_id)[vendedor_a]
    pagina = f"/encomendas/{encomenda_id}"

    # Vendedor B tenta aceitar, recusar ou retirar a proposta de A.
    assert postar(cliente_b, f"/propostas/{proposta_id}/aceitar", pagina).status_code == 404
    assert postar(cliente_b, f"/propostas/{proposta_id}/recusar", pagina).status_code == 404
    assert postar(cliente_b, f"/propostas/{proposta_id}/retirar", pagina).status_code == 404
    # O próprio vendedor não pode aceitar a sua proposta.
    assert postar(cliente_a, f"/propostas/{proposta_id}/aceitar", pagina).status_code == 404
    # O comprador não pode retirar a proposta do vendedor.
    assert postar(comprador, f"/propostas/{proposta_id}/retirar", pagina).status_code == 404
    # Outro usuário não cancela nem edita a encomenda.
    assert postar(cliente_b, f"/encomendas/{encomenda_id}/cancelar", pagina).status_code == 403
    assert cliente_b.get(f"/encomendas/{encomenda_id}/editar").status_code == 403

    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", proposta_id)[0] == "pendente"
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "em_negociacao"


def test_acoes_exigem_post_e_csrf(pessoas):
    _, comprador = pessoas["comprador"]
    encomenda_id = id_criado(publicar(comprador))
    assert comprador.get(f"/encomendas/{encomenda_id}/cancelar").status_code == 405
    assert comprador.post(f"/encomendas/{encomenda_id}/cancelar").status_code == 400  # sem token CSRF


def test_proposta_inexistente(pessoas):
    _, comprador = pessoas["comprador"]
    assert postar(comprador, "/propostas/999/aceitar", "/encomendas").status_code == 404
    assert comprador.get("/encomendas/999").status_code == 404


# ---------- expiração (RF17) ----------

def test_encomenda_vencida_expira_sozinha(app, pessoas):
    comprador_id, comprador = pessoas["comprador"]
    vendedor_a, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    with app.app_context():
        db = get_db()
        with db:
            ontem = (date.today() - timedelta(days=1)).isoformat()
            db.execute("UPDATE encomenda SET prazo_limite = ? WHERE id = ?", (ontem, encomenda_id))
            db.execute("UPDATE proposta SET prazo_entrega = ?", (ontem,))

    pagina = cliente_a.get("/encomendas").get_data(as_text=True)  # qualquer página de encomendas dispara a expiração
    assert "Milho em grão" not in pagina
    assert consultar(app, "SELECT status FROM encomenda WHERE id = ?", encomenda_id)[0] == "expirada"
    assert consultar(app, "SELECT status FROM proposta")[0] == "nao_selecionada"
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ? ORDER BY id DESC", comprador_id)[0] == "encomenda_expirada"
    assert "Prazo encerrado" in comprador.get(f"/encomendas/{encomenda_id}").get_data(as_text=True)


# ---------- painel ----------

def test_painel_lista_encomendas_e_propostas(pessoas):
    _, comprador = pessoas["comprador"]
    _, cliente_a = pessoas["a"]
    encomenda_id = id_criado(publicar(comprador))
    propor(cliente_a, encomenda_id)
    painel_comprador = comprador.get("/painel").get_data(as_text=True)
    assert "Milho em grão" in painel_comprador and "1 proposta para responder" in painel_comprador
    painel_vendedor = cliente_a.get("/painel").get_data(as_text=True)
    assert "Milho em grão" in painel_vendedor and "Aguardando resposta" in painel_vendedor
