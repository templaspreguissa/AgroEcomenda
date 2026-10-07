"""Formulário do contrato de fornecimento (RF34)."""
from wtforms import DateField, FieldList, Form, FormField, IntegerField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional

from ..db import get_db
from ..formularios import (
    ESCOLHAS_TRANSPORTE, CampoMunicipio, CampoQuantidade, CampoReais, Formulario, escolhas_unidades, texto_limpo,
)
from ..servicos.contratos import ITENS_MAXIMOS
from ..util import FREQUENCIAS

LINHAS_DE_ITEM = 5


def _inteiro_ou_nada(valor):
    return int(valor) if valor not in (None, "") else None


class ItemContratoForm(Form):
    """Uma linha da tabela de itens. Linha toda em branco é ignorada."""

    class Meta:
        locales = ("pt_BR", "pt")

    produto_id = SelectField("Produto do catálogo", coerce=_inteiro_ou_nada, validators=[Optional()])
    descricao = StringField("Descrição", filters=[texto_limpo], validators=[Optional(), Length(max=120)])
    quantidade = CampoQuantidade("Quantidade por entrega", filters=[texto_limpo], validators=[Optional()])
    unidade_id = SelectField("Unidade", coerce=_inteiro_ou_nada, validators=[Optional()])
    preco = CampoReais("Preço por unidade (R$)", filters=[texto_limpo], validators=[Optional()])

    def em_branco(self):
        return not (self.produto_id.data or self.descricao.data or self.quantidade.data or self.preco.data)

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        if self.em_branco():
            return valido
        if not self.produto_id.data and not self.descricao.data:
            self.descricao.errors.append("Escolha um produto ou descreva o item.")
            valido = False
        if not self.quantidade.data:
            self.quantidade.errors.append("Informe a quantidade por entrega.")
            valido = False
        if not self.preco.data:
            self.preco.errors.append("Informe o preço.")
            valido = False
        if not self.produto_id.data and not self.unidade_id.data:
            self.unidade_id.errors.append("Escolha a unidade.")
            valido = False
        return valido


class ContratoForm(Formulario):
    inicio = DateField("Início das entregas", validators=[DataRequired("Informe uma data válida.")])
    termino = DateField("Fim do contrato", validators=[DataRequired("Informe uma data válida.")])
    frequencia = RadioField("Frequência das entregas", choices=list(FREQUENCIAS.items()), default="semanal",
                            validators=[InputRequired("Escolha uma opção.")])
    dia_entrega = StringField("Dia e horário de entrega (opcional)", filters=[texto_limpo],
                              validators=[Optional(), Length(max=120, message="Use no máximo 120 caracteres.")])
    transporte = RadioField("Transporte", choices=ESCOLHAS_TRANSPORTE, default="vendedor_entrega",
                            validators=[InputRequired("Escolha uma opção.")])
    municipio_entrega = CampoMunicipio("Município de entrega")
    local_entrega = StringField("Local de entrega (opcional)", filters=[texto_limpo],
                                validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")])
    condicoes_pagamento = StringField("Pagamento", filters=[texto_limpo],
                                      validators=[DataRequired("Diga como e quando será o pagamento."),
                                                  Length(max=200, message="Use no máximo 200 caracteres.")])
    reajuste = StringField("Reajuste de preço (opcional)", filters=[texto_limpo],
                           validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")])
    padrao_qualidade = TextAreaField("Padrão de qualidade (opcional)", filters=[texto_limpo],
                                     validators=[Optional(), Length(max=600, message="Use no máximo 600 caracteres.")])
    aviso_previo_dias = IntegerField("Aviso prévio para rescisão (dias)", default=30,
                                     validators=[InputRequired("Informe o número de dias."),
                                                 NumberRange(0, 180, "Use de 0 a 180 dias.")])
    observacoes = TextAreaField("Observações (opcional)", filters=[texto_limpo],
                                validators=[Optional(), Length(max=1000, message="Use no máximo 1.000 caracteres.")])
    itens = FieldList(FormField(ItemContratoForm), min_entries=LINHAS_DE_ITEM, max_entries=ITENS_MAXIMOS)

    def __init__(self, produtor_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = get_db()
        produtos = [("", "Outro item (descreva)")] + [
            (linha["id"], f"{linha['titulo']} ({linha['sigla']})")
            for linha in db.execute(
                """SELECT pd.id, pd.titulo, u.sigla FROM produto pd JOIN unidade_medida u ON u.id = pd.unidade_id
                    WHERE pd.vendedor_id = ? AND pd.status IN ('ativo', 'pausado') ORDER BY pd.titulo""",
                (produtor_id,),
            )
        ]
        unidades = [("", "Escolha")] + escolhas_unidades(db)
        for linha in self.itens:
            linha.produto_id.choices = produtos
            linha.unidade_id.choices = unidades
        self.produtos_do_produtor = {
            linha["id"]: linha for linha in db.execute(
                "SELECT id, titulo, unidade_id FROM produto WHERE vendedor_id = ?", (produtor_id,)
            )
        }

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        self.erro_itens = None
        if valido and not self.lista_de_itens():
            self.erro_itens = "Inclua pelo menos um item no contrato."
            valido = False
        if self.inicio.data and self.termino.data and self.termino.data <= self.inicio.data:
            self.termino.errors.append("O fim precisa ser depois do início.")
            valido = False
        return valido

    def lista_de_itens(self):
        """Itens preenchidos, com descrição e unidade vindas do produto quando o produtor escolheu um do catálogo."""
        itens = []
        for linha in self.itens:
            if linha.form.em_branco():
                continue
            produto = self.produtos_do_produtor.get(linha.produto_id.data)
            itens.append({
                "produto_id": produto["id"] if produto else None,
                "descricao": linha.descricao.data or (produto["titulo"] if produto else ""),
                "quantidade": linha.quantidade.numero,
                "unidade_id": linha.unidade_id.data or (produto["unidade_id"] if produto else None),
                "preco_centavos": linha.preco.centavos,
            })
        return itens

    def termos(self):
        return {
            "inicio": self.inicio.data.isoformat(),
            "termino": self.termino.data.isoformat(),
            "frequencia": self.frequencia.data,
            "dia_entrega": self.dia_entrega.data or "",
            "transporte": self.transporte.data,
            "municipio_entrega_id": self.municipio_entrega.codigo,
            "local_entrega": self.local_entrega.data or "",
            "condicoes_pagamento": self.condicoes_pagamento.data,
            "padrao_qualidade": self.padrao_qualidade.data or "",
            "reajuste": self.reajuste.data or "",
            "aviso_previo_dias": self.aviso_previo_dias.data,
            "observacoes": self.observacoes.data or "",
        }
