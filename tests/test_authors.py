"""Pruebas unitarias y de integración para la jerarquía Author y Factory Method."""

import pytest
from sqlalchemy.exc import IntegrityError

from qa_platform.factories import AIAgentFactory, AuthorFactory, UserFactory
from qa_platform.models import Admin, AIAgent, Author, GeneralUser, User


class _DummyLLMStrategy:
    """Stub mínimo para probar la inyección de estrategias en AIAgent."""

    def __init__(self, provider_name: str = "MockProvider") -> None:
        self._provider_name = provider_name

    def get_provider_name(self) -> str:
        return self._provider_name


class TestAuthorPolymorphism:
    """Pruebas para la jerarquía polimórfica Author con Single Table Inheritance."""

    def test_cannot_instantiate_abstract_author_directly(self):
        """Author no debe poder instanciarse directamente."""
        with pytest.raises(TypeError):
            Author(display_name="Abstracto")

    def test_single_table_inheritance_polymorphic_queries(self, db):
        """Persistir subclases en 'authors' y recuperarlas con su tipo concreto."""
        user = User(
            username="base_user",
            email="base@example.com",
            display_name="Usuario Base",
        )
        general = GeneralUser(
            username="student_1",
            email="student@example.com",
            display_name="Estudiante Uno",
            academic_level="Grado",
        )
        admin = Admin(
            username="admin_1",
            email="admin@example.com",
            display_name="Administrador",
            special_permissions="moderate_all",
        )
        agent = AIAgent(
            bot_identifier="qa-bot-v1",
            display_name="Asistente IA",
            version="1.2.0",
            system_prompt="Responde con claridad académica.",
        )

        db.session.add_all([user, general, admin, agent])
        db.session.commit()
        db.session.expire_all()

        all_authors = db.session.scalars(db.select(Author).order_by(Author.id)).all()
        assert [type(a) for a in all_authors] == [
            User,
            GeneralUser,
            Admin,
            AIAgent,
        ]

        human_users = db.session.scalars(db.select(User).order_by(User.id)).all()
        assert len(human_users) == 3
        assert all(not u.is_agent() for u in human_users)

        agents = db.session.scalars(db.select(AIAgent)).all()
        assert len(agents) == 1
        assert agents[0].is_agent() is True
        assert agents[0].bot_identifier == "qa-bot-v1"

    def test_polymorphic_contract_methods(self):
        """Los métodos base de Author responden de forma polimórfica."""
        general = GeneralUser(
            username="isaias",
            email="isaias@example.com",
            display_name="Isaías",
        )
        admin = Admin(
            username="mod_juan",
            email="juan@example.com",
            display_name="Juan Admin",
        )
        agent = AIAgent(
            bot_identifier="gemini-helper",
            display_name="Gemini Helper",
        )

        authors: list[Author] = [general, admin, agent]

        assert [a.is_agent() for a in authors] == [False, False, True]
        assert [a.get_identifier() for a in authors] == [
            "isaias",
            "mod_juan",
            "gemini-helper",
        ]
        assert [a.get_display_name() for a in authors] == [
            "Isaías",
            "Juan Admin",
            "Gemini Helper",
        ]

    def test_password_hashing_and_verification(self):
        """La contraseña se guarda hasheada y se verifica de forma segura."""
        user = GeneralUser(
            username="secure_user",
            email="secure@example.com",
            password="MiClaveSegura123",
        )

        assert user.password_hash is not None
        assert user.password_hash != "MiClaveSegura123"
        assert user.check_password("MiClaveSegura123") is True
        assert user.check_password("incorrecta") is False
        assert user.check_password("") is False

        with pytest.raises(ValueError):
            user.set_password("   ")

    def test_user_reputation_and_role_methods(self):
        """Prueba actualización de reputación, nivel académico y moderación."""
        general = GeneralUser(
            username="joaquin",
            email="joaquin@example.com",
            academic_level="Posgrado",
        )
        assert general.reputation == 0
        assert general.update_reputation(10) == 10
        assert general.update_reputation(-3) == 7
        assert general.get_academic_level() == "Posgrado"

        admin = Admin(
            username="root_admin",
            email="root@example.com",
            special_permissions="delete_any",
        )
        result = admin.moderate_content("delete_question", target_id=42)
        assert result == {
            "moderator": "root_admin",
            "action": "delete_question",
            "target_id": 42,
            "authorized": True,
        }

        with pytest.raises(ValueError):
            admin.moderate_content("   ")

    def test_multiple_ai_agents_coexist_and_bot_identifier_is_unique(self, db):
        """Múltiples agentes sin email/username coexisten; bot_identifier es único."""
        bot_a = AIAgent(bot_identifier="bot-alpha", display_name="Bot Alpha")
        bot_b = AIAgent(bot_identifier="bot-beta", display_name="Bot Beta")
        db.session.add_all([bot_a, bot_b])
        db.session.commit()

        duplicate = AIAgent(bot_identifier="bot-alpha", display_name="Bot Duplicado")
        db.session.add(duplicate)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_ai_agent_strategy_injection_and_reload(self, db):
        """AIAgent soporta inyección y cambio de estrategia incluso tras recarga DB."""
        strategy = _DummyLLMStrategy("OpenAI")
        agent = AIAgent(
            bot_identifier="bot-strategy",
            display_name="Bot Estrategia",
            strategy=strategy,
        )
        assert agent.get_current_strategy() == "OpenAI"
        assert "bot-strategy" in repr(agent)

        db.session.add(agent)
        db.session.commit()
        agent_id = agent.id
        # expunge_all() limpia el identity map para forzar una nueva hidratación
        # desde DB (sin pasar por __init__), validando @orm.reconstructor.
        db.session.expunge_all()

        reloaded = db.session.get(AIAgent, agent_id)
        assert reloaded is not None
        assert reloaded is not agent
        assert reloaded.get_current_strategy() is None

        reloaded.set_strategy(_DummyLLMStrategy("Gemini"))
        assert reloaded.get_current_strategy() == "Gemini"

    @pytest.mark.parametrize(
        ("factory_fn", "kwargs"),
        [
            (User, {"username": "", "email": "a@example.com"}),
            (User, {"username": "valid", "email": "   "}),
            (AIAgent, {"bot_identifier": ""}),
        ],
    )
    def test_missing_required_identifiers_raise_value_error(self, factory_fn, kwargs):
        """Atributos obligatorios vacíos deben lanzar ValueError."""
        with pytest.raises(ValueError):
            factory_fn(**kwargs)


class TestAuthorFactories:
    """Pruebas unitarias y de integración para el patrón Factory Method."""

    def test_cannot_instantiate_abstract_factory(self):
        """AuthorFactory es abstracta y no puede instanciarse directamente."""
        with pytest.raises(TypeError):
            AuthorFactory()

    def test_user_factory_creates_roles_and_validates_inputs(self):
        """UserFactory instancia GeneralUser, Admin y User y valida entradas."""
        factory = UserFactory()

        general = factory.create_author(
            "ana_dev",
            "Ana",
            email="ana@example.com",
            password="clave",
            academic_level="Grado",
        )
        assert isinstance(general, GeneralUser)
        assert general.check_password("clave") is True
        assert general.get_academic_level() == "Grado"

        admin = factory.create_author(
            "carlos_mod",
            "Carlos",
            email="carlos@example.com",
            role="admin",
            special_permissions="ban_users",
        )
        assert isinstance(admin, Admin)
        assert admin.special_permissions == "ban_users"

        base_user = factory.create_author(
            "simple_user",
            "Simple",
            email="simple@example.com",
            role="user",
        )
        assert type(base_user) is User

        with pytest.raises(ValueError):
            factory.create_author("no_email", "Sin Email")

        with pytest.raises(ValueError):
            factory.create_author(
                "bad_role",
                "Rol Inválido",
                email="bad@example.com",
                role="superadmin",
            )

    def test_user_factory_register_author_persists(self, db):
        """register_author() en UserFactory persiste el usuario en la base."""
        factory = UserFactory()
        created = factory.register_author(
            "persisted_u",
            "Usuario Persistido",
            email="persisted@example.com",
            password="secreto",
        )

        fetched = db.session.get(Author, created.id)
        assert isinstance(fetched, GeneralUser)
        assert fetched.username == "persisted_u"
        assert fetched.check_password("secreto") is True

    def test_ai_agent_factory_strategy_and_persistence(self, db):
        """AIAgentFactory inyecta default_strategy, permite override y persiste."""
        default_strategy = _DummyLLMStrategy("LocalOllama")
        override_strategy = _DummyLLMStrategy("Gemini")
        factory = AIAgentFactory(default_strategy=default_strategy)

        agent_default = factory.create_author("bot-1", "Bot Uno")
        assert isinstance(agent_default, AIAgent)
        assert agent_default.get_current_strategy() == "LocalOllama"

        agent_override = factory.register_author(
            "bot-2",
            "Bot Dos",
            version="2.0.0",
            system_prompt="Ayuda con Python.",
            strategy=override_strategy,
        )
        assert agent_override.id is not None
        assert agent_override.version == "2.0.0"
        assert agent_override.get_current_strategy() == "Gemini"

        fetched = db.session.get(Author, agent_override.id)
        assert isinstance(fetched, AIAgent)
        assert fetched.bot_identifier == "bot-2"

    def test_polymorphic_factory_pipeline(self, db):
        """Las fábricas concretas se usan de forma uniforme como AuthorFactory."""
        factories: list[tuple[AuthorFactory, tuple, dict]] = [
            (
                UserFactory(),
                ("poly_user", "Usuario Polimórfico"),
                {"email": "poly@example.com"},
            ),
            (
                AIAgentFactory(default_strategy=_DummyLLMStrategy("Mock")),
                ("poly_bot", "Bot Polimórfico"),
                {},
            ),
        ]

        created = [
            factory.register_author(*args, **kwargs)
            for factory, args, kwargs in factories
        ]

        assert len(created) == 2
        assert created[0].is_agent() is False
        assert created[1].is_agent() is True
