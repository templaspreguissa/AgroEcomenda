from flask import Blueprint

bp = Blueprint("anuncios", __name__)

from . import routes  # noqa: E402,F401  (registra as rotas no blueprint)
