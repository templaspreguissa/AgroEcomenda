"""Cadastro, login, logout e controle de acesso."""
import functools
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import abort, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from . import bp
from .forms import CadastroForm, LoginForm

# Alinhado à recomendação da OWASP para PBKDF2-HMAC-SHA256 (600.000 iterações).
# O padrão do Werkzeug (scrypt:32768:8:1) fica abaixo da tabela da OWASP.
METODO_HASH = "pbkdf2:sha256:600000"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger("agroencomenda.auth")
_hash_ficticio = None


def agora_utc():
    return datetime.now(timezone.utc)


def _texto_data(momento):
    return momento.strftime(FORMATO_DATA)


@bp.before_app_request
def carregar_usuario():
    g.usuario = None
    usuario_id = session.get("usuario_id")
    if usuario_id is None:
        return
    g.usuario = get_db().execute(
        "SELECT id, nome, email, papel, tipo_pessoa, criado_em FROM usuario WHERE id = ? AND status = 'ativo'",
        (usuario_id,),
    ).fetchone()
    if g.usuario is None:
        session.clear()


def login_obrigatorio(view):
    @functools.wraps(view)
    def envoltorio(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.entrar", next=request.path))
        return view(*args, **kwargs)
    return envoltorio


def admin_obrigatorio(view):
    @functools.wraps(view)
    def envoltorio(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.entrar", next=request.path))
        if g.usuario["papel"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return envoltorio


def destino_seguro(alvo):
    """Aceita só caminhos internos, para evitar redirecionamento para outro site."""
    if not alvo or not alvo.startswith("/") or alvo.startswith("//") or "\\" in alvo:
        return None
    partes = urlsplit(alvo)
    if partes.scheme or partes.netloc:
        return None
    return alvo


def _iniciar_sessao(usuario_id):
    session.clear()  # evita fixação de sessão
    session["usuario_id"] = usuario_id
    session.permanent = True


# ---------- limite de tentativas de login ----------

def _janela_bloqueio():
    return timedelta(minutes=current_app.config["LOGIN_BLOQUEIO_MINUTOS"])


def _registro_falhas(email):
    return get_db().execute(
        "SELECT falhas, ultima_falha FROM bloqueio_login WHERE email = ?", (email,)
    ).fetchone()


def _dentro_da_janela(registro):
    ultima = datetime.strptime(registro["ultima_falha"], FORMATO_DATA).replace(tzinfo=timezone.utc)
    return agora_utc() - ultima < _janela_bloqueio()


def esta_bloqueado(email):
    registro = _registro_falhas(email)
    return bool(
        registro
        and registro["falhas"] >= current_app.config["LOGIN_MAX_FALHAS"]
        and _dentro_da_janela(registro)
    )


def registrar_falha(email):
    db = get_db()
    registro = _registro_falhas(email)
    agora = _texto_data(agora_utc())
    with db:
        if registro and _dentro_da_janela(registro):
            db.execute(
                "UPDATE bloqueio_login SET falhas = falhas + 1, ultima_falha = ? WHERE email = ?",
                (agora, email),
            )
        else:
            db.execute(
                "INSERT OR REPLACE INTO bloqueio_login (email, falhas, ultima_falha) VALUES (?, 1, ?)",
                (email, agora),
            )


def limpar_falhas(email):
    db = get_db()
    with db:
        db.execute("DELETE FROM bloqueio_login WHERE email = ?", (email,))


def _conferir_senha(senha_hash, senha):
    """Confere a senha. Sem usuário, compara com um hash fictício para o tempo de resposta ser parecido."""
    global _hash_ficticio
    if senha_hash is None:
        if _hash_ficticio is None:
            _hash_ficticio = generate_password_hash("senha-ficticia-para-tempo-constante", method=METODO_HASH)
        check_password_hash(_hash_ficticio, senha)
        return False
    return check_password_hash(senha_hash, senha)


# ---------- rotas ----------

@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if g.usuario is not None:
        return redirect(url_for("main.painel"))

    form = CadastroForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        db = get_db()
        try:
            with db:
                cursor = db.execute(
                    "INSERT INTO usuario (nome, email, senha_hash, tipo_pessoa, termos_versao, termos_aceitos_em) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        form.nome.data.strip(),
                        email,
                        generate_password_hash(form.senha.data, method=METODO_HASH),
                        form.tipo_pessoa.data,
                        current_app.config["TERMOS_VERSAO"],
                        _texto_data(agora_utc()),
                    ),
                )
        except sqlite3.IntegrityError:
            form.email.errors.append("Já existe uma conta com este e-mail. Tente entrar.")
        else:
            _iniciar_sessao(cursor.lastrowid)
            log.info("cadastro concluido usuario_id=%s", cursor.lastrowid)
            flash("Conta criada. Boas-vindas ao AgroEncomenda!", "sucesso")
            return redirect(url_for("main.painel"))

    return render_template("auth/cadastro.html", form=form)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if g.usuario is not None:
        return redirect(url_for("main.painel"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if esta_bloqueado(email):
            log.warning("login bloqueado por excesso de tentativas")
            flash("Muitas tentativas sem sucesso. Aguarde alguns minutos e tente de novo.", "erro")
        else:
            usuario = get_db().execute(
                "SELECT id, senha_hash FROM usuario WHERE email = ? AND status = 'ativo'", (email,)
            ).fetchone()
            if _conferir_senha(usuario["senha_hash"] if usuario else None, form.senha.data):
                limpar_falhas(email)
                _iniciar_sessao(usuario["id"])
                log.info("login ok usuario_id=%s", usuario["id"])
                return redirect(destino_seguro(request.args.get("next")) or url_for("main.painel"))
            registrar_falha(email)
            log.warning("falha de login")
            flash("E-mail ou senha incorretos.", "erro")

    return render_template("auth/entrar.html", form=form)


@bp.route("/sair", methods=["POST"])
def sair():
    if g.usuario is not None:
        log.info("logout usuario_id=%s", g.usuario["id"])
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("main.index"))
