"""Formulários de encomenda e de proposta."""
from datetime import timedelta

from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, Optional, ValidationError

from ..db import get_db
from ..formularios import Formulario
from ..localidades import resolver_municipio
from ..util import TRANSPORTE, hoje, ler_quantidade, reais_para_centavos

ESCOLHAS_TRANSPORTE = list(TRANSPORTE.items())


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else valor


def escolhas_categorias(db, rotulo_geral="{nome} (outros)"):
    """Categorias agrupadas pela principal, para <select> com <optgroup>."""
    linhas = db.execute("SELECT id, categoria_pai_id, nome FROM categoria WHERE ativa = 1 ORDER BY nome").fetchall()
    principais = [linha for linha in linhas if linha["categoria_pai_id"] is None]
    grupos = {}
    for principal in sorted(principais, key=lambda linha: linha["id"]):
        filhas = [(linha["id"], linha["nome"]) for linha in linhas if linha["categoria_pai_id"] == principal["id"]]
        grupos[principal["nome"]] = filhas + [(principal["id"], rotulo_geral.format(nome=principal["nome"]))]
    return grupos


def escolhas_unidades(db):
    return [(linha["id"], linha["nome"]) for linha in db.execute("SELECT id, nome FROM unidade_medida ORDER BY id")]


def _inteiro_ou_nada(valor):
    return int(valor) if valor not in (None, "") else None


class SelecaoObrigatoria(SelectField):
    """<select> que começa em "Escolha..." e exige uma opção (evita publicar com a primeira opção sem querer)."""

    def __init__(self, label=None, mensagem="Escolha uma opção.", **kwargs):
        super().__init__(label, coerce=_inteiro_ou_nada, **kwargs)
        self.mensagem = mensagem

    def pre_validate(self, form):
        if self.data is None:
            raise ValidationError(self.mensagem)
        super().pre_validate(form)


class CampoQuantidade(StringField):
    """Aceita '30', '2,5' ou '1.250,75'. Guarda o número em self.numero."""

    def pre_validate(self, form):
        self.numero = None
        if not self.data:
            return
        try:
            self.numero = ler_quantidade(self.data)
        except ValueError as erro:
            raise ValidationError("Use só números, por exemplo 30 ou 2,5.") from erro
        if self.numero <= 0:
            raise ValidationError("Informe uma quantidade maior que zero.")
        if self.numero > 1_000_000_000:
            raise ValidationError("Quantidade grande demais.")


class CampoReais(StringField):
    """Aceita '147', '147,50' ou '1.234,56'. Guarda o valor em centavos em self.centavos."""

    def pre_validate(self, form):
        self.centavos = None
        if not self.data:
            return
        try:
            self.centavos = reais_para_centavos(self.data)
        except ValueError as erro:
            raise ValidationError("Use só números, por exemplo 147,50.") from erro
        if self.centavos <= 0:
            raise ValidationError("Informe um preço maior que zero.")
        if self.centavos > 100_000_000_000:
            raise ValidationError("Preço grande demais.")


class EncomendaForm(Formulario):
    titulo = StringField(
        "O que você precisa comprar?",
        filters=[_texto],
        validators=[DataRequired("Diga o que você precisa."), Length(3, 100, "Use entre 3 e 100 caracteres.")],
    )
    categoria_id = SelecaoObrigatoria("Categoria", mensagem="Escolha uma categoria.")
    descricao = TextAreaField(
        "Detalhes (opcional)",
        filters=[_texto],
        validators=[Optional(), Length(max=2000, message="Use no máximo 2.000 caracteres.")],
    )
    quantidade = CampoQuantidade("Quantidade", filters=[_texto], validators=[DataRequired("Informe a quantidade.")])
    unidade_id = SelecaoObrigatoria("Unidade", mensagem="Escolha a unidade.")
    municipio = StringField(
        "Município de entrega",
        filters=[_texto],
        validators=[DataRequired("Informe o município de entrega.")],
    )
    prazo_limite = DateField("Prazo limite para entrega", validators=[DataRequired("Informe uma data válida.")])
    transporte = RadioField(
        "Transporte", choices=ESCOLHAS_TRANSPORTE, default="a_combinar",
        validators=[InputRequired("Escolha uma opção.")],
    )
    condicoes_pagamento = StringField(
        "Condições de pagamento (opcional)",
        filters=[_texto],
        validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = get_db()
        self.categoria_id.choices = escolhas_categorias(db)
        self.unidade_id.choices = escolhas_unidades(db)
        self.municipio_id = None

    def validate_municipio(self, campo):
        self.municipio_id = resolver_municipio(get_db(), campo.data)
        if self.municipio_id is None:
            raise ValidationError("Escolha um município da lista, no formato Município/UF (ex.: Uberaba/MG).")

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
            "municipio_id": self.municipio_id,
            "prazo_limite": self.prazo_limite.data,
            "transporte": self.transporte.data,
            "condicoes_pagamento": self.condicoes_pagamento.data or "",
        }


class PropostaForm(Formulario):
    preco = CampoReais("Preço", filters=[_texto], validators=[DataRequired("Informe o preço.")])
    quantidade = CampoQuantidade(
        "Quantidade que você oferece", filters=[_texto], validators=[DataRequired("Informe a quantidade.")]
    )
    prazo_entrega = DateField("Data de entrega", validators=[DataRequired("Informe uma data válida.")])
    transporte = RadioField(
        "Transporte", choices=ESCOLHAS_TRANSPORTE, default="a_combinar",
        validators=[InputRequired("Escolha uma opção.")],
    )
    validade = DateField("Proposta válida até (opcional)", validators=[Optional()])
    observacao = TextAreaField(
        "Observações (opcional)",
        filters=[_texto],
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
