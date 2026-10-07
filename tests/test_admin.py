"""Iteração 7: denúncias (RF19), administração (RF15, RF20, RF25, RF38) e registro das ações (RNF12)."""
from datetime import date, timedelta

import pytest

from app import servicos
from app.db import get_db

from .conftest import cliente_logado, criar_comercio, criar_produtor, criar_usuario, token_csrf


def consultar(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchone()


def todas(app, sql, *parametros):
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


def postar(cliente, url, **dados):
    return cliente.post(url, data={"csrf_token": token_csrf(cliente, "/painel"), **dados})


@pytest.fixture
def cena(app):
    admin = criar_usuario(app, "Equipe", "admin@exemplo.com")
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE usuario SET papel = 'admin' WHERE id = ?", (admin,))
    produtora = criar_usuario(app, "Ana Ribeiro", "ana@exemplo.com")
    criar_produtor(app, produtora, "Sítio Boa Vista")
    loja = criar_usuario(app, "Rita Souza", "rita@exemplo.com")
    criar_comercio(app, loja, "Mercado Bom Preço")
    consumidor = criar_usuario(app, "Marina Costa", "marina@exemplo.com")
    with app.app_context():
        produto = servicos.criar_produto(get_db(), produtora, {
            "titulo": "Tomate italiano", "categoria_id": 12, "descricao": "", "unidade_id": 1,
            "quantidade_disponivel": None, "municipio_id": 3170107, "para_consumidor": True,
            "preco_consumidor_centavos": 790, "para_lojista": False, "preco_lojista_centavos": None,
            "pedido_minimo_lojista": None, "so_verificados": False, "disponibilidade": "ano_todo", "meses_safra": 0,
        }, {}, [])
    return {
        "admin_id": admin, "admin": cliente_logado(app, admin),
        "produtora_id": produtora, "produtora": cliente_logado(app, produtora),
        "loja_id": loja, "loja": cliente_logado(app, loja),
        "consumidor_id": consumidor, "consumidor": cliente_logado(app, consumidor),
        "produto": produto,
    }


# ---------- acesso ----------

@pytest.mark.parametrize("url", ["/admin", "/admin/lojas", "/admin/denuncias", "/admin/usuarios", "/admin/categorias",
                                 "/admin/registro"])
def test_area_de_administracao_so_para_admin(cena, client, url):
    assert client.get(url).status_code == 302  # visitante vai para o login
    assert cena["consumidor"].get(url).status_code == 403
    assert cena["admin"].get(url).status_code == 200


def test_acoes_administrativas_bloqueadas_para_quem_nao_e_admin(app, cena):
    resposta = postar(cena["loja"], f"/admin/lojas/{cena['loja_id']}/verificar", motivo="Eu mesma me verifico")
    assert resposta.status_code == 403
    assert consultar(app, "SELECT verificado_em FROM perfil_comercio")[0] is None


# ---------- lojas (RF38) ----------

def test_verificar_loja_exige_motivo_e_fica_registrado(app, cena):
    admin, loja_id = cena["admin"], cena["loja_id"]
    postar(admin, f"/admin/lojas/{loja_id}/verificar", motivo="")
    assert consultar(app, "SELECT verificado_em FROM perfil_comercio")[0] is None
    postar(admin, f"/admin/lojas/{loja_id}/verificar", motivo="CNPJ ativo conferido na Receita")
    assert consultar(app, "SELECT verificado_em IS NOT NULL FROM perfil_comercio")[0] == 1
    registro = consultar(app, "SELECT admin_id, acao, motivo FROM acao_moderacao")
    assert tuple(registro) == (cena["admin_id"], "verificar_loja", "CNPJ ativo conferido na Receita")
    assert "CNPJ ativo conferido na Receita" in admin.get("/admin/registro").get_data(as_text=True)
    assert consultar(app, "SELECT tipo FROM notificacao WHERE usuario_id = ?", loja_id)[0] == "conteudo_moderado"


# ---------- denúncias (RF19) ----------

def denunciar(cliente, alvo, alvo_id, motivo="falso", descricao="Preço diferente na feira"):
    return postar(cliente, "/denunciar", alvo=alvo, id=str(alvo_id), motivo=motivo, descricao=descricao)


def test_denunciar_produto_e_moderacao_oculta(app, cena, client):
    produto = cena["produto"]
    assert "Denunciar este produto" in cena["consumidor"].get(f"/produtos/{produto}").get_data(as_text=True)
    assert denunciar(cena["consumidor"], "produto", produto).status_code == 302
    assert "Você já denunciou isto" in cena["consumidor"].get(
        denunciar(cena["consumidor"], "produto", produto).headers["Location"]).get_data(as_text=True)
    denunciar(cena["loja"], "produto", produto, motivo="golpe")
    assert consultar(app, "SELECT COUNT(*) FROM denuncia WHERE status = 'aberta'")[0] == 2

    fila = cena["admin"].get("/admin/denuncias").get_data(as_text=True)
    assert "2 denúncias sobre o mesmo item" in fila
    denuncia = consultar(app, "SELECT id FROM denuncia ORDER BY id LIMIT 1")[0]
    detalhe = cena["admin"].get(f"/admin/denuncias/{denuncia}").get_data(as_text=True)
    assert "Tomate italiano" in detalhe and "Costa" not in detalhe  # só o primeiro nome de quem denunciou

    postar(cena["admin"], f"/admin/denuncias/{denuncia}", decisao="procedente", ocultar="1",
           motivo="Anúncio com informação enganosa")
    assert consultar(app, "SELECT status FROM produto")[0] == "oculto"
    assert consultar(app, "SELECT COUNT(*) FROM denuncia WHERE status = 'procedente'")[0] == 2  # as duas foram fechadas
    assert client.get(f"/produtos/{produto}").status_code == 404
    assert cena["produtora"].get(f"/produtos/{produto}").status_code == 200  # o dono ainda vê
    aviso = consultar(app, "SELECT texto FROM notificacao WHERE usuario_id = ? AND tipo = 'conteudo_moderado'",
                      cena["produtora_id"])[0]
    assert "Anúncio com informação enganosa" in aviso
    acoes = {linha[0] for linha in todas(app, "SELECT acao FROM acao_moderacao")}
    assert acoes == {"resolver_denuncia", "ocultar"}


def test_denuncia_improcedente_nao_muda_nada(app, cena):
    denunciar(cena["consumidor"], "produto", cena["produto"])
    denuncia = consultar(app, "SELECT id FROM denuncia")[0]
    postar(cena["admin"], f"/admin/denuncias/{denuncia}", decisao="improcedente", ocultar="1", motivo="Preço é do produtor")
    assert consultar(app, "SELECT status FROM produto")[0] == "ativo"
    assert consultar(app, "SELECT status FROM denuncia")[0] == "improcedente"


def test_nao_denuncia_o_proprio_conteudo_nem_alvo_invalido(app, cena):
    resposta = denunciar(cena["produtora"], "produto", cena["produto"])
    assert "Você não pode denunciar o seu próprio conteúdo" in cena["produtora"].get(
        resposta.headers["Location"]).get_data(as_text=True)
    assert cena["consumidor"].get("/denunciar?alvo=planeta&id=1").status_code == 404
    assert cena["consumidor"].get("/denunciar?alvo=produto&id=999").status_code == 404
    assert consultar(app, "SELECT COUNT(*) FROM denuncia")[0] == 0


def test_conversa_denunciada_so_por_participante_e_lida_pela_moderacao(app, cena):
    with app.app_context():
        db = get_db()
        remetente = db.execute("SELECT * FROM usuario WHERE id = ?", (cena["consumidor_id"],)).fetchone()
        remetente = {"id": remetente["id"], "nome": remetente["nome"], "tem_produtor": False}
        conversa = servicos.conversas.iniciar_conversa(db, "produto", cena["produto"], remetente, "Mensagem ofensiva de teste")
    assert cena["admin"].get(f"/admin/conversas/{conversa}").status_code == 404  # sem denúncia, a moderação não lê
    assert cena["loja"].get(f"/denunciar?alvo=conversa&id={conversa}").status_code == 404  # não participa
    denunciar(cena["produtora"], "conversa", conversa, motivo="ofensivo", descricao="")
    assert "Mensagem ofensiva de teste" in cena["admin"].get(f"/admin/conversas/{conversa}").get_data(as_text=True)

    denuncia = consultar(app, "SELECT id FROM denuncia")[0]
    postar(cena["admin"], f"/admin/denuncias/{denuncia}", decisao="procedente", bloquear="1", motivo="Ofensa grave")
    assert consultar(app, "SELECT status FROM usuario WHERE id = ?", cena["consumidor_id"])[0] == "bloqueado"
    assert consultar(app, "SELECT status FROM usuario WHERE id = ?", cena["produtora_id"])[0] == "ativo"  # quem denunciou, não


# ---------- usuários (RF25) ----------

def test_bloquear_tira_a_sessao_e_esconde_o_conteudo(app, cena, client):
    produtora_id = cena["produtora_id"]
    postar(cena["admin"], f"/admin/usuarios/{produtora_id}/bloquear", motivo="Golpe confirmado")
    assert cena["produtora"].get("/painel").status_code == 302  # a sessão caiu
    assert "Tomate italiano" not in client.get("/produtos").get_data(as_text=True)
    assert client.get(f"/produtos/{cena['produto']}").status_code == 404
    assert client.get(f"/produtores/{produtora_id}").status_code == 404
    assert "Sítio Boa Vista" not in client.get("/produtores").get_data(as_text=True)
    assert cena["admin"].get(f"/produtos/{cena['produto']}").status_code == 200  # a administração ainda vê

    postar(cena["admin"], f"/admin/usuarios/{produtora_id}/desbloquear", motivo="Recurso aceito")
    assert "Tomate italiano" in client.get("/produtos").get_data(as_text=True)
    acoes = [linha[0] for linha in todas(app, "SELECT acao FROM acao_moderacao ORDER BY id")]
    assert acoes == ["bloquear_usuario", "desbloquear_usuario"]


def test_encomenda_de_conta_bloqueada_some(app, cena, client):
    with app.app_context():
        encomenda = servicos.criar_encomenda(get_db(), cena["loja_id"], {
            "titulo": "Tomate toda semana", "categoria_id": 12, "descricao": "", "quantidade": 100, "unidade_id": 1,
            "municipio_id": 3170107, "prazo_limite": date.today() + timedelta(days=10), "transporte": "a_combinar",
            "condicoes_pagamento": "",
        })
    postar(cena["admin"], f"/admin/usuarios/{cena['loja_id']}/bloquear", motivo="Spam de encomendas")
    assert "Tomate toda semana" not in client.get("/encomendas").get_data(as_text=True)
    assert client.get(f"/encomendas/{encomenda}").status_code == 404


def test_admin_nao_bloqueia_admin(app, cena):
    postar(cena["admin"], f"/admin/usuarios/{cena['admin_id']}/bloquear", motivo="Teste")
    assert consultar(app, "SELECT status FROM usuario WHERE id = ?", cena["admin_id"])[0] == "ativo"


def test_busca_de_usuarios(cena):
    pagina = cena["admin"].get("/admin/usuarios?q=boa vista").get_data(as_text=True)
    assert "Ana Ribeiro" in pagina and "Marina Costa" not in pagina


# ---------- moderação direta ----------

def test_ocultar_e_reativar_produto_pela_pagina(app, cena):
    produto = cena["produto"]
    pagina = cena["admin"].get(f"/produtos/{produto}").get_data(as_text=True)
    assert "Moderação" in pagina
    assert "Moderação" not in cena["consumidor"].get(f"/produtos/{produto}").get_data(as_text=True)
    postar(cena["admin"], f"/admin/conteudo/produto/{produto}/ocultar", motivo="Produto proibido", voltar=f"/produtos/{produto}")
    assert consultar(app, "SELECT status FROM produto")[0] == "oculto"
    postar(cena["admin"], f"/admin/conteudo/produto/{produto}/reativar", motivo="Corrigido pelo produtor")
    assert consultar(app, "SELECT status FROM produto")[0] == "pausado"  # o dono decide quando reativar


def test_voltar_so_para_dentro_do_site(cena):
    resposta = postar(cena["admin"], f"/admin/conteudo/produto/{cena['produto']}/ocultar", motivo="Teste de retorno",
                      voltar="//exemplo.com/golpe")
    assert resposta.headers["Location"] == "/admin"


# ---------- categorias e unidades (RF20) ----------

def test_criar_e_desativar_categoria_e_criar_unidade(app, cena):
    admin = cena["admin"]
    postar(admin, "/admin/categorias", acao="categoria", pai_id="1", nome="Cogumelos")
    categoria = consultar(app, "SELECT id FROM categoria WHERE nome = 'Cogumelos'")[0]
    assert "Cogumelos" in cena["produtora"].get("/produtos/novo").get_data(as_text=True)
    postar(admin, "/admin/categorias", acao="desativar", categoria_id=str(categoria), motivo="Criada por engano")
    assert "Cogumelos" not in cena["produtora"].get("/produtos/novo").get_data(as_text=True)
    postar(admin, "/admin/categorias", acao="categoria", pai_id="1", nome="cogumelos")
    assert consultar(app, "SELECT COUNT(*) FROM categoria WHERE nome LIKE 'cogumelos'")[0] == 1  # repetida
    postar(admin, "/admin/categorias", acao="unidade", sigla="ton", nome="Tonelada métrica")
    assert consultar(app, "SELECT nome FROM unidade_medida WHERE sigla = 'ton'")[0] == "Tonelada métrica"
    assert len(todas(app, "SELECT * FROM acao_moderacao")) == 3


def test_comando_tornar_admin(app, cena):
    resultado = app.test_cli_runner().invoke(args=["tornar-admin", "marina@exemplo.com"])
    assert "administração" in resultado.output
    assert consultar(app, "SELECT papel FROM usuario WHERE id = ?", cena["consumidor_id"])[0] == "admin"
    erro = app.test_cli_runner().invoke(args=["tornar-admin", "ninguem@exemplo.com"])
    assert erro.exit_code != 0
