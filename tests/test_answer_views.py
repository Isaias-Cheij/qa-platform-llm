"""Pruebas de integración web para el flujo de respuestas y solución aceptada.

Verifica el renderizado del formulario de respuestas en el detalle de una
pregunta, la visibilidad exclusiva del botón ``Marcar como aceptada`` para el
autor de la pregunta, la creación de respuestas vía POST, el cambio de
solución aceptada y el control de acceso ante usuarios anónimos o no autores.
"""

import pytest

from qa_platform.models import AIAgent, Answer, Category, GeneralUser, Question

# ---------------------------------------------------------------------------
# Helpers y fixtures locales
# ---------------------------------------------------------------------------


def _login(client, user) -> None:
    """Simula una sesión activa en Flask para el usuario indicado."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def question_author(db):
    """Crea y persiste el usuario autor de la pregunta."""
    user = GeneralUser(
        username="q_owner",
        email="q_owner@example.com",
        display_name="Dueño Pregunta",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def other_user(db):
    """Crea y persiste otro usuario registrado distinto al autor."""
    user = GeneralUser(
        username="responder",
        email="responder@example.com",
        display_name="Compañero",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def ai_agent(db):
    """Crea y persiste un agente IA de prueba."""
    agent = AIAgent(
        bot_identifier="qa-assistant",
        display_name="Asistente LLM",
        version="1.0.0",
    )
    db.session.add(agent)
    db.session.commit()
    return agent


@pytest.fixture()
def category(db):
    """Crea y persiste una categoría de prueba."""
    cat = Category(name="Flask", slug="flask", description="Framework Flask")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def question(db, question_author, category):
    """Crea y persiste una pregunta de prueba asociada a ``question_author``."""
    q = Question(
        title="¿Cómo registrar Blueprints en Flask?",
        slug="como-registrar-blueprints-flask",
        body="Quiero modularizar las rutas web usando Application Factory.",
        user_id=question_author.id,
        category_id=category.id,
    )
    db.session.add(q)
    db.session.commit()
    return q


# ---------------------------------------------------------------------------
# Tests de renderizado en vista de detalle
# ---------------------------------------------------------------------------


class TestAnswerDetailRendering:
    """Pruebas de visibilidad de formulario, respuestas y botón de aceptación."""

    def test_detail_shows_answer_form_for_authenticated_user(
        self, client, question, other_user
    ):
        """Un usuario logueado ve el formulario POST para publicar respuestas."""
        _login(client, other_user)
        response = client.get(f"/questions/{question.slug}")
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert f'action="/questions/{question.slug}/answers"' in html
        assert 'method="post"' in html
        assert "Publicar respuesta" in html

    def test_detail_hides_form_and_shows_login_prompt_for_anonymous(
        self, client, question
    ):
        """Un visitante anónimo ve el aviso para iniciar sesión y no el form."""
        response = client.get(f"/questions/{question.slug}")
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "/auth/login" in html
        assert f'action="/questions/{question.slug}/answers"' not in html

    def test_accept_button_visible_only_to_question_author(
        self, client, db, question, question_author, other_user
    ):
        """El botón 'Marcar como aceptada' solo aparece para el autor."""
        answer = Answer(
            body="Registrá el blueprint dentro de create_app().",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        # Visitante anónimo: no debe ver el botón.
        anon_html = client.get(f"/questions/{question.slug}").get_data(as_text=True)
        assert "Marcar como aceptada" not in anon_html

        # Usuario logueado que NO es autor de la pregunta: no debe ver el botón.
        _login(client, other_user)
        other_html = client.get(f"/questions/{question.slug}").get_data(as_text=True)
        assert "Marcar como aceptada" not in other_html

        # Autor de la pregunta: sí debe ver el botón con la acción POST.
        _login(client, question_author)
        author_html = client.get(f"/questions/{question.slug}").get_data(as_text=True)
        assert "Marcar como aceptada" in author_html
        assert f'action="/answers/{answer.id}/accept"' in author_html

    def test_accepted_answer_shown_first_with_badge_and_without_accept_button(
        self, client, db, question, question_author, other_user
    ):
        """La respuesta aceptada se muestra primero con badge y sin botón duplicado."""
        first = Answer(
            body="Primera respuesta sin aceptar.",
            question=question,
            author=other_user,
        )
        second = Answer(
            body="Segunda respuesta aceptada por el autor.",
            question=question,
            author=other_user,
            is_accepted=True,
        )
        db.session.add_all([first, second])
        db.session.commit()

        _login(client, question_author)
        html = client.get(f"/questions/{question.slug}").get_data(as_text=True)

        assert "Solución aceptada" in html
        assert html.index("Segunda respuesta aceptada") < html.index(
            "Primera respuesta sin aceptar"
        )
        assert f'action="/answers/{second.id}/accept"' not in html
        assert f'action="/answers/{first.id}/accept"' in html

    def test_ai_agent_answer_displays_ai_badge(self, client, db, question, ai_agent):
        """Las respuestas generadas por AIAgent muestran el distintivo IA."""
        bot_answer = Answer(
            body="Podés usar app.register_blueprint(mi_bp).",
            question=question,
            author=ai_agent,
        )
        db.session.add(bot_answer)
        db.session.commit()

        html = client.get(f"/questions/{question.slug}").get_data(as_text=True)
        assert "Asistente LLM" in html
        assert "badge-ai" in html


# ---------------------------------------------------------------------------
# Tests de publicación de respuestas (POST /questions/<slug>/answers)
# ---------------------------------------------------------------------------


class TestCreateAnswerRoute:
    """Pruebas del endpoint POST para publicar respuestas."""

    def test_post_answer_persists_and_redirects_to_detail(
        self, client, db, question, other_user
    ):
        """Un POST válido persiste la respuesta, redirige y la muestra en HTML."""
        _login(client, other_user)
        response = client.post(
            f"/questions/{question.slug}/answers",
            data={"body": "Usá Blueprint y registralo en create_app()."},
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "Respuesta publicada exitosamente." in html
        assert "Usá Blueprint y registralo en create_app()." in html

        saved = db.session.scalar(db.select(Answer).filter_by(question_id=question.id))
        assert saved is not None
        assert saved.author_id == other_user.id
        assert saved.is_accepted is False

    def test_post_empty_answer_returns_400_and_does_not_persist(
        self, client, db, question, other_user
    ):
        """Enviar un cuerpo vacío devuelve HTTP 400 y no guarda nada en BD."""
        _login(client, other_user)
        response = client.post(
            f"/questions/{question.slug}/answers",
            data={"body": "   "},
        )
        html = response.get_data(as_text=True)

        assert response.status_code == 400
        assert "El contenido de la respuesta es obligatorio." in html
        assert question.answers.count() == 0

    def test_post_answer_unauthenticated_redirects_to_login(self, client, db, question):
        """Un usuario anónimo es redirigido al login y no puede publicar."""
        response = client.post(
            f"/questions/{question.slug}/answers",
            data={"body": "Intento sin sesión."},
        )

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]
        assert question.answers.count() == 0

    def test_post_answer_unknown_question_returns_404(self, client, other_user):
        """Responder una pregunta inexistente devuelve HTTP 404."""
        _login(client, other_user)
        response = client.post(
            "/questions/pregunta-inexistente/answers",
            data={"body": "Respuesta huérfana."},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de marcación de respuesta aceptada (POST /answers/<id>/accept)
# ---------------------------------------------------------------------------


class TestAcceptAnswerRoute:
    """Pruebas del endpoint POST para marcar una respuesta como aceptada."""

    def test_question_author_can_accept_answer_and_ui_updates(
        self, client, db, question, question_author, other_user
    ):
        """El autor de la pregunta marca la respuesta y la vista se actualiza."""
        answer = Answer(
            body="Solución definitiva.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        _login(client, question_author)
        response = client.post(
            f"/answers/{answer.id}/accept",
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "Respuesta marcada como solución aceptada." in html
        assert "Solución aceptada" in html

        db.session.expire_all()
        reloaded = db.session.get(Answer, answer.id)
        assert reloaded is not None
        assert reloaded.is_accepted is True

    def test_accepting_another_answer_switches_accepted_solution(
        self, client, db, question, question_author, other_user
    ):
        """Aceptar otra respuesta desmarca la solución previamente aceptada."""
        a1 = Answer(
            body="Primera solución.",
            question=question,
            author=other_user,
            is_accepted=True,
        )
        a2 = Answer(
            body="Mejor solución.",
            question=question,
            author=other_user,
        )
        db.session.add_all([a1, a2])
        db.session.commit()

        _login(client, question_author)
        response = client.post(f"/answers/{a2.id}/accept")
        assert response.status_code == 302

        db.session.expire_all()
        assert db.session.get(Answer, a1.id).is_accepted is False
        assert db.session.get(Answer, a2.id).is_accepted is True

    def test_non_author_cannot_accept_answer_returns_403(
        self, client, db, question, other_user
    ):
        """Otro usuario distinto al autor de la pregunta recibe HTTP 403."""
        answer = Answer(
            body="Respuesta ajena.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        _login(client, other_user)
        response = client.post(f"/answers/{answer.id}/accept")

        assert response.status_code == 403
        db.session.expire_all()
        assert db.session.get(Answer, answer.id).is_accepted is False

    def test_unauthenticated_cannot_accept_answer_redirects_to_login(
        self, client, db, question, other_user
    ):
        """Un usuario anónimo es redirigido al login sin modificar el estado."""
        answer = Answer(
            body="Respuesta protegida.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        response = client.post(f"/answers/{answer.id}/accept")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]
        db.session.expire_all()
        assert db.session.get(Answer, answer.id).is_accepted is False

    def test_accept_unknown_answer_returns_404(self, client, question_author):
        """Intentar aceptar una respuesta inexistente devuelve HTTP 404."""
        _login(client, question_author)
        response = client.post("/answers/99999/accept")
        assert response.status_code == 404
