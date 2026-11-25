"""Modelos polimórficos de autoría para qa-platform.

Implementa la jerarquía ``Author`` -> ``User`` (``GeneralUser``, ``Admin``) y
``AIAgent`` mediante *Single Table Inheritance* (STI) en SQLAlchemy, permitiendo
que preguntas y respuestas referencien homogéneamente a cualquier emisor.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import orm
from werkzeug.security import check_password_hash, generate_password_hash

from qa_platform.extensions import db


def _require_non_empty(value: str, field_name: str) -> str:
    """Valida que un campo de texto obligatorio no esté vacío."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"El campo '{field_name}' debe ser una cadena no vacía.")
    return value.strip()


class Author(db.Model):
    """Clase base abstracta para cualquier emisor de contenido en la plataforma.

    Se persiste en la tabla única ``authors`` utilizando la columna
    discriminadora ``author_type`` para resolver las subclases de forma
    polimórfica.

    Attributes:
        id: Clave primaria autoincrementada.
        author_type: Discriminador de herencia polimórfica.
        display_name: Nombre visible del autor en la plataforma.
        created_at: Marca de tiempo UTC de creación del registro.
    """

    __tablename__ = "authors"

    id = db.Column(db.Integer, primary_key=True)
    author_type = db.Column(db.String(50), nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    # Se almacena siempre en UTC para evitar ambigüedades entre entornos.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    questions = db.relationship(
        "Question",
        back_populates="author",
        lazy="dynamic",
        foreign_keys="Question.user_id",
    )
    answers = db.relationship(
        "Answer",
        back_populates="author",
        lazy="dynamic",
        foreign_keys="Answer.author_id",
    )
    votes = db.relationship(
        "Vote",
        back_populates="user",
        lazy="dynamic",
        foreign_keys="Vote.user_id",
    )

    __mapper_args__ = {
        "polymorphic_on": "author_type",
        "polymorphic_identity": "author",
    }

    def __init__(self, **kwargs: Any) -> None:
        """Impide instanciar directamente la clase base abstracta ``Author``.

        Raises:
            TypeError: Si se intenta instanciar ``Author`` directamente.
        """
        if type(self) is Author:
            raise TypeError(
                "Author es una clase base abstracta y no puede instanciarse "
                "directamente."
            )
        super().__init__(**kwargs)

    def get_display_name(self) -> str:
        """Devuelve el nombre visible del autor.

        Returns:
            Nombre visible configurado para el autor.
        """
        return self.display_name

    def get_identifier(self) -> str:
        """Devuelve el identificador único legible del autor.

        Raises:
            NotImplementedError: Las subclases concretas deben implementarlo.
        """
        raise NotImplementedError(
            "Las subclases de Author deben implementar get_identifier()."
        )

    def is_agent(self) -> bool:
        """Indica si el autor corresponde a un agente automatizado de IA.

        Raises:
            NotImplementedError: Las subclases concretas deben implementarlo.
        """
        raise NotImplementedError(
            "Las subclases de Author deben implementar is_agent()."
        )


class User(Author):
    """Representa un usuario humano registrado en la plataforma.

    Attributes:
        username: Nombre de usuario único e indexado.
        email: Correo electrónico único e indexado.
        password_hash: Hash criptográfico de la contraseña (nunca texto plano).
        reputation: Puntuación acumulada por participación en la comunidad.
    """

    # Columnas específicas de subclase nulables en DB porque comparten la tabla
    # única ``authors`` con AIAgent bajo Single Table Inheritance.
    username = db.Column(
        db.String(80),
        unique=True,
        nullable=True,
        index=True,
    )
    email = db.Column(
        db.String(120),
        unique=True,
        nullable=True,
        index=True,
    )
    password_hash = db.Column(db.String(256), nullable=True)
    reputation = db.Column(db.Integer, nullable=True, default=0)

    __mapper_args__ = {
        "polymorphic_identity": "user",
    }

    def __init__(
        self,
        *,
        username: str,
        email: str,
        display_name: str | None = None,
        password: str | None = None,
        password_hash: str | None = None,
        reputation: int = 0,
        **kwargs: Any,
    ) -> None:
        """Inicializa un usuario humano validando sus atributos obligatorios.

        Args:
            username: Nombre de usuario único.
            email: Correo electrónico único.
            display_name: Nombre visible; si se omite se usa ``username``.
            password: Contraseña en texto plano para cifrar inmediatamente.
            password_hash: Hash previamente generado (opcional).
            reputation: Reputación inicial del usuario.
            **kwargs: Argumentos adicionales para subclases.

        Raises:
            ValueError: Si ``username``, ``email`` o ``password`` son vacíos.
        """
        clean_username = _require_non_empty(username, "username")
        clean_email = _require_non_empty(email, "email")
        resolved_display_name = (
            clean_username
            if display_name is None
            else _require_non_empty(display_name, "display_name")
        )

        super().__init__(
            username=clean_username,
            email=clean_email,
            display_name=resolved_display_name,
            password_hash=password_hash,
            reputation=reputation,
            **kwargs,
        )
        if password is not None:
            self.set_password(password)

    def set_password(self, password: str) -> None:
        """Almacena la contraseña de forma segura mediante un hash criptográfico.

        Args:
            password: Contraseña en texto plano a cifrar.

        Raises:
            ValueError: Si la contraseña es vacía o solo contiene espacios.
        """
        if not isinstance(password, str) or not password.strip():
            raise ValueError("La contraseña debe ser una cadena no vacía.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica si la contraseña provista coincide con el hash almacenado.

        Args:
            password: Contraseña en texto plano a comprobar.

        Returns:
            ``True`` si coincide con el hash guardado; ``False`` en caso contrario.
        """
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def get_email(self) -> str:
        """Devuelve el correo electrónico del usuario.

        Returns:
            Dirección de correo electrónico registrada.
        """
        return self.email

    def get_identifier(self) -> str:
        """Devuelve el nombre de usuario como identificador legible.

        Returns:
            Nombre de usuario único.
        """
        return self.username

    def is_agent(self) -> bool:
        """Indica que un usuario humano no es un agente de IA.

        Returns:
            Siempre ``False``.
        """
        return False

    def update_reputation(self, delta: int) -> int:
        """Actualiza la reputación del usuario sumando el desplazamiento indicado.

        Args:
            delta: Cantidad positiva o negativa a sumar a la reputación actual.

        Returns:
            Nuevo valor de reputación resultante.
        """
        self.reputation = (self.reputation or 0) + delta
        return self.reputation

    def __repr__(self) -> str:
        """Devuelve una representación legible del usuario para depuración.

        Returns:
            Cadena con la clase, id y username del usuario.
        """
        return f"<{type(self).__name__} id={self.id} username={self.username!r}>"


class GeneralUser(User):
    """Especialización de ``User`` para estudiantes y usuarios generales.

    Attributes:
        academic_level: Nivel académico del estudiante (grado, posgrado, etc.).
    """

    academic_level = db.Column(db.String(80), nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "general_user",
    }

    def get_academic_level(self) -> str | None:
        """Devuelve el nivel académico registrado para el usuario general.

        Returns:
            Nivel académico o ``None`` si no fue especificado.
        """
        return self.academic_level


class Admin(User):
    """Especialización de ``User`` con permisos de moderación en la plataforma.

    Attributes:
        special_permissions: Descripción o lista serializada de permisos extra.
    """

    special_permissions = db.Column(db.String(255), nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "admin",
    }

    def moderate_content(
        self, action: str, target_id: int | None = None
    ) -> dict[str, Any]:
        """Registra o ejecuta una acción de moderación autorizada por el admin.

        Args:
            action: Nombre de la acción de moderación a aplicar.
            target_id: Identificador opcional de la entidad moderada.

        Returns:
            Diccionario con el detalle de la acción autorizada.

        Raises:
            ValueError: Si ``action`` es vacía.
        """
        clean_action = _require_non_empty(action, "action")
        return {
            "moderator": self.username,
            "action": clean_action,
            "target_id": target_id,
            "authorized": True,
        }


class AIAgent(Author):
    """Representa un agente de inteligencia artificial capaz de generar respuestas.

    Attributes:
        bot_identifier: Identificador único del agente en la plataforma.
        version: Versión del agente o configuración del bot.
        system_prompt: Instrucciones de sistema asociadas al agente.
    """

    bot_identifier = db.Column(
        db.String(80),
        unique=True,
        nullable=True,
        index=True,
    )
    version = db.Column(db.String(40), nullable=True, default="1.0.0")
    system_prompt = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        "polymorphic_identity": "ai_agent",
    }

    def __init__(
        self,
        *,
        bot_identifier: str,
        display_name: str | None = None,
        version: str = "1.0.0",
        system_prompt: str | None = None,
        strategy: Any = None,
        **kwargs: Any,
    ) -> None:
        """Inicializa un agente de IA con su identificador y estrategia opcional.

        Args:
            bot_identifier: Identificador único del bot.
            display_name: Nombre visible; si se omite se usa ``bot_identifier``.
            version: Versión del agente.
            system_prompt: Prompt de sistema base para inferencia.
            strategy: Estrategia LLM inyectada en tiempo de ejecución.
            **kwargs: Argumentos adicionales del modelo base.

        Raises:
            ValueError: Si ``bot_identifier`` es vacío.
        """
        clean_bot_id = _require_non_empty(bot_identifier, "bot_identifier")
        resolved_display_name = (
            clean_bot_id
            if display_name is None
            else _require_non_empty(display_name, "display_name")
        )

        super().__init__(
            bot_identifier=clean_bot_id,
            display_name=resolved_display_name,
            version=version,
            system_prompt=system_prompt,
            **kwargs,
        )
        self._strategy: Any = strategy

    @orm.reconstructor
    def _init_on_load(self) -> None:
        """Inicializa atributos transitorios al reconstruir el modelo desde la DB.

        SQLAlchemy no invoca ``__init__`` al hidratar filas desde la base, por
        lo que inicializamos ``_strategy`` aquí para evitar ``AttributeError``.
        """
        self._strategy = None

    def is_agent(self) -> bool:
        """Indica que la instancia corresponde a un agente automatizado de IA.

        Returns:
            Siempre ``True``.
        """
        return True

    def get_identifier(self) -> str:
        """Devuelve el identificador único del agente bot.

        Returns:
            Identificador del bot.
        """
        return self.bot_identifier

    def set_strategy(self, strategy: Any) -> None:
        """Asigna o reemplaza la estrategia LLM utilizada por el agente.

        Args:
            strategy: Instancia compatible con el contrato ``LLMStrategy``.
        """
        self._strategy = strategy

    def get_current_strategy(self) -> str | None:
        """Devuelve el nombre de la estrategia LLM actualmente configurada.

        Returns:
            Nombre del proveedor si la estrategia implementa
            ``get_provider_name()``, nombre de su clase en otro caso, o ``None``
            si no hay ninguna estrategia inyectada.
        """
        if self._strategy is None:
            return None
        if hasattr(self._strategy, "get_provider_name"):
            return self._strategy.get_provider_name()
        return type(self._strategy).__name__

    def generate_response(self, prompt: str, context: str = "") -> str:
        """Delega la generación de texto en la estrategia LLM configurada.

        Combina el ``system_prompt`` del agente (si existe) con el ``context``
        provisto antes de invocar ``self._strategy.generate_response()``.

        Args:
            prompt: Consigna o pregunta principal enviada al modelo.
            context: Información adicional contextual de la consulta.

        Returns:
            Texto generado por la estrategia LLM activa.

        Raises:
            RuntimeError: Si el agente no tiene ninguna estrategia inyectada.
        """
        if self._strategy is None:
            raise RuntimeError("El agente IA no tiene una estrategia LLM configurada.")

        context_parts = [
            part.strip()
            for part in (self.system_prompt or "", context or "")
            if isinstance(part, str) and part.strip()
        ]
        combined_context = "\n\n".join(context_parts)
        return self._strategy.generate_response(prompt, combined_context)

    def answer_question(self, question: Any) -> Any:
        """Construye prompt y contexto desde una ``Question`` y crea un ``Answer``.

        Args:
            question: Instancia de ``Question`` que se desea responder.

        Returns:
            Nueva instancia de ``Answer`` asociada a la pregunta y a este
            agente (sin hacer ``commit`` en base de datos).

        Raises:
            ValueError: Si ``question`` es ``None``.
            RuntimeError: Si el agente no tiene estrategia configurada.
        """
        if question is None:
            raise ValueError("Se requiere una pregunta válida para responder.")

        prompt = f"{question.title}\n\n{question.body}".strip()

        context_lines: list[str] = []
        if getattr(question, "category", None) is not None:
            context_lines.append(f"Categoría: {question.category.name}")
        raw_tags = getattr(question, "tags", None)
        if raw_tags is not None:
            tag_names = [tag.name for tag in raw_tags]
            if tag_names:
                context_lines.append(f"Etiquetas: {', '.join(tag_names)}")

        body = self.generate_response(prompt, context="\n".join(context_lines))

        # Importación local para evitar dependencias circulares con models/answer.py.
        from qa_platform.models.answer import Answer

        return Answer(body=body, question=question, author=self)

    def __repr__(self) -> str:
        """Devuelve una representación legible del agente IA para depuración.

        Returns:
            Cadena con el id, identificador del bot y versión.
        """
        return (
            f"<AIAgent id={self.id} bot_identifier={self.bot_identifier!r} "
            f"version={self.version!r}>"
        )
