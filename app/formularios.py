"""Base dos formulários: mensagens padrão do WTForms em português."""
from flask_wtf import FlaskForm


class Formulario(FlaskForm):
    class Meta:
        # Usa as traduções que vêm com o WTForms (exige WTF_I18N_ENABLED = False na configuração).
        locales = ("pt_BR", "pt")
