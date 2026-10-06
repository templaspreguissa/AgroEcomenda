"""Formulário de produto (RF04, RF05, RF28, RF32)."""
from wtforms import BooleanField, RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ..db import get_db
from ..formularios import (
    CaixasDeSelecao, CampoMunicipio, CampoQuantidade, CampoReais, Formulario, SelecaoObrigatoria,
    escolhas_categorias, escolhas_unidades, texto_limpo,
)
from ..util import DISPONIBILIDADE, MESES_POR_EXTENSO


class ProdutoForm(Formulario):
    titulo = StringField(
        "O que você produz e vende?",
        filters=[texto_limpo],
        validators=[DataRequired("Diga qual é o produto."), Length(3, 100, "Use entre 3 e 100 caracteres.")],
    )
    categoria_id = SelecaoObrigatoria("Categoria", mensagem="Escolha uma categoria.")
    descricao = TextAreaField(
        "Descrição (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=3000, message="Use no máximo 3.000 caracteres.")],
    )
    unidade_id = SelecaoObrigatoria("Unidade de venda", mensagem="Escolha a unidade.")
    quantidade = CampoQuantidade("Quantidade disponível (opcional)", filters=[texto_limpo], validators=[Optional()])
    municipio = CampoMunicipio("Município onde está o produto", validators=[DataRequired("Informe o município.")])

    # Para quem vende e por quanto (RF28)
    para_consumidor = BooleanField("Vender para o consumidor final")
    preco_consumidor = CampoReais("Preço para o consumidor (opcional)", filters=[texto_limpo], validators=[Optional()])
    para_lojista = BooleanField("Vender para lojas e outros comércios")
    preco_lojista = CampoReais("Preço para lojas (opcional)", filters=[texto_limpo], validators=[Optional()])
    pedido_minimo = CampoQuantidade("Pedido mínimo para lojas (opcional)", filters=[texto_limpo], validators=[Optional()])
    so_verificados = BooleanField("Mostrar o preço para lojas só a comércios verificados")

    # Quando tem (RF32)
    disponibilidade = RadioField("Quando você tem este produto?", choices=list(DISPONIBILIDADE.items()), default="ano_todo")
    meses = CaixasDeSelecao(
        "Meses da safra", coerce=int, choices=[(numero, nome) for numero, nome in enumerate(MESES_POR_EXTENSO, start=1)],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        db = get_db()
        self.categoria_id.choices = escolhas_categorias(db)
        self.unidade_id.choices = escolhas_unidades(db)

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        self.erro_publico = None
        if not self.para_consumidor.data and not self.para_lojista.data:
            self.erro_publico = "Marque para quem você vende: consumidor final, lojas ou os dois."
            valido = False
        if self.disponibilidade.data == "safra" and not self.meses.data:
            self.meses.errors.append("Marque os meses da safra.")
            valido = False
        return valido

    def mascara_meses(self):
        if self.disponibilidade.data != "safra":
            return 0
        return sum(1 << (mes - 1) for mes in set(self.meses.data or []) if 1 <= mes <= 12)

    def dados(self):
        """Os campos de um público desmarcado são ignorados (o navegador pode enviá-los sem JavaScript)."""
        para_consumidor, para_lojista = bool(self.para_consumidor.data), bool(self.para_lojista.data)
        return {
            "titulo": self.titulo.data,
            "categoria_id": self.categoria_id.data,
            "descricao": self.descricao.data or "",
            "unidade_id": self.unidade_id.data,
            "quantidade_disponivel": self.quantidade.numero,
            "municipio_id": self.municipio.codigo,
            "para_consumidor": para_consumidor,
            "para_lojista": para_lojista,
            "preco_consumidor_centavos": self.preco_consumidor.centavos if para_consumidor else None,
            "preco_lojista_centavos": self.preco_lojista.centavos if para_lojista else None,
            "pedido_minimo_lojista": self.pedido_minimo.numero if para_lojista else None,
            "so_verificados": bool(self.so_verificados.data) and para_lojista,
            "disponibilidade": self.disponibilidade.data,
            "meses_safra": self.mascara_meses(),
        }
