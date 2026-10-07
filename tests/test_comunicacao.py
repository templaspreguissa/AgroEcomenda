"""Iteração 5: conversas (RF33), avisos (RF13) e alertas de oportunidade na região (RF37)."""
import re
from datetime import date, timedelta

import pytest

from app import servicos
from app.db import get_db

from .conftest import (
    BELO_HORIZONTE, GOIANIA, SACRAMENTO, UBERABA, cliente_logado, criar_comercio, criar_produtor, criar_usuario,
    token_csrf,
)

HORTALICAS, QUEIJOS, PRODUCAO_AGRICOLA = 12, 31, 1


def _produto(app, vendedor_id, titulo="Alface crespa", categoria_id=HORTALICAS, municipio_id=UBERABA,
             consumidor=350, loja=None):
    with app.app_context():
        return servicos.criar_produto(get_db(), vendedor_id, {
            "titulo": titulo, "categoria_id": categoria_id, "descricao": "", "unidade_id": 12,
            "quantidade_disponivel": None, "municipio_id": municipio_id,
            "para_consumidor": consumidor is not None, "preco_consumidor_centavos": consumidor,
            "para_lojista": loja is not None, "preco_lojista_centavos": loja, "pedido_minimo_lojista": None,
            "so_verificados": False, "disponibilidade": "ano_todo", "meses_safra": 0,
        }, {}, [])


def _encomenda(app, comprador_id, categoria_id=HORTALICAS, municipio_id=UBERABA, titulo="Alface toda semana"):
    with app.app_context():
        return servicos.criar_encomenda(get_db(), comprador_id, {
            "titulo": titulo, "categoria_id": categoria_id, "descricao": "", "quantidade": 300, "unidade_id": 12,
            "municipio_id": municipio_id, "prazo_limite": date.today() + timedelta(days=10),
            "transporte": "a_combinar", "condicoes_pagamento": "",
        })


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


def todas(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


@pytest.fixture
def pessoas(app):
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, produtora, "Sítio Boa Vista")
    consumidor = criar_usuario(app, "Marina Costa", "marina@exemplo.com")
    lojista = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    criar_comercio(app, lojista, "Mercado Bom Preço")
    outro = criar_usuario(app, "Pedro Alves", "pedro@exemplo.com")
    return {
        "produtora": (produtora, cliente_logado(app, produtora)),
        "consumidor": (consumidor, cliente_logado(app, consumidor)),
        "lojista": (lojista, cliente_logado(app, lojista)),
        "outro": (outro, cliente_logado(app, outro)),
        "produto": _produto(app, produtora),
    }


def iniciar(cliente, sobre, contexto_id, texto="Bom dia! Vocês entregam em Uberaba?"):
    url = f"/mensagens/nova?sobre={sobre}&id={contexto_id}"
    return cliente.post("/mensagens/nova", data={
        "csrf_token": token_csrf(cliente, "/painel"), "sobre": sobre, "id": str(contexto_id), "texto": texto,
    }, headers={"Referer": url})


def responder(cliente, conversa_id, texto):
    return cliente.post(f"/mensagens/{conversa_id}", data={"csrf_token": token_csrf(cliente, "/painel"), "texto": texto})


def id_da_conversa(resposta):
    assert resposta.status_code == 302, resposta.get_data(as_text=True)[:500]
    return int(re.search(r"/mensagens/(\d+)", resposta.headers["Location"]).group(1))


def contador(cliente, rotulo):
    """Número na bolinha do topo para 'Avisos' ou 'Mensagens' (0 se não há bolinha)."""
    html = cliente.get("/").get_data(as_text=True)
    trecho = re.search(rf'<span class="menu__texto">{rotulo}</span>\s*(?:<span class="contador-bolha">(\d+))?', html)
    return int(trecho.group(1) or 0)


# ---------- conversas (RF33) ----------

def test_perguntar_ao_produtor_e_receber_resposta(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    produto = pessoas["produto"]

    pagina = consumidor.get(f"/mensagens/nova?sobre=produto&id={produto}").get_data(as_text=True)
    assert "Para: Ana · Sítio Boa Vista" in pagina and "Alface crespa" in pagina
    conversa = id_da_conversa(iniciar(consumidor, "produto", produto))
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ?", produtora_id)[0] == "nova_mensagem"
    assert contador(produtora, "Mensagens") == 1

    tela = produtora.get(f"/mensagens/{conversa}").get_data(as_text=True)
    assert "Vocês entregam em Uberaba?" in tela and "Marina" in tela
    # Abrir a conversa marca como lida, e o contador do topo já sai zerado nessa mesma página.
    assert not re.search(r'menu__texto">Mensagens</span>\s*<span class="contador-bolha">', tela)
    assert contador(produtora, "Mensagens") == 0

    assert responder(produtora, conversa, "Entregamos sim!").status_code == 302
    assert contador(consumidor, "Mensagens") == 1
    caixa = consumidor.get("/mensagens").get_data(as_text=True)
    assert "Ana · Sítio Boa Vista" in caixa and "Entregamos sim!" in caixa

    # Voltar ao mesmo assunto leva à mesma conversa, sem criar outra.
    resposta = consumidor.get(f"/mensagens/nova?sobre=produto&id={produto}")
    assert resposta.status_code == 302 and resposta.headers["Location"] == f"/mensagens/{conversa}"
    assert consultar(app, "SELECT COUNT(*) FROM conversa")[0] == 1


def test_so_os_participantes_veem_a_conversa(app, pessoas):
    _, consumidor = pessoas["consumidor"]
    _, outro = pessoas["outro"]
    conversa = id_da_conversa(iniciar(consumidor, "produto", pessoas["produto"]))
    assert outro.get(f"/mensagens/{conversa}").status_code == 404
    assert responder(outro, conversa, "Oi").status_code == 404
    assert "Bom dia" not in outro.get("/mensagens").get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM mensagem")[0] == 1


def test_conversa_nao_mostra_email_e_escapa_html(pessoas):
    _, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    conversa = id_da_conversa(iniciar(consumidor, "produto", pessoas["produto"], "<script>alert(1)</script>"))
    tela = produtora.get(f"/mensagens/{conversa}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in tela and "&lt;script&gt;" in tela
    assert "marina@exemplo.com" not in tela and "Costa" not in tela  # só o primeiro nome (D13)


def test_conversa_com_loja_so_para_produtores(app, pessoas):
    lojista_id, _ = pessoas["lojista"]
    _, consumidor = pessoas["consumidor"]
    _, produtora = pessoas["produtora"]
    assert consumidor.get(f"/mensagens/nova?sobre=loja&id={lojista_id}").status_code == 403
    assert iniciar(consumidor, "loja", lojista_id).status_code == 403
    assert "Apresentar meus produtos" in produtora.get(f"/comercios/{lojista_id}").get_data(as_text=True)
    conversa = id_da_conversa(iniciar(produtora, "loja", lojista_id, "Olá! Tenho alface e tomate toda semana."))
    assert "Loja Mercado Bom Preço" in produtora.get(f"/mensagens/{conversa}").get_data(as_text=True)


def test_conversa_sobre_proposta_so_entre_as_partes(app, pessoas):
    consumidor_id, consumidor = pessoas["consumidor"]
    _, produtora = pessoas["produtora"]
    _, outro = pessoas["outro"]
    with app.app_context():
        db = get_db()
        produto = servicos.buscar_produto(db, pessoas["produto"])
        proposta = servicos.enviar_proposta_produto(db, produto, consumidor_id, {
            "preco_centavos": 300, "quantidade": 10, "prazo_entrega": date.today() + timedelta(days=3),
            "transporte": "comprador_retira", "validade": None, "observacao": "",
        }, "consumidor")
    assert outro.get(f"/mensagens/nova?sobre=proposta&id={proposta}").status_code == 404
    assert iniciar(outro, "proposta", proposta).status_code == 404
    assert f"sobre=proposta&amp;id={proposta}" in produtora.get(f"/produtos/{pessoas['produto']}").get_data(as_text=True)
    conversa = id_da_conversa(iniciar(produtora, "proposta", proposta, "Posso entregar na quinta?"))
    assert "Proposta: Alface crespa" in consumidor.get(f"/mensagens/{conversa}").get_data(as_text=True)


def test_produtor_tira_duvida_sobre_encomenda(app, pessoas):
    consumidor_id, consumidor = pessoas["consumidor"]
    _, produtora = pessoas["produtora"]
    encomenda = _encomenda(app, consumidor_id)
    assert "Tirar dúvida com o comprador" in produtora.get(f"/encomendas/{encomenda}").get_data(as_text=True)
    conversa = id_da_conversa(iniciar(produtora, "encomenda", encomenda, "Pode ser alface americana?"))
    assert "Encomenda: Alface toda semana" in consumidor.get(f"/mensagens/{conversa}").get_data(as_text=True)


def test_nao_manda_mensagem_para_si_mesmo(app, pessoas):
    _, produtora = pessoas["produtora"]
    resposta = produtora.get(f"/mensagens/nova?sobre=produto&id={pessoas['produto']}")
    assert resposta.status_code == 302
    assert "Não dá para mandar mensagem para você mesmo" in produtora.get(resposta.headers["Location"]).get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM conversa")[0] == 0


@pytest.mark.parametrize("consulta", [
    "sobre=planeta&id=1", "sobre=produto&id=abc", "sobre=produto&id=999", "sobre=contrato&id=1", "sobre=produto",
])
def test_assunto_invalido_da_404(pessoas, consulta):
    _, consumidor = pessoas["consumidor"]
    assert consumidor.get(f"/mensagens/nova?{consulta}").status_code == 404


def test_produto_oculto_nao_recebe_mensagem(app, pessoas):
    _, consumidor = pessoas["consumidor"]
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE produto SET status = 'oculto'")
    assert consumidor.get(f"/mensagens/nova?sobre=produto&id={pessoas['produto']}").status_code == 404


@pytest.mark.parametrize("texto, mensagem", [("   ", "Escreva a mensagem."), ("x" * 2001, "Use no máximo 2000")])
def test_mensagem_vazia_ou_longa(app, pessoas, texto, mensagem):
    _, consumidor = pessoas["consumidor"]
    resposta = iniciar(consumidor, "produto", pessoas["produto"], texto)
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM mensagem")[0] == 0


def test_limite_de_conversas_novas_por_dia(app, pessoas):
    app.config["CONVERSAS_NOVAS_POR_DIA"] = 2
    produtora_id, _ = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    outro_produto = _produto(app, produtora_id, "Tomate italiano")
    id_da_conversa(iniciar(consumidor, "produto", pessoas["produto"]))
    id_da_conversa(iniciar(consumidor, "produto", outro_produto))
    resposta = iniciar(consumidor, "vitrine", produtora_id)
    assert "conversas nas últimas 24 horas" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM conversa")[0] == 2


def test_limite_de_mensagens_por_hora(app, pessoas):
    app.config["MENSAGENS_POR_HORA"] = 2
    _, consumidor = pessoas["consumidor"]
    conversa = id_da_conversa(iniciar(consumidor, "produto", pessoas["produto"]))
    responder(consumidor, conversa, "Segunda mensagem")
    resposta = responder(consumidor, conversa, "Terceira mensagem")
    assert "muitas mensagens na última hora" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM mensagem")[0] == 2


def test_mensagens_exigem_login(client):
    for url in ("/mensagens", "/mensagens/1", "/mensagens/nova?sobre=produto&id=1", "/avisos"):
        resposta = client.get(url)
        assert resposta.status_code == 302 and "/entrar" in resposta.headers["Location"]


# ---------- avisos (RF13) ----------

def test_avisos_lista_abre_e_marca_como_lido(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    _, outro = pessoas["outro"]
    conversa = id_da_conversa(iniciar(consumidor, "produto", pessoas["produto"]))
    assert contador(produtora, "Avisos") == 1
    pagina = produtora.get("/avisos").get_data(as_text=True)
    assert "Marina mandou uma mensagem sobre Alface crespa." in pagina
    aviso = consultar(app, "SELECT id FROM notificacao WHERE usuario_id = ?", produtora_id)[0]

    assert outro.get(f"/avisos/{aviso}").status_code == 404  # aviso de outra pessoa
    resposta = produtora.get(f"/avisos/{aviso}")
    assert resposta.headers["Location"] == f"/mensagens/{conversa}"
    assert consultar(app, "SELECT lida_em IS NOT NULL FROM notificacao WHERE id = ?", aviso)[0] == 1
    assert contador(produtora, "Avisos") == 0


def test_marcar_todos_os_avisos_como_lidos(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    with app.app_context():
        db = get_db()
        with db:
            for numero in range(3):
                servicos.notificar(db, produtora_id, "nova_proposta", f"Aviso {numero}", "/painel")
    assert contador(produtora, "Avisos") == 3
    produtora.post("/avisos/lidos", data={"csrf_token": token_csrf(produtora, "/avisos")})
    assert contador(produtora, "Avisos") == 0


def test_aviso_nunca_leva_para_fora_do_site(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    with app.app_context():
        db = get_db()
        with db:
            servicos.notificar(db, produtora_id, "nova_proposta", "Link estranho", "https://exemplo.com/golpe")
    aviso = consultar(app, "SELECT id FROM notificacao")[0]
    assert produtora.get(f"/avisos/{aviso}").headers["Location"] == "/avisos"


# ---------- alertas da região (RF37) ----------

def test_produto_para_lojas_avisa_lojas_da_regiao_que_compram_a_categoria(app):
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, produtora)
    perto = criar_usuario(app, "Loja Perto", "perto@exemplo.com")
    criar_comercio(app, perto, "Mercado Perto", cnpj="11222333000181", municipio_id=SACRAMENTO, interesses=[HORTALICAS])
    longe = criar_usuario(app, "Loja Longe", "longe@exemplo.com")
    criar_comercio(app, longe, "Mercado Longe", cnpj="12ABC34501DE35", municipio_id=BELO_HORIZONTE, interesses=[HORTALICAS])
    sem_interesse = criar_usuario(app, "Loja Queijo", "queijo@exemplo.com")
    criar_comercio(app, sem_interesse, "Queijaria", cnpj="AGRO2026PROD96", municipio_id=UBERABA, interesses=[QUEIJOS])

    _produto(app, produtora, "Alface só para consumidor")  # não é para lojas: ninguém é avisado
    assert consultar(app, "SELECT COUNT(*) FROM notificacao")[0] == 0
    produto = _produto(app, produtora, "Alface para lojas", consumidor=None, loja=240)
    avisados = {linha[0] for linha in todas(app, "SELECT usuario_id FROM notificacao WHERE tipo = 'produto_na_regiao'")}
    assert avisados == {perto}
    texto, link = consultar(app, "SELECT texto, link FROM notificacao WHERE usuario_id = ?", perto)
    assert "Alface para lojas" in texto and "Sítio Teste" in texto and link == f"/produtos/{produto}"


def test_interesse_na_categoria_principal_vale_para_as_subcategorias(app):
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, produtora)
    loja = criar_usuario(app, "Loja", "loja@exemplo.com")
    criar_comercio(app, loja, "Mercado", interesses=[PRODUCAO_AGRICOLA])
    _produto(app, produtora, "Alface para lojas", consumidor=None, loja=240)
    assert consultar(app, "SELECT COUNT(*) FROM notificacao WHERE usuario_id = ?", loja)[0] == 1


def test_encomenda_avisa_produtores_da_regiao_que_vendem_a_categoria(app):
    comprador = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    perto = criar_usuario(app, "Produtor Perto", "perto@exemplo.com")
    criar_produtor(app, perto, "Horta Perto", municipio_id=SACRAMENTO)
    _produto(app, perto, "Alface", municipio_id=SACRAMENTO)
    longe = criar_usuario(app, "Produtor Longe", "longe@exemplo.com")
    criar_produtor(app, longe, "Horta Longe", municipio_id=GOIANIA)
    _produto(app, longe, "Alface", municipio_id=GOIANIA)
    outra_categoria = criar_usuario(app, "Queijeiro", "queijo@exemplo.com")
    criar_produtor(app, outra_categoria, "Queijaria", municipio_id=UBERABA)
    _produto(app, outra_categoria, "Queijo", categoria_id=QUEIJOS)

    encomenda = _encomenda(app, comprador)
    avisados = {linha[0] for linha in todas(app, "SELECT usuario_id FROM notificacao WHERE tipo = 'encomenda_na_regiao'")}
    assert avisados == {perto}
    assert consultar(app, "SELECT link FROM notificacao WHERE usuario_id = ?", perto)[0] == f"/encomendas/{encomenda}"
