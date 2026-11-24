"""Pruebas funcionales para el endpoint /health y la factory en modo testing."""


def test_health_returns_ok(client):
    """Verifica que GET /health responde 200 con status ok en JSON."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_health_content_type_is_json(client):
    """Verifica que la respuesta de /health tiene cabecera JSON."""
    response = client.get("/health")

    assert response.is_json
