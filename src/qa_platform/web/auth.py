"""Blueprint web de autenticación: registro, inicio/cierre de sesión y protección."""

import functools
from collections.abc import Callable
from typing import Any, cast
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from qa_platform.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
)

SESSION_USER_ID_KEY = "user_id"

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
_auth_service = AuthService()


def _is_safe_next_url(target: str | None) -> bool:
    """Valida que la URL de retorno sea una ruta relativa interna segura.

    Evita vulnerabilidades de *open redirect* rechazando URLs externas o con
    esquema/host explícito (por ejemplo ``https://...`` o ``//evil.com``).
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc


@auth_bp.before_app_request
def load_logged_in_user() -> None:
    """Carga el usuario autenticado en ``g.current_user`` a partir de ``session``."""
    user_id = session.get(SESSION_USER_ID_KEY)
    g.current_user = _auth_service.get_user_by_id(user_id)
    # Si la sesión referenciaba a un usuario eliminado o inválido, limpiarla.
    if user_id is not None and g.current_user is None:
        session.pop(SESSION_USER_ID_KEY, None)


@auth_bp.app_context_processor
def inject_current_user() -> dict[str, Any]:
    """Expone ``current_user`` automáticamente en todas las plantillas Jinja2."""
    return {"current_user": getattr(g, "current_user", None)}


def login_required[F: Callable[..., Any]](view: F) -> F:
    """Decorador que restringe una ruta web a usuarios con sesión iniciada.

    Si no hay un usuario autenticado en ``g.current_user``, redirige al
    formulario de login conservando la ruta solicitada en el parámetro
    ``next``.
    """

    @functools.wraps(view)
    def wrapped_view(*args: Any, **kwargs: Any) -> Any:
        if getattr(g, "current_user", None) is None:
            flash("Debés iniciar sesión para acceder a esta sección.", "warning")
            next_target = (
                request.full_path.rstrip("?") if request.query_string else request.path
            )
            return redirect(url_for("auth.login", next=next_target))
        return view(*args, **kwargs)

    return cast(F, wrapped_view)


@auth_bp.route("/register", methods=("GET", "POST"))
def register() -> Any:
    """Muestra y procesa el formulario de registro de nuevos usuarios."""
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "")
        display_name = request.form.get("display_name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        academic_level = request.form.get("academic_level", "")

        form_data = {
            "username": username,
            "display_name": display_name,
            "email": email,
            "academic_level": academic_level,
        }

        try:
            user = _auth_service.register_user(
                username=username,
                email=email,
                password=password,
                display_name=display_name or None,
                academic_level=academic_level or None,
            )
        except RegistrationError as exc:
            errors = {exc.field or "general": str(exc)}
            flash(str(exc), "danger")
            return (
                render_template(
                    "auth/register.html",
                    form_data=form_data,
                    errors=errors,
                ),
                400,
            )

        # Regenerar el contenido de la sesión al autenticar para evitar
        # fijación de sesión (session fixation).
        session.clear()
        session[SESSION_USER_ID_KEY] = user.id
        flash("Cuenta creada con éxito. ¡Bienvenido/a!", "success")
        return redirect(url_for("index"))

    return render_template("auth/register.html", form_data={}, errors={})


@auth_bp.route("/login", methods=("GET", "POST"))
def login() -> Any:
    """Muestra y procesa el formulario de inicio de sesión."""
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            user = _auth_service.authenticate_user(email=email, password=password)
        except InvalidCredentialsError as exc:
            flash(str(exc), "danger")
            return (
                render_template(
                    "auth/login.html",
                    form_data={"email": email},
                    errors={"general": str(exc)},
                    next_url=next_url,
                ),
                401,
            )

        session.clear()
        session[SESSION_USER_ID_KEY] = user.id
        flash(f"¡Hola de nuevo, {user.get_display_name()}!", "success")

        destination = next_url if _is_safe_next_url(next_url) else url_for("index")
        return redirect(destination)

    return render_template(
        "auth/login.html",
        form_data={},
        errors={},
        next_url=next_url,
    )


@auth_bp.post("/logout")
def logout() -> Any:
    """Cierra la sesión activa del usuario y redirige al inicio."""
    session.clear()
    flash("Cerraste sesión correctamente.", "info")
    return redirect(url_for("index"))


@auth_bp.get("/profile")
@login_required
def profile() -> Any:
    """Muestra el perfil básico del usuario actualmente autenticado."""
    return render_template("auth/profile.html", user=g.current_user)
