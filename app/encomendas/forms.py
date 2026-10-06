"""Formulários de encomenda e de proposta."""
from datetime import timedelta

from wtforms import DateField, RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, Optional, ValidationError

from ..db import get_db
from ..formularios import (
    ESCOLHAS_TRANSPORTE, CampoMunicipio, CampoQuantidade, CampoReais, Formulario, SelecaoObrigatoria,
    escolhas_categorias, escolhas_unidades, texto_limpo,
)
from ..util import hoje


class EncomendaForm(Formulario):
    titulo = StringField(
        "O que você precisa comprar?",
        filters=[texto_limpo],
        validators=[DataRequired("Diga o que você precisa."), Length(3, 100, "Use entre 3 e 100 caracteres.")],
    )
    categoria_id = SelecaoObrigatoria("Categoria", mensagem="Escolha uma categoria.")
    descricao = TextAreaField(
        "Detalhes (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=2000, message="Use no máximo 2.000 caracteres.")],
    )
    quantidade = CampoQuantidade("Quantidade", filters=[texto_limpo], validators=[DataRequired("Informe a quantidade.")])
    unidade_id = SelecaoObrigatoria("Unidade", mensagem="Escolha a unidade.")
    municipio = CampoMunicipio(
        "Município de entrega", validators=[DataRequired("Informe o município de entrega.")]
    )
    prazo_limite = DateField("Prazo limite para entrega", validators=[DataRequired("Informe uma data válida.")])
    transporte = RadioField(
        "Transporte", choices=ESCOLHAS_TRANSPORTE, default="a_combinar",
        validators=[InputRequired("Escolha uma opção.")],
    )
    condicoes_pagamento = StringField(
        "Condições de pagamento (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = get_db()
        self.categoria_id.choices = escolhas_categorias(db)
        self.unidade_id.choices = escolhas_unidades(db)

    def validate_prazo_limite(self, campo):
        if campo.data < hoje():
            raise ValidationError("O prazo limite não pode ser uma data que já passou.")
        if campo.data > hoje() + timedelta(days=366):
            raise ValidationError("Use um prazo de até um ano.")

    def dados(self):
        return {
            "titulo": self.titulo.data,
            "categoria_id": self.categoria_id.data,
            "descricao": self.descricao.data or "",
            "quantidade": self.quantidade.numero,
            "unidade_id": self.unidade_id.data,
            "municipio_id": self.municipio.codigo,
            "prazo_limite": self.prazo_limite.data,
            "transporte": self.transporte.data,
            "condicoes_pagamento": self.condicoes_pagamento.data or "",
        }


class PropostaForm(Formulario):
    """Usado nos dois fluxos: produtor respondendo encomenda e comprador fazendo oferta num produto."""

    preco = CampoReais("Preço", filters=[texto_limpo], validators=[DataRequired("Informe o preço.")])
    quantidade = CampoQuantidade(
        "Quantidade que você oferece", filters=[texto_limpo], validators=[DataRequired("Informe a quantidade.")]
    )
    prazo_entrega = DateField("Data de entrega", validators=[DataRequired("Informe uma data válida.")])
    transporte = RadioField(
        "Transporte", choices=ESCOLHAS_TRANSPORTE, default="a_combinar",
        validators=[InputRequired("Escolha uma opção.")],
    )
    validade = DateField("Proposta válida até (opcional)", validators=[Optional()])
    observacao = TextAreaField(
        "Observações (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=1000, message="Use no máximo 1.000 caracteres.")],
    )

    def dados(self):
        return {
            "preco_centavos": self.preco.centavos,
            "quantidade": self.quantidade.numero,
            "prazo_entrega": self.prazo_entrega.data,
            "transporte": self.transporte.data,
            "validade": self.validade.data,
            "observacao": self.observacao.data or "",
        }
