"""Iteração 4: preço por público (RF28, RF29, RF31, RF32).

O ponto principal: o preço para lojas nunca chega ao HTML de quem não pode vê-lo,
nem pode ser descoberto pelos filtros e pela ordenação por preço.
"""
from datetime import date, timedelta

import pytest

from app import servicos
from app.db import get_db
from app.util import hoje

from .conftest import UBERABA, cliente_logado, criar_comercio, criar_produtor, criar_usuario, token_csrf

KG, L, DZ, BANDEJA = 1, 5, 11, 14
QUEIJOS, LEITE, OVOS, FRUTAS = 31, 30, 32, 13
SELO_ARTE = {6: "Selo ARTE"}
SEM_REGISTRO = {6: "Sem registro: venda só para estabelecimento inspecionado"}

# Preços com centavos "estranhos" para não coincidirem com nenhum outro texto da página.
QUEIJO_CONSUMIDOR, QUEIJO_LOJA = "48,91", "36,17"
OVOS_CONSUMIDOR, OVOS_LOJA = "14,29", "10,53"
LEITE_LOJA = "2,47"
MORANGO_CONSUMIDOR = "12,88"
PRECOS_DE_LOJA = (QUEIJO_LOJA, OVOS_LOJA, LEITE_LOJA)


def _produto(app, vendedor_id, titulo, categoria_id, unidade_id, consumidor=None, loja=None, minimo=None,
             so_verificados=False, atributos=None, meses_safra=0):
    dados = {
        "titulo": titulo, "categoria_id": categoria_id, "descricao": "", "unidade_id": unidade_id,
        "quantidade_disponivel": 1000, "municipio_id": UBERABA,
        "para_consumidor": consumidor is not None, "preco_consumidor_centavos": consumidor,
        "para_lojista": loja is not None, "preco_lojista_centavos": loja, "pedido_minimo_lojista": minimo,
        "so_verificados": so_verificados,
        "disponibilidade": "safra" if meses_safra else "ano_todo", "meses_safra": meses_safra,
    }
    with app.app_context():
        return servicos.criar_produto(get_db(), vendedor_id, dados, atributos or {}, [])


@pytest.fixture
def cenario(app):
    dono = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, dono, "Sítio Boa Vista")
    produtos = {
        "queijo": _produto(app, dono, "Queijo para todos", QUEIJOS, KG, consumidor=4891, loja=3617, minimo=5,
                           atributos=SELO_ARTE),
        "leite": _produto(app, dono, "Leite só para lojas", LEITE, L, loja=247, minimo=500, atributos=SEM_REGISTRO),
        "ovos": _produto(app, dono, "Ovos para verificadas", OVOS, DZ, consumidor=1429, loja=1053, so_verificados=True,
                         atributos=SELO_ARTE),
        "morango": _produto(app, dono, "Morango só para consumidor", FRUTAS, BANDEJA, consumidor=1288),
    }
    consumidor = criar_usuario(app, "Marina Costa", "marina@exemplo.com")
    loja = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    criar_comercio(app, loja, "Mercado Bom Preço", cnpj="11222333000181")
    loja_verificada = criar_usuario(app, "Paulo Lima", "paulo@exemplo.com")
    criar_comercio(app, loja_verificada, "Empório Verificado", cnpj="12ABC34501DE35")
    app.test_cli_runner().invoke(args=["verificar-comercio", str(loja_verificada)])
    admin = criar_usuario(app, "Admin", "admin@exemplo.com")
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET papel = 'admin' WHERE id = ?", (admin,))
    return {
        "produtos": produtos, "dono_id": dono, "dono": cliente_logado(app, dono),
        "visitante": app.test_client(), "consumidor": cliente_logado(app, consumidor),
        "loja_id": loja, "loja": cliente_logado(app, loja),
        "loja_verificada": cliente_logado(app, loja_verificada), "admin": cliente_logado(app, admin),
    }


def html(cliente, url):
    resposta = cliente.get(url)
    assert resposta.status_code == 200, url
    return resposta.get_data(as_text=True)


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


# ---------- quem vê o quê ----------

@pytest.mark.parametrize("quem", ["visitante", "consumidor"])
def test_preco_de_loja_nunca_aparece_para_visitante_e_consumidor(cenario, quem):
    cliente = cenario[quem]
    produtos = cenario["produtos"]
    paginas = ["/", "/produtos", "/produtos?ordem=menor_preco", f"/produtores/{cenario['dono_id']}", "/produtores"]
    paginas += [f"/produtos/{produto_id}" for produto_id in produtos.values()]
    for url in paginas:
        pagina = html(cliente, url)
        for preco in PRECOS_DE_LOJA:
            assert preco not in pagina, (url, preco)

    lista = html(cliente, "/produtos")
    assert "Queijo para todos" in lista and QUEIJO_CONSUMIDOR in lista
    assert "Morango só para consumidor" in lista
    assert "Leite só para lojas" not in lista  # produto só para lojas some da lista
    detalhe_leite = html(cliente, f"/produtos/{produtos['leite']}")
    assert "Vendido só para lojas" in detalhe_leite


def test_loja_ve_preco_de_loja_pedido_minimo_e_referencia(cenario):
    lista = html(cenario["loja_verificada"], "/produtos")
    assert QUEIJO_LOJA in lista and LEITE_LOJA in lista and OVOS_LOJA in lista
    assert "Pedido mínimo: 5 kg" in lista
    assert f"Preço ao consumidor: R$ {QUEIJO_CONSUMIDOR}" in lista
    assert "Morango só para consumidor" not in lista  # no modo loja, só o que é vendido para lojas
    assert "Preços que você vê: <strong>para lojas</strong>" in lista


def test_preco_so_para_verificadas(cenario):
    ovos = f"/produtos/{cenario['produtos']['ovos']}"
    for url in ("/produtos", ovos, f"/produtores/{cenario['dono_id']}"):
        pagina = html(cenario["loja"], url)
        assert OVOS_LOJA not in pagina, url
    assert "Preço só para lojas verificadas" in html(cenario["loja"], ovos)
    assert OVOS_LOJA in html(cenario["loja_verificada"], ovos)


@pytest.mark.parametrize("consulta", [
    "?preco_min=10&preco_max=11",       # faixa que contém o preço escondido dos ovos
    "?preco_max=11&ordem=menor_preco",
])
def test_filtro_de_preco_nao_revela_preco_escondido(cenario, consulta):
    pagina = html(cenario["loja"], "/produtos" + consulta)
    assert "Ovos para verificadas" not in pagina
    assert "Ovos para verificadas" in html(cenario["loja_verificada"], "/produtos" + consulta)


def test_loja_pode_ver_como_consumidor_e_voltar(cenario):
    loja = cenario["loja"]
    resposta = loja.post("/ver-como", data={
        "csrf_token": token_csrf(loja, "/produtos"), "modo": "consumidor", "voltar": "/produtos?q=",
    })
    assert resposta.headers["Location"] == "/produtos?q="
    como_consumidor = html(loja, "/produtos")
    assert QUEIJO_CONSUMIDOR in como_consumidor and QUEIJO_LOJA not in como_consumidor
    assert "Morango só para consumidor" in como_consumidor and "Leite só para lojas" not in como_consumidor
    loja.post("/ver-como", data={"csrf_token": token_csrf(loja, "/produtos"), "modo": "loja", "voltar": "/produtos"})
    assert QUEIJO_LOJA in html(loja, "/produtos")


def test_ver_como_nao_aceita_destino_externo(cenario):
    loja = cenario["loja"]
    resposta = loja.post("/ver-como", data={
        "csrf_token": token_csrf(loja, "/produtos"), "modo": "consumidor", "voltar": "https://exemplo.com/golpe",
    })
    assert resposta.headers["Location"] == "/produtos"


def test_consumidor_nao_vira_loja_pelo_ver_como(cenario):
    consumidor = cenario["consumidor"]
    consumidor.post("/ver-como", data={"csrf_token": token_csrf(consumidor, "/produtos"), "modo": "loja"})
    pagina = html(consumidor, "/produtos")
    assert QUEIJO_LOJA not in pagina and "Leite só para lojas" not in pagina


@pytest.mark.parametrize("quem", ["dono", "admin"])
def test_dono_e_admin_veem_os_dois_precos(cenario, quem):
    pagina = html(cenario[quem], f"/produtos/{cenario['produtos']['queijo']}")
    assert QUEIJO_CONSUMIDOR in pagina and QUEIJO_LOJA in pagina
    assert "pedido mínimo 5 kg" in pagina


def test_vitrine_mostra_o_que_cada_publico_compra(cenario):
    vitrine = f"/produtores/{cenario['dono_id']}"
    do_consumidor = html(cenario["consumidor"], vitrine)
    assert "Morango só para consumidor" in do_consumidor and "Leite só para lojas" not in do_consumidor
    da_loja = html(cenario["loja"], vitrine)
    assert "Leite só para lojas" in da_loja and "Morango só para consumidor" not in da_loja
    do_dono = html(cenario["dono"], vitrine)
    assert "Leite só para lojas" in do_dono and "Morango só para consumidor" in do_dono


# ---------- propostas por canal (RF31) ----------

def propor(cliente, produto_id, **mudancas):
    url = f"/produtos/{produto_id}/proposta"
    dados = {
        "csrf_token": token_csrf(cliente, url), "preco": "30,00", "quantidade": "10",
        "prazo_entrega": (date.today() + timedelta(days=7)).isoformat(), "transporte": "comprador_retira",
    }
    dados.update(mudancas)
    return cliente.post(url, data=dados)


def test_canal_da_proposta_e_decidido_no_servidor(app, cenario):
    queijo = cenario["produtos"]["queijo"]
    assert propor(cenario["consumidor"], queijo, canal="lojista").status_code == 302  # campo extra é ignorado
    assert propor(cenario["loja"], queijo).status_code == 302
    canais = {linha[0]: linha[1] for linha in _todas(app, "SELECT comprador_id, canal FROM proposta")}
    assert canais[cenario["loja_id"]] == "lojista"
    assert sorted(canais.values()) == ["consumidor", "lojista"]


def _todas(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


def test_formulario_da_loja_vem_com_preco_e_pedido_minimo_de_loja(cenario):
    pagina = html(cenario["loja"], f"/produtos/{cenario['produtos']['queijo']}/proposta")
    assert "Pedir cotação para a loja" in pagina
    assert f'value="{QUEIJO_LOJA}"' in pagina and 'value="5"' in pagina
    pagina_consumidor = html(cenario["consumidor"], f"/produtos/{cenario['produtos']['queijo']}/proposta")
    assert "Fazer pedido" in pagina_consumidor and QUEIJO_LOJA not in pagina_consumidor


def test_pedido_minimo_para_lojas(app, cenario):
    resposta = propor(cenario["loja"], cenario["produtos"]["queijo"], quantidade="2")
    assert "menor que o pedido mínimo para lojas" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


def test_consumidor_nao_compra_produto_so_para_lojas(app, cenario):
    leite = cenario["produtos"]["leite"]
    consumidor = cenario["consumidor"]
    url = f"/produtos/{leite}/proposta"
    assert consumidor.get(url).status_code == 302
    # Mesmo enviando o formulário direto (com um token válido de outra página), a proposta não entra.
    resposta = consumidor.post(url, data={
        "csrf_token": token_csrf(consumidor, "/produtos"), "preco": "2,47", "quantidade": "600",
        "prazo_entrega": (date.today() + timedelta(days=7)).isoformat(), "transporte": "comprador_retira",
    })
    assert resposta.status_code == 302
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


def test_loja_nao_verificada_compra_como_consumidor_quando_o_preco_e_so_para_verificadas(app, cenario):
    assert propor(cenario["loja"], cenario["produtos"]["ovos"]).status_code == 302
    assert consultar(app, "SELECT canal FROM proposta")[0] == "consumidor"


def test_produtor_ve_o_nome_da_loja_na_proposta(cenario):
    queijo = cenario["produtos"]["queijo"]
    propor(cenario["loja"], queijo)
    pagina = html(cenario["dono"], f"/produtos/{queijo}")
    assert "Mercado Bom Preço" in pagina and "Souza" not in pagina  # nome completo só depois do aceite


def test_tirar_um_publico_encerra_as_propostas_dele(app, cenario):
    queijo = cenario["produtos"]["queijo"]
    propor(cenario["consumidor"], queijo)
    propor(cenario["loja"], queijo)
    dono = cenario["dono"]
    url = f"/produtos/{queijo}/editar"
    resposta = dono.post(url, data={
        "csrf_token": token_csrf(dono, url), "titulo": "Queijo para todos", "categoria_id": QUEIJOS,
        "unidade_id": KG, "municipio": "Uberaba/MG", "para_lojista": "y", "preco_lojista": "36,17",
        "disponibilidade": "ano_todo", "atributo-6": "Selo ARTE",
    }, content_type="multipart/form-data")
    assert resposta.status_code == 302
    situacao = {linha[0]: linha[1] for linha in _todas(app, "SELECT canal, status FROM proposta")}
    assert situacao == {"consumidor": "nao_selecionada", "lojista": "pendente"}
    assert consultar(app, "SELECT para_consumidor, preco_consumidor_centavos FROM produto WHERE id = ?", queijo)[0] == 0


# ---------- formulário (RF28, RF32) ----------

def cadastrar(cliente, **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/produtos/novo"), "titulo": "Alface crespa", "categoria_id": 12,
        "unidade_id": 12, "municipio": "Uberaba/MG", "para_consumidor": "y", "preco_consumidor": "3,50",
        "disponibilidade": "ano_todo",
    }
    dados.update(mudancas)
    dados = {chave: valor for chave, valor in dados.items() if valor is not None}
    return cliente.post("/produtos/novo", data=dados, content_type="multipart/form-data")


def test_campos_de_publico_desmarcado_sao_ignorados(app, cenario):
    resposta = cadastrar(cenario["dono"], preco_lojista="2,00", pedido_minimo="50", so_verificados="y")
    assert resposta.status_code == 302
    linha = consultar(app, "SELECT para_lojista, preco_lojista_centavos, pedido_minimo_lojista, so_verificados "
                           "FROM produto WHERE titulo = 'Alface crespa'")
    assert tuple(linha) == (0, None, None, 0)


def test_precisa_escolher_um_publico(app, cenario):
    resposta = cadastrar(cenario["dono"], para_consumidor=None)
    assert "Marque para quem você vende" in resposta.get_data(as_text=True)


def test_safra_precisa_dos_meses(cenario):
    resposta = cadastrar(cenario["dono"], disponibilidade="safra")
    assert "Marque os meses da safra." in resposta.get_data(as_text=True)


def test_fora_da_safra_some_do_filtro_deste_mes(app, cenario):
    fora = sum(1 << m for m in range(12) if m != hoje().month - 1)  # todos os meses, menos o atual
    _produto(app, cenario["dono_id"], "Manga fora de época", FRUTAS, KG, consumidor=500, meses_safra=fora)
    _produto(app, cenario["dono_id"], "Pitaya da época", FRUTAS, KG, consumidor=600, meses_safra=1 << (hoje().month - 1))
    cliente = cenario["consumidor"]
    tudo = html(cliente, "/produtos")
    assert "Manga fora de época" in tudo and "Fora da safra" in tudo
    deste_mes = html(cliente, "/produtos?agora=1")
    assert "Manga fora de época" not in deste_mes and "Pitaya da época" in deste_mes
    assert "Queijo para todos" in deste_mes  # o ano todo
