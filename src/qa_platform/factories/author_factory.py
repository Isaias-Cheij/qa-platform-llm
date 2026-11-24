"""Creador abstracto del patrón Factory Method para autores."""

from abc import ABC, abstractmethod
from typing import Any

from qa_platform.extensions import db
from qa_platform.models.author import Author


class AuthorFactory(ABC):
    """Fábrica abstracta para crear y registrar autores de la plataforma."""

    @abstractmethod
    def create_author(
        self, identifier: str, display_name: str, **kwargs: Any
    ) -> Author:
        """Instancia un autor concreto sin persistirlo en la base de datos.

        Args:
            identifier: Identificador único del autor (username o bot_identifier).
            display_name: Nombre visible en la plataforma.
            **kwargs: Parámetros específicos de cada subtipo de autor.

        Returns:
            Instancia concreta de ``Author``.
        """

    def register_author(
        self,
        identifier: str,
        display_name: str,
        *,
        commit: bool = True,
        **kwargs: Any,
    ) -> Author:
        """Crea un autor mediante el factory method y lo persiste en sesión.

        Args:
            identifier: Identificador único del autor.
            display_name: Nombre visible en la plataforma.
            commit: Indica si se debe confirmar la transacción inmediatamente.
            **kwargs: Parámetros adicionales reenviados a ``create_author()``.

        Returns:
            La instancia de ``Author`` agregada (y persistida si ``commit=True``).
        """
        author = self.create_author(identifier, display_name, **kwargs)
        db.session.add(author)
        if commit:
            db.session.commit()
        return author
