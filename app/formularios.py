"""Base e campos reutilizáveis dos formulários (mensagens em português)."""
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired, ValidationError

from .db import get_db
from .localidades import resolver_municipio
from .util import TRANSPORTE, ler_quantidade, reais_para_centavos

ESCOLHAS_TRANSPORTE = list(TRANSPORTE.items())


class Formulario(FlaskForm):
    class Meta:
        # Usa as traduções que vêm com o WTForms (exige WTF_I18N_ENABLED = False na configuração).
        locales = ("pt_BR", "pt")


def texto_limpo(valor):
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
    """Aceita '30', '2,5' ou '1.250,75'. Guarda o número em self.numero (None se vazio)."""

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
    """Aceita '147', '147,50' ou '1.234,56'. Guarda o valor em centavos em self.centavos (None se vazio)."""

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


class CampoMunicipio(StringField):
    """Texto 'Município/UF' (com sugestões de <datalist>). Guarda o código IBGE em self.codigo."""

    def __init__(self, label=None, **kwargs):
        kwargs.setdefault("filters", [texto_limpo])
        kwargs.setdefault("validators", [DataRequired("Informe o município.")])
        super().__init__(label, **kwargs)

    def post_validate(self, form, validation_stopped):
        self.codigo = None
        if validation_stopped or self.errors:
            return
        self.codigo = resolver_municipio(get_db(), self.data)
        if self.codigo is None:
            self.errors.append("Escolha um município da lista, no formato Município/UF (ex.: Uberaba/MG).")
