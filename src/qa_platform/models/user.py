"""Modelo de dominio User para qa-platform.

Define la entidad de usuario persistida en la base de datos relacional
mediante SQLAlchemy. El modelo se instancia sin asociacion directa a una
app concreta; la tabla se crea al ejecutar ``db.create_all()`` dentro del
contexto de aplicacion.
"""

from datetime import UTC, datetime

from qa_platform.extensions import db


class User(db.Model):
    """Representa un usuario registrado en la plataforma.

    Attributes:
        id: Clave primaria autoincrementada.
        username: Nombre de usuario unico, indexado para busquedas frecuentes.
        email: Correo electronico unico, indexado para busquedas frecuentes.
        created_at: Marca de tiempo UTC del momento de creacion del registro.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )
    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True,
    )
    # Se almacena siempre en UTC para evitar ambiguedades al comparar
    # registros entre entornos con distintos husos horarios.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """Devuelve una representacion legible del objeto para depuracion.

        Returns:
            Cadena con el id y username del usuario.
        """
        return f"<User id={self.id} username={self.username!r}>"
