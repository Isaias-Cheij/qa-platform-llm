"""Fábrica concreta para la creación de usuarios humanos."""

from typing import Any

from qa_platform.factories.author_factory import AuthorFactory
from qa_platform.models.author import Admin, GeneralUser, User


class UserFactory(AuthorFactory):
    """Concrete Creator que instancia ``User``, ``GeneralUser`` y ``Admin``."""

    def create_author(self, identifier: str, display_name: str, **kwargs: Any) -> User:
        """Crea una instancia de usuario humano según el rol solicitado.

        Args:
            identifier: Nombre de usuario único (``username``).
            display_name: Nombre visible del usuario.
            **kwargs: Debe incluir ``email``; opcionalmente acepta ``password``,
                ``role`` (``"general"``, ``"admin"`` o ``"user"``),
                ``academic_level``, ``special_permissions`` y ``reputation``.

        Returns:
            Instancia de ``GeneralUser``, ``Admin`` o ``User``.

        Raises:
            ValueError: Si falta ``email`` o se especifica un ``role`` inválido.
        """
        email = kwargs.get("email")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("El campo 'email' es obligatorio para crear un usuario.")

        password = kwargs.get("password")
        role = kwargs.get("role", "general")
        reputation = kwargs.get("reputation", 0)

        common_args: dict[str, Any] = {
            "username": identifier,
            "email": email,
            "display_name": display_name,
            "password": password,
            "reputation": reputation,
        }

        if role == "general":
            return GeneralUser(
                **common_args,
                academic_level=kwargs.get("academic_level"),
            )
        if role == "admin":
            return Admin(
                **common_args,
                special_permissions=kwargs.get("special_permissions"),
            )
        if role == "user":
            return User(**common_args)

        raise ValueError(
            f"Rol de usuario no reconocido: {role!r}. "
            "Valores permitidos: 'general', 'admin', 'user'."
        )
