"""AgroEncomenda: marketplace de negociações no agronegócio.

Ponto de entrada da aplicação Flask (padrão "application factory").
"""
import logging
import os
import secrets
from datetime import timedelta

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect

csrf = CSRFProtect()

# Política de segurança de conteúdo: só recursos do próprio site.
# Por isso todo JavaScript fica em arquivos .js (nada de <script> inline).
CSP = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "agroencomenda.db"),
        PASTA_FOTOS=os.path.join(app.instance_path, "uploads"),  # fora de /static e fora do Git
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,  # até 5 fotos de celular por envio
        FOTO_TAMANHO_MAXIMO=8 * 1024 * 1024,
        FOTOS_POR_PRODUTO=5,
        TERMOS_VERSAO="2026-10-v0.6",
        REPOSITORIO_URL="https://github.com/templaspreguissa/AgroEcomenda",
        SENHA_MINIMA=15,
        LOGIN_MAX_FALHAS=5,
        LOGIN_BLOQUEIO_MINUTOS=15,
        WTF_I18N_ENABLED=False,  # mensagens do WTForms em português via Meta.locales (app/formularios.py)
        ITENS_POR_PAGINA=20,
        CONVERSAS_NOVAS_POR_DIA=20,  # contra spam (RF33)
        MENSAGENS_POR_HORA=60,
    )

    if test_config is None:
        # Configuração local opcional em instance/config.py (fora do Git)
        # e variáveis de ambiente com prefixo FLASK_ (ex.: FLASK_SECRET_KEY).
        app.config.from_pyfile("config.py", silent=True)
        app.config.from_prefixed_env()
    else:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        if app.debug:
            app.config["SECRET_KEY"] = "chave-de-desenvolvimento-nao-usar-em-producao"
        else:
            # Chave aleatória só para esta execução: segura, mas as sessões caem a cada reinício.
            app.config["SECRET_KEY"] = secrets.token_hex()
            app.logger.warning("FLASK_SECRET_KEY não definida: usando chave temporária.")

    if app.config.get("SESSION_COOKIE_SECURE") is None and not app.debug and not app.testing:
        app.config["SESSION_COOKIE_SECURE"] = True

    os.makedirs(app.instance_path, exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    csrf.init_app(app)

    from . import comandos, db
    db.init_app(app)
    comandos.init_app(app)

    from .util import registrar_filtros
    registrar_filtros(app)

    from . import visibilidade
    visibilidade.registrar(app)

    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .comunicacao import bp as comunicacao_bp
    from .contratos import bp as contratos_bp
    from .encomendas import bp as encomendas_bp
    from .main import bp as main_bp
    from .perfis import bp as perfis_bp
    from .produtos import bp as produtos_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(perfis_bp)
    app.register_blueprint(produtos_bp)
    app.register_blueprint(encomendas_bp)
    app.register_blueprint(comunicacao_bp)
    app.register_blueprint(contratos_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)

    @app.after_request
    def cabecalhos_de_seguranca(resposta):
        resposta.headers.setdefault("Content-Security-Policy", CSP)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resposta

    @app.errorhandler(CSRFError)
    def erro_csrf(_erro):
        return render_template(
            "erro.html",
            titulo="Formulário expirado",
            mensagem="O formulário expirou ou foi enviado de outro site. Volte, recarregue a página e tente de novo.",
        ), 400

    @app.errorhandler(403)
    def erro_403(_erro):
        return render_template(
            "erro.html", titulo="Acesso negado", mensagem="Você não tem permissão para ver esta página."
        ), 403

    @app.errorhandler(404)
    def erro_404(_erro):
        return render_template(
            "erro.html", titulo="Página não encontrada", mensagem="Confira o endereço ou volte para o início."
        ), 404

    @app.errorhandler(413)
    def erro_413(_erro):
        return render_template(
            "erro.html", titulo="Arquivo grande demais", mensagem="O envio passou do tamanho máximo permitido."
        ), 413

    return app
