"""Comandos de linha de comando além dos do banco (app/db.py)."""
import secrets

import click
from flask.cli import with_appcontext

from .db import get_db


@click.command("verificar-comercio")
@click.argument("usuario_id", type=int)
@click.option("--remover", is_flag=True, help="Tira o selo de verificado.")
@with_appcontext
def verificar_comercio_command(usuario_id, remover):
    """Marca a loja (perfil de comércio) da conta USUARIO_ID como verificada.

    Use depois de conferir o CNPJ na Receita Federal. Até existir a tela de administração,
    a verificação é feita por aqui.
    """
    from .perfis.dados import verificar_comercio
    if not verificar_comercio(get_db(), usuario_id, verificado=not remover):
        raise click.ClickException(f"A conta {usuario_id} não tem perfil de comércio.")
    click.echo(f"Loja da conta {usuario_id} {'sem selo de verificado' if remover else 'verificada'}.")


@click.command("tornar-admin")
@click.argument("email")
@click.option("--remover", is_flag=True, help="Volta a conta para usuário comum.")
@with_appcontext
def tornar_admin_command(email, remover):
    """Dá (ou tira) o papel de administração da conta com este e-mail."""
    db = get_db()
    with db:
        alterou = db.execute(
            "UPDATE usuario SET papel = ? WHERE email = ? AND status = 'ativo'",
            ("usuario" if remover else "admin", email.strip().lower()),
        ).rowcount
    if not alterou:
        raise click.ClickException("Nenhuma conta ativa com esse e-mail.")
    click.echo("Conta voltou a ser de usuário comum." if remover else "Conta agora é de administração.")


@click.command("carregar-demo")
@click.option("--senha-fixa", is_flag=True,
              help="Usa a senha de app/demo.py, que é pública. Só no computador local, nunca no site publicado.")
@with_appcontext
def carregar_demo_command(senha_fixa):
    """Cria contas, vitrines, lojas e produtos fictícios para demonstração.

    Sem --senha-fixa, sorteia uma senha para as pessoas da história e outra para a administração,
    e mostra as duas uma única vez.
    """
    from .demo import DEMO_SENHA, DemoJaCarregada, carregar_demo
    senha, senha_admin = (DEMO_SENHA, None) if senha_fixa else (secrets.token_urlsafe(12), secrets.token_urlsafe(12))
    try:
        resumo = carregar_demo(get_db(), senha, senha_admin)
    except DemoJaCarregada as erro:
        raise click.ClickException(str(erro)) from erro
    click.echo(resumo)
    if senha_fixa:
        click.echo("Senha de todas as contas: a de app/demo.py.")
    else:
        click.echo(f"Senha de ana, carlos, jose, rita, paulo e marina: {senha}")
        click.echo(f"Senha de admin.demo@example.com: {senha_admin}")
        click.echo("Anote agora: as senhas não ficam guardadas e não aparecem de novo.")


def init_app(app):
    app.cli.add_command(verificar_comercio_command)
    app.cli.add_command(carregar_demo_command)
    app.cli.add_command(tornar_admin_command)
