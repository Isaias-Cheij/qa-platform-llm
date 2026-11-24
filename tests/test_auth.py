"""Pruebas unitarias y funcionales para registro, login y sesiones firmadas."""

import pytest

from qa_platform.models import GeneralUser, User
from qa_platform.services import (
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
)
from qa_platform.web import login_required


class TestAuthService:
    """Pruebas de unidad para las reglas de negocio de AuthService."""

    def test_register_user_persists_hashed_password_and_normalized_email(self, db):
        """Registra un GeneralUser con email en minúsculas y contraseña hasheada."""
        service = AuthService()
        user = service.register_user(
            username="  isaias_qa  ",
            email="Isaias.QA@Example.COM ",
            password="ClaveMuySegura123",
            display_name="Isaías Cheij",
            academic_level="Grado",
        )

        assert user.id is not None
        assert isinstance(user, GeneralUser)
        assert user.username == "isaias_qa"
        assert user.email == "isaias.qa@example.com"
        assert user.display_name == "Isaías Cheij"
        assert user.academic_level == "Grado"
        assert user.password_hash != "ClaveMuySegura123"
        assert user.check_password("ClaveMuySegura123") is True

    def test_register_user_rejects_duplicate_email_case_insensitive(self, db):
        """Impide registrar dos usuarios con el mismo correo electrónico."""
        service = AuthService()
        service.register_user(
            username="user_one",
            email="dup@example.com",
            password="Password123",
        )

        with pytest.raises(RegistrationError) as exc_info:
            service.register_user(
                username="user_two",
                email="DUP@example.com",
                password="Password123",
            )

        assert exc_info.value.field == "email"

    def test_register_user_rejects_duplicate_username_case_insensitive(self, db):
        """Impide registrar dos usuarios con el mismo username."""
        service = AuthService()
        service.register_user(
            username="JuanL",
            email="juan1@example.com",
            password="Password123",
        )

        with pytest.raises(RegistrationError) as exc_info:
            service.register_user(
                username="juanl",
                email="juan2@example.com",
                password="Password123",
            )

        assert exc_info.value.field == "username"

    @pytest.mark.parametrize(
        ("username", "email", "password", "expected_field"),
        [
            ("ab", "valid@example.com", "Password123", "username"),
            ("valid_user", "correo-invalido", "Password123", "email"),
            ("valid_user", "valid@example.com", "corta", "password"),
            ("valid_user", "valid@example.com", "        ", "password"),
        ],
    )
    def test_register_user_validates_fields(
        self, db, username, email, password, expected_field
    ):
        """Valida longitud de username, formato de email y largo mínimo de clave."""
        service = AuthService()

        with pytest.raises(RegistrationError) as exc_info:
            service.register_user(
                username=username,
                email=email,
                password=password,
            )

        assert exc_info.value.field == expected_field

    def test_authenticate_user_success_and_failures(self, db):
        """Verifica credenciales válidas y rechaza contraseña o correo erróneos."""
        service = AuthService()
        service.register_user(
            username="joaquin_n",
            email="joaquin@example.com",
            password="MiPassword2026",
        )

        authenticated = service.authenticate_user(
            email="JOAQUIN@example.com",
            password="MiPassword2026",
        )
        assert authenticated.username == "joaquin_n"

        with pytest.raises(InvalidCredentialsError):
            service.authenticate_user(
                email="joaquin@example.com",
                password="otra-password",
            )

        with pytest.raises(InvalidCredentialsError):
            service.authenticate_user(
                email="noexiste@example.com",
                password="MiPassword2026",
            )


class TestAuthWebRoutes:
    """Pruebas funcionales HTTP para registro, login, logout y rutas protegidas."""

    def test_get_register_renders_accessible_autofill_form(self, client):
        """GET /auth/register devuelve 200 con atributos de autofill esperados."""
        response = client.get("/auth/register")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'autocomplete="username"' in html
        assert 'autocomplete="new-password"' in html
        assert 'type="email"' in html

    def test_post_register_creates_user_signs_session_and_updates_nav(self, client, db):
        """POST /auth/register válido crea usuario, inicia sesión y redirige a /."""
        response = client.post(
            "/auth/register",
            data={
                "username": "nuevo_est",
                "display_name": "Estudiante Nuevo",
                "email": "nuevo@example.com",
                "password": "ClaveSegura99",
                "academic_level": "Grado",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

        user = db.session.scalar(
            db.select(User).where(User.email == "nuevo@example.com")
        )
        assert user is not None
        assert user.password_hash != "ClaveSegura99"
        assert user.check_password("ClaveSegura99") is True

        with client.session_transaction() as sess:
            assert sess["user_id"] == user.id

        home_resp = client.get("/")
        home_html = home_resp.get_data(as_text=True)
        assert "Estudiante Nuevo" in home_html
        assert "/auth/logout" in home_html

    def test_post_register_duplicate_email_returns_400(self, client, db):
        """POST /auth/register con email duplicado devuelve 400 y marca el campo."""
        AuthService().register_user(
            username="primero",
            email="repetido@example.com",
            password="Password123",
        )

        response = client.post(
            "/auth/register",
            data={
                "username": "segundo",
                "email": "repetido@example.com",
                "password": "Password123",
            },
        )

        assert response.status_code == 400
        html = response.get_data(as_text=True)
        assert 'aria-invalid="true"' in html
        assert db.session.scalars(db.select(User)).all().__len__() == 1

    def test_post_register_short_password_returns_400_and_does_not_persist(
        self, client, db
    ):
        """POST /auth/register con contraseña corta devuelve 400 sin crear usuario."""
        response = client.post(
            "/auth/register",
            data={
                "username": "usuario_corto",
                "email": "corto@example.com",
                "password": "123",
            },
        )

        assert response.status_code == 400
        assert db.session.scalars(db.select(User)).all() == []

    def test_get_login_renders_autofill_attributes(self, client):
        """GET /auth/login devuelve 200 con autocomplete para inicio de sesión."""
        response = client.get("/auth/login")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'autocomplete="username"' in html
        assert 'autocomplete="current-password"' in html

    def test_post_login_valid_sets_signed_cookie_and_session(self, client, db):
        """POST /auth/login válido firma la cookie de sesión y redirige."""
        user = AuthService().register_user(
            username="login_ok",
            email="login@example.com",
            password="PasswordValida1",
        )

        response = client.post(
            "/auth/login",
            data={"email": "login@example.com", "password": "PasswordValida1"},
        )

        assert response.status_code == 302
        assert "Set-Cookie" in response.headers
        with client.session_transaction() as sess:
            assert sess["user_id"] == user.id

    def test_post_login_invalid_credentials_returns_401(self, client, db):
        """POST /auth/login inválido devuelve 401 y no autentica la sesión."""
        AuthService().register_user(
            username="login_fail",
            email="fail@example.com",
            password="PasswordValida1",
        )

        response = client.post(
            "/auth/login",
            data={"email": "fail@example.com", "password": "incorrecta"},
        )

        assert response.status_code == 401
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_post_logout_clears_session(self, client, db):
        """POST /auth/logout limpia la sesión firmada y redirige al inicio."""
        AuthService().register_user(
            username="logout_user",
            email="logout@example.com",
            password="PasswordValida1",
        )
        client.post(
            "/auth/login",
            data={"email": "logout@example.com", "password": "PasswordValida1"},
        )

        response = client.post("/auth/logout")
        assert response.status_code == 302

        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_profile_requires_authentication(self, client, db):
        """GET /auth/profile redirige si es anónimo y responde 200 si está logueado."""
        anon_resp = client.get("/auth/profile")
        assert anon_resp.status_code == 302
        assert anon_resp.headers["Location"].endswith("/auth/login?next=/auth/profile")

        AuthService().register_user(
            username="perfil_user",
            email="perfil@example.com",
            password="PasswordValida1",
        )
        client.post(
            "/auth/login",
            data={"email": "perfil@example.com", "password": "PasswordValida1"},
        )

        auth_resp = client.get("/auth/profile")
        assert auth_resp.status_code == 200
        assert "perfil@example.com" in auth_resp.get_data(as_text=True)

    def test_login_required_protects_publication_route_and_redirects_back(
        self, app, client, db
    ):
        """Una ruta de publicación protegida exige login y respeta el parámetro next.

        Usa un endpoint stub propio (/stub/publish) para verificar el
        comportamiento del decorador login_required de forma aislada, sin
        depender de la implementacion real de /questions/new (que ya esta
        registrada por questions_bp y aplica validaciones adicionales).
        """

        @app.route("/stub/publish", methods=("GET", "POST"))
        @login_required
        def publish_stub():
            return {"created": True}, 201

        # Un usuario anonimo debe ser redirigido al login conservando el next.
        anon_post = client.post("/stub/publish")
        assert anon_post.status_code == 302
        assert anon_post.headers["Location"].endswith("/auth/login?next=/stub/publish")

        AuthService().register_user(
            username="author_ok",
            email="author@example.com",
            password="PasswordValida1",
        )
        login_resp = client.post(
            "/auth/login",
            data={
                "email": "author@example.com",
                "password": "PasswordValida1",
                "next": "/stub/publish",
            },
        )
        assert login_resp.status_code == 302
        assert login_resp.headers["Location"].endswith("/stub/publish")

        # Con sesion activa, el stub devuelve 201 sin ninguna validacion extra.
        auth_post = client.post("/stub/publish")
        assert auth_post.status_code == 201
        assert auth_post.json == {"created": True}

    @pytest.mark.parametrize(
        "malicious_next",
        [
            "https://evil.example/steal",
            "//evil.example/phish",
        ],
    )
    def test_login_rejects_open_redirect_targets(self, client, db, malicious_next):
        """Ignora URLs externas en el parámetro next para evitar open redirects."""
        AuthService().register_user(
            username="safe_redirect",
            email="safe@example.com",
            password="PasswordValida1",
        )

        response = client.post(
            "/auth/login",
            data={
                "email": "safe@example.com",
                "password": "PasswordValida1",
                "next": malicious_next,
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_tampered_session_cookie_is_rejected(self, app, client, db):
        """Una cookie de sesión adulterada no autentica al usuario."""
        AuthService().register_user(
            username="signed_user",
            email="signed@example.com",
            password="PasswordValida1",
        )
        client.post(
            "/auth/login",
            data={"email": "signed@example.com", "password": "PasswordValida1"},
        )

        cookie_name = app.config.get("SESSION_COOKIE_NAME", "session")
        client.set_cookie(cookie_name, "forged.tampered.cookie-payload")

        response = client.get("/auth/profile")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]
