"""Campos específicos por categoria (RF05), definidos na tabela atributo_categoria.

Os atributos ficam na categoria principal (ex.: "Produtos de origem animal") e valem
para todas as subcategorias dela (ex.: "Queijos e laticínios").
"""
import json

from .util import hoje, ler_quantidade


def atributos_por_principal(db):
    grupos = {}
    for linha in db.execute(
        """SELECT a.id, a.categoria_id, a.nome, a.tipo, a.obrigatorio, a.opcoes, c.nome AS categoria_nome
             FROM atributo_categoria a JOIN categoria c ON c.id = a.categoria_id
            ORDER BY a.categoria_id, a.id"""
    ):
        atributo = dict(linha)
        atributo["lista_opcoes"] = json.loads(linha["opcoes"]) if linha["opcoes"] else []
        grupos.setdefault(linha["categoria_id"], []).append(atributo)
    return grupos


def categoria_principal(db, categoria_id):
    linha = db.execute("SELECT id, categoria_pai_id FROM categoria WHERE id = ?", (categoria_id,)).fetchone()
    if linha is None:
        return None
    return linha["categoria_pai_id"] or linha["id"]


def ler_atributos(db, categoria_id, formulario):
    """Lê os campos 'atributo-<id>' da categoria escolhida. Devolve (valores, erros).

    Campos de outras categorias são ignorados (o navegador pode enviá-los se o JavaScript estiver desligado).
    """
    principal = categoria_principal(db, categoria_id)
    valores, erros = {}, {}
    for atributo in atributos_por_principal(db).get(principal, []):
        texto = (formulario.get(f"atributo-{atributo['id']}") or "").strip()[:100]
        if not texto:
            if atributo["obrigatorio"]:
                erros[atributo["id"]] = f"Informe {atributo['nome'].lower()}."
            continue
        if atributo["tipo"] == "numero":
            try:
                if ler_quantidade(texto) < 0:
                    raise ValueError
            except ValueError:
                erros[atributo["id"]] = "Use só números, por exemplo 1200 ou 2,5."
                continue
        elif atributo["tipo"] == "ano":
            if not texto.isdigit() or not 1900 <= int(texto) <= hoje().year + 1:
                erros[atributo["id"]] = f"Informe um ano entre 1900 e {hoje().year + 1}."
                continue
        elif atributo["tipo"] == "lista" and texto not in atributo["lista_opcoes"]:
            erros[atributo["id"]] = "Escolha uma das opções."
            continue
        valores[atributo["id"]] = texto
    return valores, erros

