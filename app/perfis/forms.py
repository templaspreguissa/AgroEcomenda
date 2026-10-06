"""Formulários dos perfis de produtor e de comércio (RF26, RF27) e dos dados da conta (RF02)."""
from wtforms import BooleanField, RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, Optional, ValidationError

from .. import cnpj
from ..formularios import (
    CampoMunicipio, CampoTelefone, Formulario, SelecaoObrigatoria, texto_limpo, texto_ou_nada,
)
from ..util import FORMAS_VENDA, ORGANICO, TIPOS_COMERCIO


class _ContatoPublico:
    telefone = CampoTelefone("Telefone comercial (opcional)", filters=[texto_limpo], validators=[Optional()])
    whatsapp = BooleanField("Este número também é WhatsApp")


class PerfilProdutorForm(_ContatoPublico, Formulario):
    nome_vitrine = StringField(
        "Nome da vitrine",
        filters=[texto_limpo],
        validators=[DataRequired("Dê um nome para a sua vitrine."), Length(3, 80, "Use entre 3 e 80 caracteres.")],
    )
    descricao = TextAreaField(
        "Sobre a sua produção (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=1500, message="Use no máximo 1.500 caracteres.")],
    )
    municipio = CampoMunicipio("Município da propriedade")
    vende_retirada = BooleanField(FORMAS_VENDA["vende_retirada"])
    vende_entrega = BooleanField(FORMAS_VENDA["vende_entrega"])
    vende_feira = BooleanField(FORMAS_VENDA["vende_feira"])
    vende_envio = BooleanField(FORMAS_VENDA["vende_envio"])
    onde_encontrar = StringField(
        "Onde e quando encontrar você (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=300, message="Use no máximo 300 caracteres.")],
    )
    organico = RadioField("A produção é orgânica?", choices=list(ORGANICO.items()), default="nao")
    organico_registro = StringField(
        "Certificadora ou OCS",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=120, message="Use no máximo 120 caracteres.")],
    )

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        self.erro_formas = None
        if not any(self.formas().values()):
            self.erro_formas = "Escolha pelo menos uma forma de venda."
            valido = False
        if self.vende_feira.data and not self.onde_encontrar.data:
            self.onde_encontrar.errors.append("Diga onde e quando fica a feira ou o ponto de venda.")
            valido = False
        if self.organico.data != "nao" and not self.organico_registro.data:
            self.organico_registro.errors.append("Informe a certificadora ou a OCS. Sem isso, marque “Não”.")
            valido = False
        return valido

    def formas(self):
        return {chave: bool(getattr(self, chave).data) for chave in FORMAS_VENDA}

    def dados(self):
        return {
            "nome_vitrine": self.nome_vitrine.data,
            "descricao": self.descricao.data or "",
            "municipio_id": self.municipio.codigo,
            **self.formas(),
            "onde_encontrar": self.onde_encontrar.data or "",
            "organico": self.organico.data,
            "organico_registro": self.organico_registro.data if self.organico.data != "nao" else "",
            "telefone_publico": self.telefone.digitos,
            "telefone_whatsapp": bool(self.whatsapp.data and self.telefone.digitos),
        }


class PerfilComercioForm(_ContatoPublico, Formulario):
    nome_fantasia = StringField(
        "Nome do comércio",
        filters=[texto_limpo],
        validators=[DataRequired("Informe o nome do comércio."), Length(2, 80, "Use entre 2 e 80 caracteres.")],
    )
    cnpj = StringField("CNPJ", filters=[texto_limpo], validators=[DataRequired("Informe o CNPJ.")])
    tipo = SelecaoObrigatoria(
        "Tipo de comércio", mensagem="Escolha o tipo de comércio.", coerce=texto_ou_nada,
        choices=list(TIPOS_COMERCIO.items()),
    )
    descricao = TextAreaField(
        "Sobre o comércio (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=1500, message="Use no máximo 1.500 caracteres.")],
    )
    municipio = CampoMunicipio("Município")
    volume_compra = StringField(
        "O que e quanto costuma comprar (opcional)",
        filters=[texto_limpo],
        validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")],
    )

    def validate_cnpj(self, campo):
        if not cnpj.valido(campo.data):
            raise ValidationError("CNPJ inválido. Confira os 14 caracteres, por exemplo 12.ABC.345/01DE-35.")

    def dados(self):
        return {
            "nome_fantasia": self.nome_fantasia.data,
            "cnpj": cnpj.normalizar(self.cnpj.data),
            "tipo": self.tipo.data,
            "descricao": self.descricao.data or "",
            "municipio_id": self.municipio.codigo,
            "volume_compra": self.volume_compra.data or "",
            "telefone_publico": self.telefone.digitos,
            "telefone_whatsapp": bool(self.whatsapp.data and self.telefone.digitos),
        }


class ContaForm(Formulario):
    nome = StringField(
        "Seu nome",
        filters=[texto_limpo],
        validators=[DataRequired("Informe seu nome."), Length(2, 120, "Use entre 2 e 120 caracteres.")],
    )
    tipo_pessoa = RadioField(
        "Você é",
        choices=[("PF", "Pessoa física"), ("PJ", "Empresa ou cooperativa")],
        validators=[InputRequired("Escolha uma opção.")],
    )
    municipio = CampoMunicipio("Seu município (opcional)", validators=[Optional()])
