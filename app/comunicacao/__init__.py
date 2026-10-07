from flask import Blueprint

bp = Blueprint("comunicacao", __name__)

from . import routes  # noqa: E402,F401  (registra as rotas no blueprint)
