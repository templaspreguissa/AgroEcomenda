"""Comandos de linha de comando além dos do banco (app/db.py)."""
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


@click.command("carregar-demo")
@with_appcontext
def carregar_demo_command():
    """Cria contas, vitrines, lojas e anúncios fictícios para demonstração (só em ambiente local)."""
    from .demo import DemoJaCarregada, carregar_demo
    try:
        resumo = carregar_demo(get_db())
    except DemoJaCarregada as erro:
        raise click.ClickException(str(erro)) from erro
    click.echo(resumo)


def init_app(app):
    app.cli.add_command(verificar_comercio_command)
    app.cli.add_command(carregar_demo_command)
