"""Produtos: fotos, campos por categoria, busca e propostas de compra (Iterações 2 e 4)."""
import os
from datetime import date, timedelta
from io import BytesIO

import pytest
from PIL import Image

from app.db import get_db

from .conftest import cliente_logado, criar_produtor, criar_usuario, token_csrf

DAQUI_10 = date.today() + timedelta(days=10)
QUEIJOS, GRAOS, BOVINOS, OVOS = 31, 10, 20, 32
UNIDADE_KG, UNIDADE_SC60, UNIDADE_DZ = 1, 3, 11
ATRIBUTO_RACA, ATRIBUTO_IDADE, ATRIBUTO_INSPECAO, ATRIBUTO_REGISTRO = 3, 4, 6, 7


def jpeg(largura=2000, altura=1500, com_gps=True):
    """Foto de teste. Por padrão leva EXIF com GPS, como uma foto de celular."""
    imagem = Image.new("RGB", (largura, altura), "green")
    exif = Image.Exif()
    if com_gps:
        exif[0x8825] = {1: "S", 2: (19.0, 45.0, 0.0)}
        exif[0x010F] = "Celular de Teste"
    saida = BytesIO()
    imagem.save(saida, "JPEG", exif=exif)
    return saida.getvalue()


def png():
    saida = BytesIO()
    Image.new("RGB", (300, 200), "yellow").save(saida, "PNG")
    return saida.getvalue()


@pytest.fixture
def pessoas(app):
    vendedor = criar_usuario(app, "José Carlos Pereira", "jose@exemplo.com")
    criar_produtor(app, vendedor, "Queijaria Serra Azul")
    comprador = criar_usuario(app, "Lúcia Helena Martins", "lucia@exemplo.com")
    outro = criar_usuario(app, "Pedro Alves", "pedro@exemplo.com")
    return {
        "vendedor": (vendedor, cliente_logado(app, vendedor)),
        "comprador": (comprador, cliente_logado(app, comprador)),
        "outro": (outro, cliente_logado(app, outro)),
    }


def cadastrar_produto(cliente, fotos=(), **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/produtos/novo"),
        "titulo": "Queijo minas artesanal",
        "categoria_id": QUEIJOS,
        "descricao": "Maturado por 22 dias.",
        "para_consumidor": "y",
        "preco_consumidor": "1.048,00",
        "unidade_id": UNIDADE_KG,
        "quantidade": "100",
        "municipio": "Uberaba/MG",
        "disponibilidade": "ano_todo",
        f"atributo-{ATRIBUTO_INSPECAO}": "Selo ARTE",
        f"atributo-{ATRIBUTO_REGISTRO}": "ARTE 123",
    }
    dados.update(mudancas)
    dados["fotos"] = [(BytesIO(conteudo), nome) for nome, conteudo in fotos]
    return cliente.post("/produtos/novo", data=dados, content_type="multipart/form-data")


def id_criado(resposta):
    assert resposta.status_code == 302, resposta.get_data(as_text=True)[:800]
    return int(resposta.headers["Location"].rstrip("/").split("/")[-1])


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


def arquivos_na_pasta(app):
    pasta = app.config["PASTA_FOTOS"]
    return sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []


def propor(cliente, produto_id, **mudancas):
    url = f"/produtos/{produto_id}/proposta"
    dados = {
        "csrf_token": token_csrf(cliente, url), "preco": "1.000,00", "quantidade": "10",
        "prazo_entrega": DAQUI_10.isoformat(), "transporte": "comprador_retira", "validade": "", "observacao": "",
    }
    dados.update(mudancas)
    return cliente.post(url, data=dados)


def postar(cliente, url, pagina):
    return cliente.post(url, data={"csrf_token": token_csrf(cliente, pagina)})


# ---------- publicar com fotos (RF04) ----------

def test_publicar_com_foto_remove_exif_e_redimensiona(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor, fotos=[("queijo.jpg", jpeg()), ("lateral.png", png())]))
    fotos = arquivos_na_pasta(app)
    assert len(fotos) == 2 and all(nome.endswith(".jpg") and len(nome) == 36 for nome in fotos)
    with Image.open(os.path.join(app.config["PASTA_FOTOS"], fotos[0])) as salva:
        assert salva.format == "JPEG"
        assert max(salva.size) <= 1280
        assert dict(salva.getexif()) == {}  # sem GPS nem fabricante
    pagina = vendedor.get(f"/produtos/{produto_id}").get_data(as_text=True)
    assert "R$ 1.048,00" in pagina and "Selo ARTE" in pagina and "ARTE 123" in pagina
    assert "Pode ser vendido em todo o país" in pagina


def test_foto_servida_com_tipo_correto(app, pessoas, client):
    _, vendedor = pessoas["vendedor"]
    id_criado(cadastrar_produto(vendedor, fotos=[("queijo.jpg", jpeg())]))
    nome = arquivos_na_pasta(app)[0]
    resposta = client.get(f"/fotos/{nome}")
    assert resposta.status_code == 200
    assert resposta.mimetype == "image/jpeg"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("nome, conteudo, mensagem", [
    ("falsa.jpg", b"<html><script>alert(1)</script></html>", "não é uma imagem válida"),
    ("animacao.gif", b"GIF89a", "não é uma foto aceita"),
    ("sem-extensao", jpeg(200, 150), "não é uma foto aceita"),
], ids=["html-disfarcado-de-jpg", "gif", "sem-extensao"])
def test_arquivos_recusados(app, pessoas, nome, conteudo, mensagem):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, fotos=[("boa.jpg", jpeg()), (nome, conteudo)])
    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM produto")[0] == 0
    assert arquivos_na_pasta(app) == []  # a foto boa enviada junto também foi apagada


def test_limite_de_fotos(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, fotos=[(f"f{i}.jpg", jpeg(200, 150)) for i in range(6)])
    assert "no máximo 5 fotos" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM produto")[0] == 0


def test_foto_grande_demais(app, pessoas):
    app.config["FOTO_TAMANHO_MAXIMO"] = 1024
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, fotos=[("grande.jpg", jpeg())])
    assert "passa de" in resposta.get_data(as_text=True)


def test_preco_opcional_vira_a_combinar(pessoas):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor, preco_consumidor=""))
    assert "A combinar" in vendedor.get(f"/produtos/{produto_id}").get_data(as_text=True)


# ---------- campos por categoria (RF05) ----------

def test_inspecao_obrigatoria_em_origem_animal(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_INSPECAO}": ""})
    assert "Informe serviço de inspeção." in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM produto")[0] == 0


def test_inspecao_fora_da_lista(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_INSPECAO}": "Inspecionado pelo vizinho"})
    assert "Escolha uma das opções." in resposta.get_data(as_text=True)


SEM_REGISTRO = "Sem registro: venda só para estabelecimento inspecionado"
SO_LOJAS = {"para_consumidor": "", "preco_consumidor": "", "para_lojista": "y", "preco_lojista": "2,40"}


@pytest.mark.parametrize("servico, aviso, publico", [
    ("SIM (municipal)", "pode ser vendido só dentro de Uberaba/MG", {}),
    ("SIE (estadual)", "pode ser vendido só dentro de MG", {}),
    (SEM_REGISTRO, "Não é para o consumidor final", SO_LOJAS),
], ids=["sim", "sie", "sem-registro"])
def test_aviso_de_area_de_venda_pela_inspecao(pessoas, client, servico, aviso, publico):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_INSPECAO}": servico}, **publico))
    assert aviso in client.get(f"/produtos/{produto_id}").get_data(as_text=True)


def test_sem_registro_de_inspecao_nao_vai_para_o_consumidor(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_INSPECAO}": SEM_REGISTRO})
    assert "Produto sem registro de inspeção só pode ser vendido para lojas" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM produto")[0] == 0


@pytest.mark.parametrize("comprador_em, permitido", [
    ("Uberaba/MG", True), ("Sacramento/MG", False),
], ids=["mesmo-municipio", "outro-municipio"])
def test_inspecao_municipal_limita_a_venda_ao_municipio(app, pessoas, comprador_em, permitido):
    _, vendedor = pessoas["vendedor"]
    comprador_id, comprador = pessoas["comprador"]
    produto_id = id_criado(cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_INSPECAO}": "SIM (municipal)"}))
    with app.app_context():
        db = get_db()
        codigo = db.execute("SELECT codigo_ibge FROM municipio WHERE nome = ?", (comprador_em.split("/")[0],)).fetchone()[0]
        with db:
            db.execute("UPDATE usuario SET municipio_id = ? WHERE id = ?", (codigo, comprador_id))
    resposta = propor(comprador, produto_id)
    assert (resposta.status_code == 302) == permitido
    if not permitido:
        assert "inspeção municipal (SIM) e só pode ser vendido dentro de Uberaba/MG" in resposta.get_data(as_text=True)


def test_numero_invalido_no_atributo(pessoas):
    _, vendedor = pessoas["vendedor"]
    resposta = cadastrar_produto(vendedor, titulo="Novilhas nelore", categoria_id=BOVINOS, unidade_id=6, quantidade="20",
                        **{f"atributo-{ATRIBUTO_IDADE}": "doze"})
    assert "Use só números" in resposta.get_data(as_text=True)


def test_atributos_de_outra_categoria_sao_ignorados(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    # "Raça" é de Pecuária. Num produto de queijo, o campo enviado é descartado.
    produto_id = id_criado(cadastrar_produto(vendedor, **{f"atributo-{ATRIBUTO_RACA}": "Nelore"}))
    with app.app_context():
        salvos = {linha[0] for linha in get_db().execute(
            "SELECT atributo_id FROM produto_atributo WHERE produto_id = ?", (produto_id,))}
    assert salvos == {ATRIBUTO_INSPECAO, ATRIBUTO_REGISTRO}


def test_subcategoria_herda_atributos_da_principal(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(
        vendedor, titulo="Novilhas nelore", categoria_id=BOVINOS, unidade_id=6, quantidade="20",
        **{f"atributo-{ATRIBUTO_RACA}": "Nelore", f"atributo-{ATRIBUTO_INSPECAO}": ""},
    ))
    assert consultar(app, "SELECT valor FROM produto_atributo WHERE produto_id = ?", produto_id)[0] == "Nelore"


def test_cadastrar_produto_exige_vitrine(app):
    sem_vitrine = criar_usuario(app, "Maria Sem Vitrine", "maria@exemplo.com")
    cliente = cliente_logado(app, sem_vitrine)
    resposta = cliente.get("/produtos/novo")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].startswith("/minha-vitrine?next=")


# ---------- busca e filtros (RF06) ----------

def test_busca_e_filtros(pessoas, client):
    _, vendedor = pessoas["vendedor"]
    cadastrar_produto(vendedor)
    cadastrar_produto(vendedor, titulo="Ovos caipira", categoria_id=OVOS, unidade_id=UNIDADE_DZ, preco_consumidor="2.500,00")
    cadastrar_produto(vendedor, titulo="Milho em grão", categoria_id=GRAOS, unidade_id=UNIDADE_SC60, preco_consumidor="70,00",
             quantidade="500", municipio="Goiânia/GO")

    def pagina(consulta):
        return client.get("/produtos" + consulta).get_data(as_text=True)

    assert "Mostrando 1–3 de 3 produtos" in pagina("")
    assert "Ovos caipira" in pagina(f"?categoria={OVOS}") and "Queijo minas" not in pagina(f"?categoria={OVOS}")
    assert "Milho" in pagina("?uf=GO") and "Queijo minas" not in pagina("?uf=GO")
    faixa = pagina("?preco_min=1.000&preco_max=2.000")
    assert "Queijo minas" in faixa and "Ovos caipira" not in faixa and "Milho" not in faixa
    menor = pagina("?ordem=menor_preco")
    assert menor.index("Milho em") < menor.index("Queijo minas") < menor.index("Ovos caipira")
    assert "Nenhum produto com esses filtros" in pagina("?q=mandioca")
    assert "Milho" in pagina("?q=GRAO")  # sem diferenciar acento e maiúsculas


def test_preco_invalido_no_filtro_e_ignorado(pessoas, client):
    _, vendedor = pessoas["vendedor"]
    cadastrar_produto(vendedor)
    assert "Queijo minas" in client.get("/produtos?preco_min=abc").get_data(as_text=True)


# ---------- situação do produto (RF16) ----------

def test_pausar_reativar_e_encerrar(app, pessoas, client):
    _, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    propor(comprador, produto_id)
    pagina = f"/produtos/{produto_id}"

    postar(vendedor, f"/produtos/{produto_id}/pausar", pagina)
    assert consultar(app, "SELECT status FROM produto")[0] == "pausado"
    assert consultar(app, "SELECT status FROM proposta")[0] == "nao_selecionada"
    assert "Queijo minas" not in client.get("/produtos").get_data(as_text=True)

    postar(vendedor, f"/produtos/{produto_id}/reativar", pagina)
    assert consultar(app, "SELECT status FROM produto")[0] == "ativo"
    postar(vendedor, f"/produtos/{produto_id}/encerrar", pagina)
    assert consultar(app, "SELECT status FROM produto")[0] == "encerrado"
    assert vendedor.get(f"/produtos/{produto_id}/editar").status_code == 302  # encerrado não se edita


def test_editar_remove_e_adiciona_fotos(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor, fotos=[("a.jpg", jpeg(400, 300)), ("b.jpg", jpeg(400, 300))]))
    removida = consultar(app, "SELECT id, arquivo FROM foto_produto ORDER BY id LIMIT 1")
    url = f"/produtos/{produto_id}/editar"
    dados = {
        "csrf_token": token_csrf(vendedor, url), "titulo": "Queijo minas curado", "categoria_id": QUEIJOS,
        "descricao": "", "para_consumidor": "y", "preco_consumidor": "1.200,00", "unidade_id": UNIDADE_KG, "quantidade": "1",
        "disponibilidade": "ano_todo",
        "municipio": "Uberaba/MG", f"atributo-{ATRIBUTO_INSPECAO}": "SIF (federal)", "remover_foto": str(removida["id"]),
        "fotos": [(BytesIO(png()), "nova.png")],
    }
    assert vendedor.post(url, data=dados, content_type="multipart/form-data").status_code == 302
    assert consultar(app, "SELECT COUNT(*) FROM foto_produto")[0] == 2
    assert removida["arquivo"] not in arquivos_na_pasta(app)  # arquivo apagado do disco
    assert len(arquivos_na_pasta(app)) == 2
    assert consultar(app, "SELECT preco_consumidor_centavos FROM produto")[0] == 120_000


# ---------- propostas de compra (RF18) ----------

def test_proposta_de_compra_e_aceite(app, pessoas):
    vendedor_id, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    _, outro = pessoas["outro"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    pagina = f"/produtos/{produto_id}"

    assert propor(comprador, produto_id).status_code == 302
    propor(outro, produto_id, preco="980,00")
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ?", vendedor_id)[0] == "nova_proposta"
    tela_vendedor = vendedor.get(pagina).get_data(as_text=True)
    assert "Propostas de compra (2)" in tela_vendedor
    assert "Lúcia" in tela_vendedor and "Martins" not in tela_vendedor

    proposta_id = consultar(app, "SELECT id FROM proposta WHERE preco_unitario_centavos = 100000")[0]
    postar(vendedor, f"/produtos/propostas/{proposta_id}/aceitar", pagina)
    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", proposta_id)[0] == "aceita"
    assert consultar(app, "SELECT status FROM produto")[0] == "ativo"  # pode continuar vendendo
    assert consultar(app, "SELECT COUNT(*) FROM proposta WHERE status = 'pendente'")[0] == 1

    assert "lucia@exemplo.com" in vendedor.get(pagina).get_data(as_text=True)
    assert "jose@exemplo.com" in comprador.get(pagina).get_data(as_text=True)
    tela_outro = outro.get(pagina).get_data(as_text=True)
    assert "jose@exemplo.com" not in tela_outro and "Pereira" not in tela_outro


@pytest.mark.parametrize("mudanca, mensagem", [
    ({"quantidade": "200"}, "maior que a quantidade disponível"),
    ({"prazo_entrega": (date.today() - timedelta(days=1)).isoformat()}, "já passou"),
    ({"preco": "-5"}, "maior que zero"),
])
def test_regras_da_proposta_de_compra(app, pessoas, mudanca, mensagem):
    _, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    assert mensagem in propor(comprador, produto_id, **mudanca).get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


def test_vendedor_nao_propoe_no_proprio_produto(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    assert vendedor.get(f"/produtos/{produto_id}/proposta").status_code == 302
    assert consultar(app, "SELECT COUNT(*) FROM proposta")[0] == 0


def test_recusar_e_retirar(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    pagina = f"/produtos/{produto_id}"
    propor(comprador, produto_id)
    proposta_id = consultar(app, "SELECT id FROM proposta")[0]
    postar(vendedor, f"/produtos/propostas/{proposta_id}/recusar", pagina)
    assert consultar(app, "SELECT status FROM proposta")[0] == "recusada"

    propor(comprador, produto_id)  # nova proposta depois da recusa
    nova_id = consultar(app, "SELECT id FROM proposta WHERE status = 'pendente'")[0]
    postar(comprador, f"/produtos/propostas/{nova_id}/retirar", pagina)
    assert consultar(app, "SELECT status FROM proposta WHERE id = ?", nova_id)[0] == "retirada"


# ---------- controle de acesso ----------

def test_controle_de_acesso_em_produtos(app, pessoas):
    _, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    _, outro = pessoas["outro"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    pagina = f"/produtos/{produto_id}"
    propor(comprador, produto_id)
    proposta_id = consultar(app, "SELECT id FROM proposta")[0]

    assert postar(comprador, f"/produtos/propostas/{proposta_id}/aceitar", pagina).status_code == 404
    assert postar(outro, f"/produtos/propostas/{proposta_id}/recusar", pagina).status_code == 404
    assert postar(outro, f"/produtos/propostas/{proposta_id}/retirar", pagina).status_code == 404
    assert postar(vendedor, f"/produtos/propostas/{proposta_id}/retirar", pagina).status_code == 404
    assert postar(outro, f"/produtos/{produto_id}/encerrar", pagina).status_code == 403
    assert outro.get(f"/produtos/{produto_id}/editar").status_code == 403
    # Proposta de encomenda e de produto não se misturam nas rotas.
    assert postar(vendedor, f"/propostas/{proposta_id}/aceitar", "/encomendas").status_code == 404
    assert consultar(app, "SELECT status FROM proposta")[0] == "pendente"


def test_produto_oculto_e_suas_fotos_somem(app, pessoas, client):
    _, vendedor = pessoas["vendedor"]
    produto_id = id_criado(cadastrar_produto(vendedor, fotos=[("a.jpg", jpeg(400, 300))]))
    nome = arquivos_na_pasta(app)[0]
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE produto SET status = 'oculto'")
    assert client.get(f"/produtos/{produto_id}").status_code == 404
    assert client.get(f"/fotos/{nome}").status_code == 404
    assert vendedor.get(f"/fotos/{nome}").status_code == 200  # o dono ainda vê


@pytest.mark.parametrize("nome", ["../app/schema.sql", "x.jpg", "abc.png", "0" * 32 + ".jpg"])
def test_nomes_de_foto_invalidos(client, nome):
    assert client.get(f"/fotos/{nome}").status_code == 404


# ---------- painel e página inicial ----------

def test_painel_e_inicio_mostram_produtos(pessoas, client):
    _, vendedor = pessoas["vendedor"]
    _, comprador = pessoas["comprador"]
    produto_id = id_criado(cadastrar_produto(vendedor))
    propor(comprador, produto_id)
    painel_vendedor = vendedor.get("/painel").get_data(as_text=True)
    assert "Queijo minas artesanal" in painel_vendedor and "1 proposta de compra para responder" in painel_vendedor
    assert "Pedido de compra" in comprador.get("/painel").get_data(as_text=True)
    assert "Produtos recentes" in client.get("/").get_data(as_text=True)
