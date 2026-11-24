"""Servicio de autenticación y registro de usuarios para qa-platform.

Encapsula las reglas de negocio de registro, validación de unicidad,
verificación de credenciales y recuperación de usuarios autenticados sin
acoplar los controladores HTTP a detalles de persistencia.
"""

from sqlalchemy.exc import IntegrityError

from qa_platform.extensions import db
from qa_platform.factories import UserFactory
from qa_platform.models import User


class AuthError(Exception):
    """Excepción base para errores de autenticación y registro."""


class RegistrationError(AuthError):
    """Error de validación o conflicto durante el registro de un usuario.

    Attributes:
        field: Nombre del campo del formulario asociado al error, si aplica.
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class InvalidCredentialsError(AuthError):
    """Error lanzado cuando el correo o la contraseña no son válidos."""


class AuthService:
    """Servicio de dominio para registrar y autenticar usuarios humanos."""

    def __init__(self, user_factory: UserFactory | None = None) -> None:
        """Inicializa el servicio con una fábrica de usuarios inyectable.

        Args:
            user_factory: Fábrica concreta usada para instanciar y registrar
                nuevos usuarios. Si se omite, crea una instancia de
                ``UserFactory``.
        """
        self._user_factory = user_factory or UserFactory()

    def register_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        display_name: str | None = None,
        academic_level: str | None = None,
    ) -> User:
        """Valida los datos de registro y persiste un nuevo ``GeneralUser``.

        Args:
            username: Nombre de usuario deseado (3 a 80 caracteres).
            email: Correo electrónico único del usuario.
            password: Contraseña en texto plano (mínimo 8 caracteres).
            display_name: Nombre visible opcional; si se omite usa ``username``.
            academic_level: Nivel académico opcional del estudiante.

        Returns:
            Instancia persistida del usuario registrado.

        Raises:
            RegistrationError: Si algún campo es inválido o ya existe otro
                usuario con el mismo correo o nombre de usuario.
        """
        clean_username = (username or "").strip()
        if len(clean_username) < 3 or len(clean_username) > 80:
            raise RegistrationError(
                "El nombre de usuario debe tener entre 3 y 80 caracteres.",
                field="username",
            )

        clean_email = (email or "").strip().lower()
        _, at_sep, domain = clean_email.partition("@")
        if (
            not clean_email
            or len(clean_email) > 120
            or not at_sep
            or "." not in domain
            or any(ch.isspace() for ch in clean_email)
        ):
            raise RegistrationError(
                "Ingresá un correo electrónico válido.",
                field="email",
            )

        if not isinstance(password, str) or not password.strip() or len(password) < 8:
            raise RegistrationError(
                "La contraseña debe tener al menos 8 caracteres.",
                field="password",
            )

        resolved_display_name = (display_name or "").strip() or clean_username
        resolved_academic_level = (academic_level or "").strip() or None

        existing_email = db.session.scalar(
            db.select(User).where(db.func.lower(User.email) == clean_email)
        )
        if existing_email is not None:
            raise RegistrationError(
                "Ya existe una cuenta registrada con ese correo electrónico.",
                field="email",
            )

        existing_username = db.session.scalar(
            db.select(User).where(
                db.func.lower(User.username) == clean_username.lower()
            )
        )
        if existing_username is not None:
            raise RegistrationError(
                "Ese nombre de usuario ya está en uso.",
                field="username",
            )

        try:
            user = self._user_factory.register_author(
                clean_username,
                resolved_display_name,
                email=clean_email,
                password=password,
                role="general",
                academic_level=resolved_academic_level,
            )
        except IntegrityError as exc:
            db.session.rollback()
            raise RegistrationError(
                "No se pudo completar el registro porque el usuario o correo ya existe."
            ) from exc

        return user

    def authenticate_user(self, *, email: str, password: str) -> User:
        """Verifica las credenciales de un usuario registrado.

        Args:
            email: Correo electrónico ingresado en el formulario de login.
            password: Contraseña en texto plano a validar contra el hash.

        Returns:
            Instancia de ``User`` correspondiente a las credenciales válidas.

        Raises:
            InvalidCredentialsError: Si el usuario no existe o la contraseña
                no coincide.
        """
        clean_email = (email or "").strip().lower()
        if not clean_email or not password:
            raise InvalidCredentialsError(
                "Correo electrónico o contraseña incorrectos."
            )

        user = db.session.scalar(
            db.select(User).where(db.func.lower(User.email) == clean_email)
        )
        if user is None or not user.check_password(password):
            raise InvalidCredentialsError(
                "Correo electrónico o contraseña incorrectos."
            )

        return user

    def get_user_by_id(self, user_id: int | None) -> User | None:
        """Recupera un usuario humano por su identificador primario.

        Args:
            user_id: Identificador almacenado en la sesión de Flask.

        Returns:
            El ``User`` encontrado, o ``None`` si no existe o corresponde a un
            autor no humano.
        """
        if user_id is None:
            return None

        user = db.session.get(User, user_id)
        return user if isinstance(user, User) else None
