"""Avisos de oportunidade na região (RF37).

- Produto novo vendido a lojas: avisa as lojas da mesma região imediata que compram aquela categoria.
- Encomenda nova: avisa os produtores da mesma região imediata que vendem aquela categoria.

Rodam dentro da transação que cria o produto ou a encomenda.
"""
from .comum import notificar

LIMITE_DE_AVISOS = 500  # proteção simples para um cadastro não gerar avisos sem fim


def _categoria_e_principal(db, categoria_id):
    linha = db.execute("SELECT id, COALESCE(categoria_pai_id, id) AS principal FROM categoria WHERE id = ?",
                       (categoria_id,)).fetchone()
    return linha["id"], linha["principal"]


def _regiao(db, municipio_id):
    linha = db.execute("SELECT regiao_imediata_id FROM municipio WHERE codigo_ibge = ?", (municipio_id,)).fetchone()
    return linha["regiao_imediata_id"] if linha else None


def avisar_lojas_da_regiao(db, produto_id):
    produto = db.execute(
        """SELECT pd.id, pd.titulo, pd.categoria_id, pd.municipio_id, pd.vendedor_id, pd.para_lojista,
                  m.nome AS municipio_nome, m.uf, pp.nome_vitrine
             FROM produto pd JOIN municipio m ON m.codigo_ibge = pd.municipio_id
             LEFT JOIN perfil_produtor pp ON pp.usuario_id = pd.vendedor_id
            WHERE pd.id = ?""",
        (produto_id,),
    ).fetchone()
    regiao = _regiao(db, produto["municipio_id"])
    if not produto["para_lojista"] or regiao is None:
        return 0
    categoria, principal = _categoria_e_principal(db, produto["categoria_id"])
    lojas = db.execute(
        """SELECT pc.usuario_id FROM perfil_comercio pc
             JOIN municipio m ON m.codigo_ibge = pc.municipio_id
             JOIN usuario u   ON u.id = pc.usuario_id
            WHERE pc.status = 'ativo' AND u.status = 'ativo' AND pc.usuario_id <> ? AND m.regiao_imediata_id = ?
              AND EXISTS (SELECT 1 FROM comercio_interesse ci JOIN categoria c ON c.id = ci.categoria_id
                           WHERE ci.usuario_id = pc.usuario_id
                             AND (ci.categoria_id = ? OR ci.categoria_id = ? OR c.categoria_pai_id = ?))
            LIMIT ?""",
        (produto["vendedor_id"], regiao, categoria, principal, categoria, LIMITE_DE_AVISOS),
    ).fetchall()
    de_quem = f", de {produto['nome_vitrine']}" if produto["nome_vitrine"] else ""
    for loja in lojas:
        notificar(
            db, loja["usuario_id"], "produto_na_regiao",
            f'Produto novo para lojas perto de você: "{produto["titulo"]}"{de_quem}, '
            f'em {produto["municipio_nome"]}/{produto["uf"]}.',
            f"/produtos/{produto_id}",
        )
    return len(lojas)


def avisar_produtores_da_regiao(db, encomenda_id):
    encomenda = db.execute(
        """SELECT e.id, e.titulo, e.categoria_id, e.municipio_entrega_id, e.comprador_id,
                  m.nome AS municipio_nome, m.uf
             FROM encomenda e JOIN municipio m ON m.codigo_ibge = e.municipio_entrega_id WHERE e.id = ?""",
        (encomenda_id,),
    ).fetchone()
    regiao = _regiao(db, encomenda["municipio_entrega_id"])
    if regiao is None:
        return 0
    categoria, principal = _categoria_e_principal(db, encomenda["categoria_id"])
    produtores = db.execute(
        """SELECT pp.usuario_id FROM perfil_produtor pp
             JOIN municipio m ON m.codigo_ibge = pp.municipio_id
             JOIN usuario u   ON u.id = pp.usuario_id
            WHERE pp.status = 'ativo' AND u.status = 'ativo' AND pp.usuario_id <> ? AND m.regiao_imediata_id = ?
              AND EXISTS (SELECT 1 FROM produto pd JOIN categoria c ON c.id = pd.categoria_id
                           WHERE pd.vendedor_id = pp.usuario_id AND pd.status = 'ativo'
                             AND (pd.categoria_id = ? OR c.categoria_pai_id = ? OR pd.categoria_id = ?))
            LIMIT ?""",
        (encomenda["comprador_id"], regiao, categoria, categoria, principal, LIMITE_DE_AVISOS),
    ).fetchall()
    for produtor in produtores:
        notificar(
            db, produtor["usuario_id"], "encomenda_na_regiao",
            f'Encomenda nova perto de você: "{encomenda["titulo"]}", com entrega em '
            f'{encomenda["municipio_nome"]}/{encomenda["uf"]}.',
            f"/encomendas/{encomenda_id}",
        )
    return len(produtores)
