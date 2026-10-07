"""Iteração 3: vitrine do produtor, perfil de comércio, diretórios e dados da conta (RF02, RF26, RF27)."""
import os
from io import BytesIO

import pytest
from PIL import Image

from app.db import get_db

from .conftest import (
    SACRAMENTO, UBERABA, cadastrar, cliente_logado, criar_comercio, criar_produtor, criar_usuario, token_csrf,
)
from .test_produtos import cadastrar_produto, id_criado, jpeg

HORTALICAS, QUEIJOS, PRODUTOS_ORIGEM_ANIMAL, OVOS = 12, 31, 3, 32


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


@pytest.fixture
def pessoas(app):
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    lojista = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    consumidor = criar_usuario(app, "Marina Costa", "marina@exemplo.com")
    return {
        "produtora": (produtora, cliente_logado(app, produtora)),
        "lojista": (lojista, cliente_logado(app, lojista)),
        "consumidor": (consumidor, cliente_logado(app, consumidor)),
    }


def salvar_vitrine(cliente, foto=None, **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/minha-vitrine"),
        "nome_vitrine": "Sítio Boa Vista",
        "descricao": "Hortaliças de produção familiar.",
        "municipio": "Uberaba/MG",
        "vende_retirada": "y",
        "vende_feira": "y",
        "onde_encontrar": "Feira do Produtor, sábados das 6h às 11h",
        "organico": "nao",
        "organico_registro": "",
        "telefone": "",
    }
    dados.update(mudancas)
    dados = {chave: valor for chave, valor in dados.items() if valor is not None}
    if foto:
        dados["foto"] = (BytesIO(foto), "logo.jpg")
    return cliente.post("/minha-vitrine", data=dados, content_type="multipart/form-data")


def salvar_loja(cliente, interesses=(HORTALICAS,), **mudancas):
    dados = {
        "csrf_token": token_csrf(cliente, "/minha-loja"),
        "nome_fantasia": "Mercado Bom Preço",
        "cnpj": "12.ABC.345/01DE-35",
        "tipo": "mercado",
        "municipio": "Uberaba/MG",
        "descricao": "",
        "volume_compra": "300 maços por semana",
        "telefone": "",
        "interesse": [str(i) for i in interesses],
    }
    dados.update(mudancas)
    return cliente.post("/minha-loja", data=dados)


# ---------- vitrine do produtor (RF26) ----------

def test_criar_vitrine_e_ver_pagina_publica(app, pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    resposta = salvar_vitrine(produtora)
    assert resposta.status_code == 302
    assert resposta.headers["Location"] == f"/produtores/{produtora_id}"
    perfil = consultar(app, "SELECT * FROM perfil_produtor WHERE usuario_id = ?", produtora_id)
    assert perfil["nome_busca"] == "sitio boa vista"
    assert (perfil["vende_retirada"], perfil["vende_feira"], perfil["vende_entrega"]) == (1, 1, 0)
    pagina = client.get(f"/produtores/{produtora_id}").get_data(as_text=True)
    assert "Sítio Boa Vista" in pagina and "Uberaba/MG" in pagina
    assert "Feira do Produtor, sábados" in pagina
    assert "Mandar mensagem" in pagina and "wa.me" not in pagina  # sem telefone público, contato pela plataforma


@pytest.mark.parametrize("mudancas, mensagem", [
    ({"vende_retirada": None, "vende_feira": None}, "Escolha pelo menos uma forma de venda."),
    ({"onde_encontrar": ""}, "Diga onde e quando fica a feira"),
    ({"organico": "certificado"}, "Informe a certificadora ou a OCS"),
    ({"telefone": "9999"}, "Informe o telefone com DDD"),
    ({"municipio": "Cidade Inventada/MG"}, "Escolha um município da lista"),
    ({"nome_vitrine": "AB"}, "Use entre 3 e 80 caracteres."),
], ids=["sem-forma", "feira-sem-local", "organico-sem-registro", "telefone", "municipio", "nome-curto"])
def test_validacoes_da_vitrine(app, pessoas, mudancas, mensagem):
    produtora_id, produtora = pessoas["produtora"]
    resposta = salvar_vitrine(produtora, **mudancas)
    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM perfil_produtor")[0] == 0


def test_telefone_publico_e_whatsapp_so_quando_o_produtor_quer(app, pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    salvar_vitrine(produtora, telefone="(34) 99876-5432", whatsapp="y")
    assert consultar(app, "SELECT telefone_publico FROM perfil_produtor")[0] == "34998765432"
    pagina = client.get(f"/produtores/{produtora_id}").get_data(as_text=True)
    assert "(34) 99876-5432" in pagina and "https://wa.me/5534998765432" in pagina

    salvar_vitrine(produtora, telefone="", whatsapp="y")  # apagar o telefone tira também o WhatsApp
    perfil = consultar(app, "SELECT telefone_publico, telefone_whatsapp FROM perfil_produtor")
    assert tuple(perfil) == (None, 0)
    assert "wa.me" not in client.get(f"/produtores/{produtora_id}").get_data(as_text=True)


def test_organico_declarado_aparece_com_registro(pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    salvar_vitrine(produtora, organico="ocs", organico_registro="OCS Vale Verde")
    assert "OCS Vale Verde" in client.get(f"/produtores/{produtora_id}").get_data(as_text=True)


def test_foto_da_vitrine_sem_exif_e_troca_apaga_a_antiga(app, pessoas, client):
    _, produtora = pessoas["produtora"]
    salvar_vitrine(produtora, foto=jpeg(800, 600))
    primeira = consultar(app, "SELECT foto FROM perfil_produtor")[0]
    caminho = os.path.join(app.config["PASTA_FOTOS"], primeira)
    with Image.open(caminho) as salva:
        assert dict(salva.getexif()) == {}
    assert client.get(f"/fotos/{primeira}").status_code == 200

    salvar_vitrine(produtora, foto=jpeg(400, 300))
    segunda = consultar(app, "SELECT foto FROM perfil_produtor")[0]
    assert segunda != primeira and not os.path.exists(caminho)

    salvar_vitrine(produtora, remover_foto="1")
    assert consultar(app, "SELECT foto FROM perfil_produtor")[0] is None
    assert client.get(f"/fotos/{segunda}").status_code == 404


def test_vitrine_mostra_os_produtos_ativos(app, pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    salvar_vitrine(produtora)
    produto_id = id_criado(cadastrar_produto(produtora))
    pagina = client.get(f"/produtores/{produtora_id}").get_data(as_text=True)
    assert "Queijo minas artesanal" in pagina and "Queijos e laticínios" in pagina
    detalhe = client.get(f"/produtos/{produto_id}").get_data(as_text=True)
    assert f'href="/produtores/{produtora_id}"' in detalhe  # o produto leva à vitrine


def test_vitrine_oculta_some_para_os_outros(app, pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    criar_produtor(app, produtora_id)
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE perfil_produtor SET status = 'oculto'")
    assert client.get(f"/produtores/{produtora_id}").status_code == 404
    assert produtora.get(f"/produtores/{produtora_id}").status_code == 200
    assert "Sítio Teste" not in client.get("/produtores").get_data(as_text=True)


def test_produtora_cria_vitrine_e_volta_para_cadastrar_produto(pessoas):
    _, produtora = pessoas["produtora"]
    url = "/minha-vitrine?next=/produtos/novo"
    dados = {
        "csrf_token": token_csrf(produtora, url), "nome_vitrine": "Sítio Boa Vista", "municipio": "Uberaba/MG",
        "vende_retirada": "y", "organico": "nao",
    }
    resposta = produtora.post(url, data=dados)
    assert resposta.headers["Location"] == "/produtos/novo"


# ---------- perfil de comércio (RF27) ----------

def test_cadastrar_loja_com_cnpj_alfanumerico(app, pessoas):
    lojista_id, lojista = pessoas["lojista"]
    resposta = salvar_loja(lojista, interesses=(HORTALICAS, OVOS, 9999))
    assert resposta.status_code == 302
    loja = consultar(app, "SELECT * FROM perfil_comercio WHERE usuario_id = ?", lojista_id)
    assert loja["cnpj"] == "12ABC34501DE35" and loja["tipo"] == "mercado"
    assert loja["verificado_em"] is None
    interesses = {linha[0] for linha in get_db_all(app, "SELECT categoria_id FROM comercio_interesse")}
    assert interesses == {HORTALICAS, OVOS}  # a categoria inexistente foi ignorada


def get_db_all(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


@pytest.mark.parametrize("mudancas, mensagem", [
    ({"cnpj": "12.ABC.345/01DE-36"}, "CNPJ inválido"),
    ({"cnpj": ""}, "Informe o CNPJ."),
    ({"tipo": ""}, "Escolha o tipo de comércio."),
    ({"tipo": "boate"}, "Escolha inválida"),
], ids=["dv-errado", "sem-cnpj", "sem-tipo", "tipo-inexistente"])
def test_validacoes_da_loja(app, pessoas, mudancas, mensagem):
    _, lojista = pessoas["lojista"]
    resposta = salvar_loja(lojista, **mudancas)
    assert mensagem in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM perfil_comercio")[0] == 0


def test_cnpj_repetido_em_outra_conta(app, pessoas):
    lojista_id, lojista = pessoas["lojista"]
    _, outro = pessoas["consumidor"]
    salvar_loja(lojista)
    resposta = salvar_loja(outro, cnpj="12ABC34501DE35", nome_fantasia="Outro Mercado")
    assert "Este CNPJ já está cadastrado em outra conta" in resposta.get_data(as_text=True)
    assert consultar(app, "SELECT COUNT(*) FROM perfil_comercio")[0] == 1


def test_trocar_cnpj_tira_o_selo_de_verificado(app, pessoas):
    lojista_id, lojista = pessoas["lojista"]
    salvar_loja(lojista)
    resultado = app.test_cli_runner().invoke(args=["verificar-comercio", str(lojista_id)])
    assert "verificada" in resultado.output
    salvar_loja(lojista, volume_compra="400 maços por semana")  # mesmo CNPJ: continua verificada
    assert consultar(app, "SELECT verificado_em FROM perfil_comercio")[0] is not None
    salvar_loja(lojista, cnpj="11.222.333/0001-81")
    assert consultar(app, "SELECT verificado_em FROM perfil_comercio")[0] is None


def test_comando_verificar_comercio_sem_loja(app, pessoas):
    consumidor_id, _ = pessoas["consumidor"]
    resultado = app.test_cli_runner().invoke(args=["verificar-comercio", str(consumidor_id)])
    assert resultado.exit_code != 0 and "não tem perfil de comércio" in resultado.output


def test_pagina_da_loja_so_para_produtores(app, pessoas, client):
    lojista_id, lojista = pessoas["lojista"]
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    criar_comercio(app, lojista_id, cnpj="12ABC34501DE35", telefone_publico="3433330000")
    criar_produtor(app, produtora_id)
    url = f"/comercios/{lojista_id}"

    assert client.get(url).status_code == 302  # visitante vai para o login
    negado = consumidor.get(url)
    assert negado.status_code == 403 and "Área para produtores" in negado.get_data(as_text=True)
    assert "3333-0000" not in negado.get_data(as_text=True)
    pagina = produtora.get(url).get_data(as_text=True)
    assert "12.ABC.345/01DE-35" in pagina and "(34) 3333-0000" in pagina
    assert lojista.get(url).status_code == 200  # a própria loja
    assert produtora.get("/comercios/9999").status_code == 404


def test_diretorio_de_comercios_e_filtros(app, pessoas):
    lojista_id, _ = pessoas["lojista"]
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    outro = criar_usuario(app, "Paulo Lima", "paulo@exemplo.com")
    criar_comercio(app, lojista_id, nome="Mercado Bom Preço", interesses=[HORTALICAS])
    criar_comercio(app, outro, nome="Restaurante Sabor da Roça", cnpj="12ABC34501DE35", tipo="restaurante",
                   municipio_id=SACRAMENTO, interesses=[PRODUTOS_ORIGEM_ANIMAL])
    criar_produtor(app, produtora_id)

    assert consumidor.get("/comercios").status_code == 403

    def pagina(consulta=""):
        return produtora.get("/comercios" + consulta).get_data(as_text=True)

    tudo = pagina()
    assert "Mercado Bom Preço" in tudo and "Restaurante Sabor da Roça" in tudo
    assert "Sabor da Roça" not in pagina("?tipo=mercado")
    # Interesse na categoria principal vale para a subcategoria (queijos) e vice-versa.
    assert "Restaurante Sabor da Roça" in pagina(f"?categoria={QUEIJOS}")
    assert "Mercado Bom Preço" not in pagina(f"?categoria={QUEIJOS}")
    assert "Mercado Bom Preço" in pagina(f"?categoria=1")  # hortaliças é subcategoria da produção agrícola
    assert "Bom Preço" not in pagina("?q=sabor roca") and "Sabor da Roça" in pagina("?q=sabor roca")


def test_link_de_comercios_so_no_menu_de_produtores(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    criar_produtor(app, produtora_id)
    assert 'href="/comercios"' in produtora.get("/").get_data(as_text=True)
    assert 'href="/comercios"' not in consumidor.get("/").get_data(as_text=True)


# ---------- diretório de produtores ----------

def test_diretorio_de_produtores_busca_por_produto_e_categoria(app, pessoas, client):
    produtora_id, produtora = pessoas["produtora"]
    outro = criar_usuario(app, "Carlos Mendes", "carlos@exemplo.com")
    salvar_vitrine(produtora)
    criar_produtor(app, outro, "Fazenda Santa Clara", municipio_id=SACRAMENTO)
    cadastrar_produto(produtora)  # queijo

    def pagina(consulta=""):
        return client.get("/produtores" + consulta).get_data(as_text=True)

    assert "Sítio Boa Vista" in pagina() and "Fazenda Santa Clara" in pagina()
    assert "1 produto à venda" in pagina()
    so_queijo = pagina("?q=queijo")
    assert "Sítio Boa Vista" in so_queijo and "Fazenda Santa Clara" not in so_queijo
    por_categoria = pagina(f"?categoria={PRODUTOS_ORIGEM_ANIMAL}")
    assert "Sítio Boa Vista" in por_categoria and "Fazenda Santa Clara" not in por_categoria


# ---------- cadastro e conta ----------

@pytest.mark.parametrize("usos, destino", [
    (["vender", "comercio"], "/minha-vitrine?next=/minha-loja"),
    (["vender"], "/minha-vitrine"),
    (["comercio"], "/minha-loja"),
    (["consumo"], "/produtores"),
    ([], "/painel"),
], ids=["os-dois", "vender", "comercio", "consumo", "nenhum"])
def test_cadastro_leva_ao_proximo_passo(client, usos, destino):
    resposta = cadastrar(client, usos=usos)
    assert resposta.status_code == 302
    assert resposta.headers["Location"] == destino


def test_cadastro_ja_marca_o_uso_vindo_da_pagina_inicial(client):
    html = client.get("/cadastro?uso=comercio").get_data(as_text=True)
    assert '<input checked id="usos-1" name="usos" type="checkbox" value="comercio">' in html
    assert '<input id="usos-0" name="usos" type="checkbox" value="vender">' in html


def test_editar_dados_da_conta(app, pessoas):
    consumidor_id, consumidor = pessoas["consumidor"]
    resposta = consumidor.post("/minha-conta", data={
        "csrf_token": token_csrf(consumidor, "/minha-conta"), "nome": "Marina Costa Lima",
        "tipo_pessoa": "PF", "municipio": "Sacramento/MG",
    })
    assert resposta.status_code == 302
    linha = consultar(app, "SELECT nome, municipio_id FROM usuario WHERE id = ?", consumidor_id)
    assert tuple(linha) == ("Marina Costa Lima", SACRAMENTO)


def test_painel_mostra_vitrine_e_loja(app, pessoas):
    produtora_id, produtora = pessoas["produtora"]
    _, consumidor = pessoas["consumidor"]
    criar_produtor(app, produtora_id, "Sítio Boa Vista")
    criar_comercio(app, produtora_id, nome="Empório da Ana")  # a mesma conta pode ter os dois perfis
    painel = produtora.get("/painel").get_data(as_text=True)
    assert "Sítio Boa Vista" in painel and "Empório da Ana" in painel
    vazio = consumidor.get("/painel").get_data(as_text=True)
    assert "Criar vitrine" in vazio and "Cadastrar loja" in vazio


def test_rotas_de_perfil_exigem_login(client):
    for url in ("/minha-vitrine", "/minha-loja", "/minha-conta", "/comercios"):
        resposta = client.get(url)
        assert resposta.status_code == 302 and "/entrar" in resposta.headers["Location"]
