"""Formulários de cadastro e login (Flask-WTF já inclui o token CSRF)."""
from flask import current_app
from wtforms import BooleanField, EmailField, PasswordField, RadioField, StringField
from wtforms.validators import DataRequired, EqualTo, InputRequired, Length, Regexp, ValidationError

from ..formularios import CaixasDeSelecao, Formulario

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def sem_espacos_nas_pontas(valor):
    """O autocompletar do celular costuma deixar um espaço no fim do e-mail."""
    return valor.strip() if isinstance(valor, str) else valor

# Lista curta de senhas comuns. O NIST SP 800-63B-4 pede comparar a senha
# com uma lista de senhas comuns ou vazadas. Em produção, use uma lista maior.
SENHAS_COMUNS = {
    "123456789012345", "1234567890123456", "123456789123456789",
    "senhasenhasenha", "senha1234567890", "minhasenha12345",
    "qwertyuiopasdfg", "qwertyuiopasdfgh", "abcdefghijklmno",
    "passwordpassword", "agroencomenda123", "agroencomenda2026",
    "aaaaaaaaaaaaaaa", "000000000000000", "111111111111111",
}


USOS = {
    "vender": "Vender o que eu produzo",
    "comercio": "Comprar para o meu comércio (mercado, restaurante, distribuidor...)",
    "consumo": "Comprar direto do produtor para consumo",
}


def problema_da_senha(senha, email=""):
    """Regras do NIST SP 800-63B-4: comprimento mínimo, sem senhas comuns e sem partes do e-mail."""
    senha = senha or ""
    minimo = current_app.config["SENHA_MINIMA"]
    if len(senha) < minimo:
        return f"Use pelo menos {minimo} caracteres. Dica: junte quatro palavras, como uma frase."
    compacta = senha.lower().replace(" ", "")
    if compacta in SENHAS_COMUNS or len(set(compacta)) <= 2:
        return "Essa senha é muito comum. Escolha outra."
    parte_email = (email or "").split("@")[0].lower()
    if len(parte_email) >= 4 and parte_email in senha.lower():
        return "A senha não pode conter o seu e-mail."
    return None


class CadastroForm(Formulario):
    nome = StringField(
        "Seu nome",
        validators=[DataRequired("Informe seu nome."), Length(2, 120, "Use entre 2 e 120 caracteres.")],
    )
    email = EmailField(
        "E-mail",
        filters=[sem_espacos_nas_pontas],
        validators=[
            DataRequired("Informe seu e-mail."),
            Length(max=254, message="E-mail longo demais."),
            Regexp(EMAIL_RE, message="Informe um e-mail válido, como nome@exemplo.com."),
        ],
    )
    tipo_pessoa = RadioField(
        "Você é",
        choices=[("PF", "Pessoa física"), ("PJ", "Empresa ou cooperativa")],
        default="PF",
        validators=[InputRequired("Escolha uma opção.")],
    )
    usos = CaixasDeSelecao("Como você vai usar o AgroEncomenda? (opcional)", choices=list(USOS.items()))
    senha = PasswordField(
        "Senha",
        validators=[DataRequired("Crie uma senha."), Length(max=128, message="Use no máximo 128 caracteres.")],
    )
    confirmar = PasswordField(
        "Repita a senha",
        validators=[DataRequired("Repita a senha."), EqualTo("senha", "As senhas não são iguais.")],
    )
    aceite = BooleanField(
        "Li e aceito os Termos de Uso e a Política de Privacidade",
        validators=[DataRequired("Para criar a conta, aceite os Termos de Uso e a Política de Privacidade.")],
    )

    def validate_senha(self, campo):
        problema = problema_da_senha(campo.data, self.email.data)
        if problema:
            raise ValidationError(problema)


class LoginForm(Formulario):
    email = EmailField(
        "E-mail", filters=[sem_espacos_nas_pontas], validators=[DataRequired("Informe seu e-mail."), Length(max=254)]
    )
    senha = PasswordField("Senha", validators=[DataRequired("Informe sua senha."), Length(max=128)])


class EsqueciSenhaForm(Formulario):
    email = EmailField(
        "E-mail da conta", filters=[sem_espacos_nas_pontas],
        validators=[DataRequired("Informe seu e-mail."), Length(max=254)],
    )


class RedefinirSenhaForm(Formulario):
    senha = PasswordField(
        "Nova senha",
        validators=[DataRequired("Crie uma senha."), Length(max=128, message="Use no máximo 128 caracteres.")],
    )
    confirmar = PasswordField(
        "Repita a nova senha",
        validators=[DataRequired("Repita a senha."), EqualTo("senha", "As senhas não são iguais.")],
    )

    def __init__(self, email, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email_da_conta = email

    def validate_senha(self, campo):
        problema = problema_da_senha(campo.data, self.email_da_conta)
        if problema:
            raise ValidationError(problema)
