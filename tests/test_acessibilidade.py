"""Iteração 7: revisão de acessibilidade automatizada (RNF08, WCAG 2.2 AA).

Abre as páginas do sistema com os dados de demonstração, como visitante, produtora, loja e administração,
e confere o que dá para conferir no HTML:
- idioma da página e título (3.1.1, 2.4.2);
- um único h1 por página e ids sem repetição (1.3.1, 4.1.1);
- todo campo de formulário com rótulo (1.3.1, 3.3.2, 4.1.2);
- toda imagem com texto alternativo (1.1.1) e todo link e botão com nome (2.4.4, 4.1.2).
E calcula o contraste das cores do CSS (1.4.3: pelo menos 4,5:1 para texto).
"""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.db import get_db

from .conftest import cliente_logado

VAZIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Auditoria(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problemas, self.ids, self.h1, self.lang, self.titulo = [], [], 0, None, ""
        self.pilha = []          # elementos abertos (tag, atributos)
        self.rotulos_para = set()
        self.campos = []         # (id, tem_rotulo_em_volta, atributos)
        self.nomeaveis = []      # links e botões abertos: [tag, atributos, texto]
        self.no_titulo = False

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "html":
            self.lang = atributos.get("lang")
        if "id" in atributos:
            self.ids.append(atributos["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.no_titulo = True
        if tag == "label" and atributos.get("for"):
            self.rotulos_para.add(atributos["for"])
        if tag == "img" and "alt" not in atributos:
            self.problemas.append(f"imagem sem alt: {atributos.get('src')}")
        if tag in ("input", "select", "textarea"):
            tipo = atributos.get("type", "text")
            if tipo not in ("hidden", "submit", "button", "reset"):
                dentro_de_label = any(t == "label" for t, _ in self.pilha)
                self.campos.append((atributos.get("id"), dentro_de_label, atributos))
        if tag in ("a", "button"):
            self.nomeaveis.append([tag, atributos, ""])
        for aberto in self.nomeaveis:
            if tag == "img" and atributos.get("alt"):
                aberto[2] += atributos["alt"]
        if tag not in VAZIOS:
            self.pilha.append((tag, atributos))

    def handle_endtag(self, tag):
        if tag == "title":
            self.no_titulo = False
        if tag in ("a", "button") and self.nomeaveis:
            aberto = self.nomeaveis.pop()
            nome = aberto[2].strip() or aberto[1].get("aria-label", "")
            if not nome and aberto[1].get("aria-hidden") != "true" and aberto[1].get("tabindex") != "-1":
                self.problemas.append(f"{tag} sem nome: {aberto[1]}")
        for posicao in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[posicao][0] == tag:
                del self.pilha[posicao:]
                break

    def handle_data(self, texto):
        if self.no_titulo:
            self.titulo += texto
        for aberto in self.nomeaveis:
            aberto[2] += texto

    def concluir(self):
        if self.lang != "pt-BR":
            self.problemas.append(f"idioma da página: {self.lang}")
        if not self.titulo.strip():
            self.problemas.append("página sem título")
        if self.h1 != 1:
            self.problemas.append(f"{self.h1} títulos h1 (o certo é 1)")
        repetidos = {i for i in self.ids if self.ids.count(i) > 1}
        if repetidos:
            self.problemas.append(f"ids repetidos: {sorted(repetidos)}")
        for campo_id, dentro_de_label, atributos in self.campos:
            if not (dentro_de_label or (campo_id and campo_id in self.rotulos_para)
                    or atributos.get("aria-label") or atributos.get("aria-labelledby")):
                self.problemas.append(f"campo sem rótulo: {atributos.get('name')}")
        return self.problemas


def auditar(html):
    auditoria = Auditoria()
    auditoria.feed(html)
    return auditoria.concluir()


@pytest.fixture
def demo(app):
    app.test_cli_runner().invoke(args=["carregar-demo"])
    with app.app_context():
        ids = {linha["email"].split(".")[0]: linha["id"] for linha in get_db().execute("SELECT id, email FROM usuario")}
    return {apelido: cliente_logado(app, usuario_id) for apelido, usuario_id in ids.items()} | {"ids": ids}


PAGINAS = {
    "visitante": ["/", "/entrar", "/cadastro", "/esqueci-a-senha", "/termos", "/privacidade", "/produtos",
                  "/produtos?q=alface&regiao=1", "/produtores", "/encomendas", "/produtos/1", "/produtores/{ana}",
                  "/encomendas/1"],
    "ana": ["/painel", "/minha-vitrine", "/produtos/novo", "/produtos/1/editar", "/minha-conta", "/minha-conta/excluir",
            "/mensagens", "/mensagens/1", "/avisos", "/contratos", "/contratos/1", "/contratos/1/imprimir",
            "/contratos/novo?loja={paulo}", "/comercios", "/comercios/{rita}", "/encomendas/nova",
            "/denunciar?alvo=loja&id={paulo}"],
    "rita": ["/minha-loja", "/produtos", "/produtos/6", "/produtos/6/proposta", "/contratos/novo?produto=2"],
    "admin": ["/admin", "/admin/lojas", "/admin/denuncias", "/admin/denuncias/1", "/admin/usuarios",
              "/admin/categorias", "/admin/registro"],
}


@pytest.mark.parametrize("quem", list(PAGINAS))
def test_paginas_sem_problemas_de_acessibilidade(app, demo, quem):
    cliente = app.test_client() if quem == "visitante" else demo[quem]
    falhas = {}
    for modelo in PAGINAS[quem]:
        url = modelo.format(**demo["ids"])
        resposta = cliente.get(url)
        assert resposta.status_code == 200, url
        problemas = auditar(resposta.get_data(as_text=True))
        if problemas:
            falhas[url] = problemas
    assert falhas == {}


def test_auditoria_acusa_problemas():
    """Prova de que a auditoria funciona: um HTML ruim precisa ser acusado."""
    ruim = '<html lang="en"><title></title><h1>A</h1><h1>B</h1><img src="x.jpg"><input name="q"><a href="/"></a>' \
           '<p id="a"></p><p id="a"></p></html>'
    problemas = " | ".join(auditar(ruim))
    for esperado in ("idioma", "sem título", "2 títulos h1", "imagem sem alt", "campo sem rótulo", "a sem nome",
                     "ids repetidos"):
        assert esperado in problemas


# ---------- contraste (WCAG 2.2, critério 1.4.3) ----------

def _variaveis():
    css = (Path(__file__).parent.parent / "app" / "static" / "css" / "estilo.css").read_text(encoding="utf-8")
    raiz = css[css.index(":root {"):css.index("}", css.index(":root {"))]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", raiz))


def _luminancia(cor):
    canais = [int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lineares = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lineares[0] + 0.7152 * lineares[1] + 0.0722 * lineares[2]


def contraste(cor_a, cor_b):
    claro, escuro = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


# Combinações de texto e fundo usadas no CSS.
PARES = [
    ("texto", "fundo"), ("texto", "superficie"), ("texto-suave", "fundo"), ("texto-suave", "superficie"),
    ("texto-suave", "verde-claro"), ("verde", "superficie"), ("verde", "fundo"), ("verde-escuro", "verde-claro"),
    ("#ffffff", "verde"), ("#ffffff", "verde-escuro"), ("terra", "superficie"), ("terra", "terra-claro"),
    ("texto", "terra-claro"), ("azul", "azul-claro"), ("azul", "superficie"), ("erro", "superficie"),
    ("erro", "erro-fundo"), ("#ffffff", "erro"), ("#7c2d12", "#fff1e6"), ("#eef7ef", "verde-escuro"),
]


@pytest.mark.parametrize("texto, fundo", PARES)
def test_contraste_de_texto(texto, fundo):
    cores = _variaveis()
    cor_texto, cor_fundo = cores.get(texto, texto), cores.get(fundo, fundo)
    assert contraste(cor_texto, cor_fundo) >= 4.5, f"{texto} sobre {fundo}: {contraste(cor_texto, cor_fundo):.2f}"


def test_calculo_de_contraste_confere_com_a_wcag():
    assert round(contraste("#000000", "#ffffff"), 1) == 21.0
    assert round(contraste("#767676", "#ffffff"), 1) == 4.5  # cinza no limite, exemplo clássico
