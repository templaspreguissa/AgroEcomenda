"""Formulário de anúncio de venda (RF04, RF05)."""
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ..db import get_db
from ..formularios import (
    CampoMunicipio, CampoQuantidade, CampoReais, Formulario, SelecaoObrigatoria, escolhas_categorias,
    escolhas_unidades, texto_limpo,
)

class AnuncioForm(Formulario):
    titulo = StringField(
        "O que você está vendendo?",
        filters=[texto_limpo],
        validators=[DataRequired("Diga o que você está vendendo."), Length(3, 100, "Use entre 3 e 100 caracteres.")],
    )
    categoria_id = SelecaoObrigatoria("Categoria", mensagem="Escolha uma categoria.")
    descricao = TextAreaField(
        "Descrição (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=3000, message="Use no máximo 3.000 caracteres.")],
    )
    preco = CampoReais("Preço (opcional)", filters=[texto_limpo], validators=[Optional()])
    unidade_id = SelecaoObrigatoria("Unidade de venda", mensagem="Escolha a unidade.")
    quantidade = CampoQuantidade("Quantidade disponível (opcional)", filters=[texto_limpo], validators=[Optional()])
    municipio = CampoMunicipio("Município onde está o produto", validators=[DataRequired("Informe o município.")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = get_db()
        self.categoria_id.choices = escolhas_categorias(db)
        self.unidade_id.choices = escolhas_unidades(db)

    def dados(self):
        return {
            "titulo": self.titulo.data,
            "categoria_id": self.categoria_id.data,
            "descricao": self.descricao.data or "",
            "preco_centavos": self.preco.centavos,
            "unidade_id": self.unidade_id.data,
            "quantidade": self.quantidade.numero,
            "municipio_id": self.municipio.codigo,
        }
