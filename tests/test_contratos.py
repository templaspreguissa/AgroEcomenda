"""Iteração 6: contratos de fornecimento (RF34), impressão (RF35) e parcerias públicas (RF36)."""
import hashlib
import json
import re
from datetime import date, timedelta

import pytest

from app import servicos
from app.db import get_db
from app.servicos import contratos

from .conftest import SACRAMENTO, cliente_logado, criar_comercio, criar_produtor, criar_usuario, token_csrf

HORTALICAS, MACO = 12, 12
HOJE = date.today()


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


def todas(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


@pytest.fixture
def partes(app):
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, produtora, "Sítio Boa Vista")
    loja = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    criar_comercio(app, loja, "Mercado Bom Preço", cnpj="12ABC34501DE35", municipio_id=SACRAMENTO)
    outro = criar_usuario(app, "Pedro Alves", "pedro@exemplo.com")
    with app.app_context():
        produto = servicos.criar_produto(get_db(), produtora, {
            "titulo": "Alface crespa", "categoria_id": HORTALICAS, "descricao": "", "unidade_id": MACO,
            "quantidade_disponivel": None, "municipio_id": 3170107, "para_consumidor": True,
            "preco_consumidor_centavos": 350, "para_lojista": True, "preco_lojista_centavos": 240,
            "pedido_minimo_lojista": 50, "so_verificados": False, "disponibilidade": "ano_todo", "meses_safra": 0,
        }, {}, [])
    return {
        "produtora_id": produtora, "produtora": cliente_logado(app, produtora),
        "loja_id": loja, "loja": cliente_logado(app, loja),
        "outro": cliente_logado(app, outro), "produto": produto,
    }


def dados_do_formulario(cliente, url, **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/painel"),
        "inicio": HOJE.isoformat(), "termino": (HOJE + timedelta(days=180)).isoformat(),
        "frequencia": "semanal", "dia_entrega": "segundas, até 10h", "transporte": "vendedor_entrega",
        "municipio_entrega": "Sacramento/MG", "local_entrega": "Rua das Flores, 100 (fictício)",
        "condicoes_pagamento": "Boleto 14 dias após cada entrega", "reajuste": "", "padrao_qualidade": "Maços de 300 g",
        "aviso_previo_dias": "30", "observacoes": "",
        "itens-0-produto_id": "", "itens-0-descricao": "Alface crespa", "itens-0-quantidade": "300",
        "itens-0-unidade_id": str(MACO), "itens-0-preco": "2,40",
    }
    dados.update(mudancas)
    return cliente.post(url, data={chave: valor for chave, valor in dados.items() if valor is not None})


def propor(partes, **mudancas):
    """A produtora propõe à loja, a partir da página da loja. Devolve o id do contrato (rascunho)."""
    resposta = dados_do_formulario(partes["produtora"], f"/contratos/novo?loja={partes['loja_id']}", **mudancas)
    assert resposta.status_code == 302, resposta.get_data(as_text=True)[:600]
    return int(re.search(r"/contratos/(\d+)", resposta.headers["Location"]).group(1))


def agir(cliente, contrato_id, acao, **campos):
    dados = {"csrf_token": token_csrf(cliente, "/painel"), **campos}
    return cliente.post(f"/contratos/{contrato_id}/{acao}", data=dados)


def hash_atual(app, contrato_id):
    return consultar(app, "SELECT v.hash FROM contrato c JOIN contrato_versao v ON v.contrato_id = c.id "
                          "AND v.versao = c.versao_atual WHERE c.id = ?", contrato_id)[0]


# ---------- fluxo completo ----------

def test_propor_enviar_e_aceitar(app, partes):
    loja = partes["loja"]
    contrato = propor(partes)
    assert consultar(app, "SELECT status FROM contrato")[0] == "rascunho"
    assert loja.get(f"/contratos/{contrato}").status_code == 404  # rascunho só existe para o autor

    agir(partes["produtora"], contrato, "enviar")
    assert consultar(app, "SELECT status, aguardando_id FROM contrato")[:] == ("enviado", partes["loja_id"])
    assert consultar(app, "SELECT COUNT(*) FROM notificacao WHERE usuario_id = ? AND tipo = 'contrato'", partes["loja_id"])[0] == 1
    pagina = loja.get(f"/contratos/{contrato}").get_data(as_text=True)
    assert "Sítio Boa Vista aguarda a sua resposta" in pagina and "Alface crespa" in pagina
    assert "Rua das Flores, 100" in pagina  # o local de entrega é visto pelas duas partes

    resposta = agir(loja, contrato, "aceitar", hash=hash_atual(app, contrato))
    assert resposta.status_code == 302
    assert consultar(app, "SELECT status FROM contrato")[0] == "ativo"
    aceites = todas(app, "SELECT usuario_id, versao, hash FROM contrato_aceite ORDER BY usuario_id")
    assert {a["usuario_id"] for a in aceites} == {partes["produtora_id"], partes["loja_id"]}
    assert len({a["hash"] for a in aceites}) == 1  # os dois aceitaram exatamente a mesma versão

    ativo = partes["produtora"].get(f"/contratos/{contrato}").get_data(as_text=True)
    assert "rita@exemplo.com" in ativo  # contato liberado depois do aceite das duas partes


def test_hash_e_o_sha256_do_json_guardado(app, partes):
    contrato = propor(partes)
    agir(partes["produtora"], contrato, "enviar")
    versao = consultar(app, "SELECT termos, hash FROM contrato_versao")
    assert hashlib.sha256(versao["termos"].encode("utf-8")).hexdigest() == versao["hash"]
    termos = json.loads(versao["termos"])
    assert termos["comprador"]["cnpj"] == "12ABC34501DE35" and termos["fornecedor"]["vitrine"] == "Sítio Boa Vista"
    assert termos["itens"][0]["preco_unitario_centavos"] == 240
    assert "o código bate com os termos guardados" in partes["loja"].get(f"/contratos/{contrato}").get_data(as_text=True)


def test_alteracao_vira_nova_versao_e_aceite_antigo_e_recusado(app, partes):
    loja, produtora = partes["loja"], partes["produtora"]
    contrato = propor(partes)
    agir(produtora, contrato, "enviar")
    hash_v1 = hash_atual(app, contrato)

    # A loja propõe outro preço: versão 2, já aceita pela loja, e a vez passa para a produtora.
    resposta = dados_do_formulario(loja, f"/contratos/{contrato}/editar", **{"itens-0-preco": "2,20"})
    assert resposta.status_code == 302
    linha = consultar(app, "SELECT versao_atual, aguardando_id FROM contrato")
    assert tuple(linha) == (2, partes["produtora_id"])
    hash_v2 = hash_atual(app, contrato)
    assert hash_v2 != hash_v1

    # A produtora tenta aceitar com a página antiga aberta (hash da versão 1): recusado.
    resposta = agir(produtora, contrato, "aceitar", hash=hash_v1)
    assert "O contrato mudou desde que você abriu a página" in produtora.get(resposta.headers["Location"]).get_data(as_text=True)
    assert consultar(app, "SELECT status FROM contrato")[0] == "enviado"

    agir(produtora, contrato, "aceitar", hash=hash_v2)
    assert consultar(app, "SELECT status FROM contrato")[0] == "ativo"
    assert consultar(app, "SELECT preco_unitario_centavos FROM contrato_item")[0] == 220


def test_quem_nao_e_parte_recebe_404(app, partes):
    contrato = propor(partes)
    agir(partes["produtora"], contrato, "enviar")
    outro = partes["outro"]
    for url in (f"/contratos/{contrato}", f"/contratos/{contrato}/imprimir", f"/contratos/{contrato}/editar"):
        assert outro.get(url).status_code == 404
    assert agir(outro, contrato, "aceitar", hash=hash_atual(app, contrato)).status_code == 404
    assert outro.get(f"/mensagens/nova?sobre=contrato&id={contrato}").status_code == 404
    assert consultar(app, "SELECT status FROM contrato")[0] == "enviado"


def test_so_quem_esta_sendo_aguardado_responde(app, partes):
    contrato = propor(partes)
    agir(partes["produtora"], contrato, "enviar")
    agir(partes["produtora"], contrato, "aceitar", hash=hash_atual(app, contrato))  # quem enviou não "aceita de novo"
    assert consultar(app, "SELECT status FROM contrato")[0] == "enviado"
    resposta = partes["produtora"].get(f"/contratos/{contrato}/editar")
    assert resposta.status_code == 302  # não é a vez dela alterar


def test_descartar_rascunho_apaga_e_a_outra_parte_nunca_ve(app, partes):
    contrato = propor(partes)
    assert partes["produtora"].get(f"/mensagens/nova?sobre=contrato&id={contrato}").status_code == 404
    resposta = agir(partes["produtora"], contrato, "cancelar")
    assert resposta.headers["Location"] == "/contratos"
    assert consultar(app, "SELECT COUNT(*) FROM contrato")[0] == 0
    assert consultar(app, "SELECT COUNT(*) FROM contrato_item")[0] == 0
    assert partes["loja"].get(f"/contratos/{contrato}").status_code == 404


def test_recusar_e_cancelar(app, partes):
    contrato = propor(partes)
    agir(partes["produtora"], contrato, "enviar")
    agir(partes["loja"], contrato, "recusar", motivo="Preço acima do que pagamos hoje")
    linha = consultar(app, "SELECT status, motivo_encerramento FROM contrato WHERE id = ?", contrato)
    assert tuple(linha) == ("recusado", "Preço acima do que pagamos hoje")

    segundo = propor(partes)
    agir(partes["produtora"], segundo, "enviar")
    agir(partes["loja"], segundo, "cancelar")  # quem está sendo aguardado recusa; não cancela
    assert consultar(app, "SELECT status FROM contrato WHERE id = ?", segundo)[0] == "enviado"
    agir(partes["produtora"], segundo, "cancelar")
    assert consultar(app, "SELECT status FROM contrato WHERE id = ?", segundo)[0] == "cancelado"


def _ativar(app, partes):
    contrato = propor(partes)
    agir(partes["produtora"], contrato, "enviar")
    agir(partes["loja"], contrato, "aceitar", hash=hash_atual(app, contrato))
    return contrato


def test_rescisao_exige_motivo_e_respeita_o_aviso_previo(app, partes):
    contrato = _ativar(app, partes)
    agir(partes["loja"], contrato, "rescindir", motivo="")
    assert consultar(app, "SELECT status FROM contrato")[0] == "ativo"
    agir(partes["loja"], contrato, "rescindir", motivo="Fechamos a seção de hortifrúti")
    linha = consultar(app, "SELECT status, rescisao_efetiva_em FROM contrato")
    assert linha["status"] == "rescindido"
    assert linha["rescisao_efetiva_em"] == (HOJE + timedelta(days=30)).isoformat()


def test_encerramento_automatico_no_fim_da_vigencia(app, partes):
    contrato = _ativar(app, partes)
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE contrato SET inicio = ?, termino = ?",
                       ((HOJE - timedelta(days=60)).isoformat(), (HOJE - timedelta(days=1)).isoformat()))
    partes["loja"].get("/contratos")
    assert consultar(app, "SELECT status FROM contrato WHERE id = ?", contrato)[0] == "encerrado"


def test_parceria_so_aparece_com_as_duas_autorizacoes(app, partes, client):
    contrato = _ativar(app, partes)
    vitrine = f"/produtores/{partes['produtora_id']}"
    produto = f"/produtos/{partes['produto']}"
    agir(partes["produtora"], contrato, "parceria", mostrar="1")
    assert "Encontre também em" not in client.get(vitrine).get_data(as_text=True)
    agir(partes["loja"], contrato, "parceria", mostrar="1")
    pagina = client.get(vitrine).get_data(as_text=True)
    assert "Encontre também em" in pagina and "Mercado Bom Preço — Sacramento/MG" in pagina
    assert "Também à venda em" not in client.get(produto).get_data(as_text=True)  # item sem produto do catálogo

    agir(partes["loja"], contrato, "rescindir", motivo="Fim da parceria de teste")
    assert "Encontre também em" not in client.get(vitrine).get_data(as_text=True)


def test_contrato_a_partir_do_produto_ja_vem_preenchido(app, partes):
    loja = partes["loja"]
    pagina = loja.get(f"/produtos/{partes['produto']}").get_data(as_text=True)
    assert "Propor contrato de fornecimento" in pagina
    formulario = loja.get(f"/contratos/novo?produto={partes['produto']}").get_data(as_text=True)
    assert 'value="2,40"' in formulario and 'value="50"' in formulario  # preço e pedido mínimo para lojas
    resposta = dados_do_formulario(loja, f"/contratos/novo?produto={partes['produto']}", **{
        "itens-0-produto_id": str(partes["produto"]), "itens-0-descricao": "", "itens-0-unidade_id": "",
    })
    assert resposta.status_code == 302
    item = consultar(app, "SELECT produto_id, descricao, unidade_id FROM contrato_item")
    assert tuple(item) == (partes["produto"], "Alface crespa", MACO)  # descrição e unidade vêm do catálogo
    assert consultar(app, "SELECT autor_id, produtor_id FROM contrato")[:] == (partes["loja_id"], partes["produtora_id"])

    # Com o item ligado ao produto, a página do produto mostra a loja parceira.
    contrato = consultar(app, "SELECT id FROM contrato")[0]
    agir(loja, contrato, "enviar")
    agir(partes["produtora"], contrato, "aceitar", hash=hash_atual(app, contrato))
    agir(loja, contrato, "parceria", mostrar="1")
    agir(partes["produtora"], contrato, "parceria", mostrar="1")
    assert "Também à venda em" in partes["outro"].get(f"/produtos/{partes['produto']}").get_data(as_text=True)


def test_consumidor_sem_loja_nao_propoe_contrato(app, partes):
    resposta = partes["outro"].get(f"/contratos/novo?produto={partes['produto']}")
    assert resposta.status_code == 302
    assert consultar(app, "SELECT COUNT(*) FROM contrato")[0] == 0


def test_loja_nao_propoe_contrato_a_outra_loja(app, partes):
    resposta = partes["loja"].get(f"/contratos/novo?loja={partes['loja_id']}")
    assert resposta.status_code == 302  # loja sem vitrine não propõe "como produtor"


def test_proposta_aceita_vira_contrato(app, partes):
    loja_id = partes["loja_id"]
    with app.app_context():
        db = get_db()
        produto = servicos.buscar_produto(db, partes["produto"])
        proposta = servicos.enviar_proposta_produto(db, produto, loja_id, {
            "preco_centavos": 230, "quantidade": 300, "prazo_entrega": HOJE + timedelta(days=3),
            "transporte": "vendedor_entrega", "validade": None, "observacao": "",
        }, "lojista")
    url = f"/contratos/novo?proposta={proposta}"
    assert partes["loja"].get(url).status_code == 302  # proposta ainda pendente
    with app.app_context():
        db = get_db()
        servicos.responder_proposta_produto(db, servicos.buscar_proposta(db, proposta),
                                            servicos.buscar_produto(db, partes["produto"]), partes["produtora_id"], True)
    assert "Transformar em contrato" in partes["loja"].get(f"/produtos/{partes['produto']}").get_data(as_text=True)
    formulario = partes["loja"].get(url).get_data(as_text=True)
    assert 'value="2,30"' in formulario and 'value="300"' in formulario
    assert partes["outro"].get(url).status_code == 404


@pytest.mark.parametrize("mudancas, mensagem", [
    ({"termino": HOJE.isoformat()}, "O fim precisa ser depois do início."),
    ({"termino": (HOJE + timedelta(days=800)).isoformat()}, "vigência de até dois anos"),
    ({"itens-0-descricao": "", "itens-0-quantidade": "", "itens-0-preco": "", "itens-0-unidade_id": ""},
     "Inclua pelo menos um item"),
    ({"itens-0-preco": ""}, "Informe o preço."),
    ({"condicoes_pagamento": ""}, "Diga como e quando será o pagamento."),
    ({"aviso_previo_dias": "400"}, "Use de 0 a 180 dias."),
], ids=["fim-antes", "mais-de-2-anos", "sem-itens", "item-sem-preco", "sem-pagamento", "aviso-longo"])
def test_validacoes_do_formulario(app, partes, mudancas, mensagem):
    resposta = dados_do_formulario(partes["produtora"], f"/contratos/novo?loja={partes['loja_id']}", **mudancas)
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM contrato")[0] == 0


def test_item_nao_pode_ser_produto_de_outro_produtor(app, partes):
    intruso = criar_usuario(app, "Carlos", "carlos@exemplo.com")
    criar_produtor(app, intruso, "Outra Fazenda")
    with app.app_context():
        alheio = servicos.criar_produto(get_db(), intruso, {
            "titulo": "Queijo", "categoria_id": 31, "descricao": "", "unidade_id": 1, "quantidade_disponivel": None,
            "municipio_id": 3170107, "para_consumidor": True, "preco_consumidor_centavos": 4000, "para_lojista": False,
            "preco_lojista_centavos": None, "pedido_minimo_lojista": None, "so_verificados": False,
            "disponibilidade": "ano_todo", "meses_safra": 0,
        }, {6: "Selo ARTE"}, [])
        with pytest.raises(servicos.RegraNegocio, match="não é deste produtor"):
            contratos.validar_termos(get_db(), partes["produtora_id"], {
                "inicio": HOJE.isoformat(), "termino": (HOJE + timedelta(days=30)).isoformat(),
                "frequencia": "semanal", "transporte": "a_combinar", "aviso_previo_dias": 30,
            }, [{"produto_id": alheio}])


def test_versao_para_imprimir(app, partes):
    contrato = _ativar(app, partes)
    pagina = partes["loja"].get(f"/contratos/{contrato}/imprimir").get_data(as_text=True)
    assert "Contrato de fornecimento nº" in pagina and "12.ABC.345/01DE-35" in pagina
    assert hash_atual(app, contrato) in pagina
    assert "art. 10, § 2º, da Medida Provisória nº 2.200-2/2001" in pagina
    assert "Aceita por Ana Ribeiro" in pagina and "Aceita por Rita Souza" in pagina
    assert "Total por entrega" in pagina and "R$ 720,00" in pagina  # 300 maços x R$ 2,40
    assert "data-imprimir" in pagina and "<script>" not in pagina
