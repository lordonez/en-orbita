from unittest.mock import patch

from fastapi import status


def test_missing_api_key_returns_401(client):
    """Verifica que omitir el encabezado X-API-Key rechace la solicitud con HTTP 401."""
    with patch("app.services.jpl_service.httpx.AsyncClient.get") as mock_jpl:
        response = client.post(
            "/scripts/generate",
            json={
                "start_date": "2026-09-10",
                "end_date": "2026-09-20",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "X-API-Key" in response.json()["detail"]
        # Asegurar que NO se realizaron llamadas externas a JPL
        mock_jpl.assert_not_called()


def test_invalid_api_key_returns_401(client):
    """Verifica que proveer una X-API-Key incorrecta rechace la solicitud con HTTP 401."""
    with patch("app.services.jpl_service.httpx.AsyncClient.get") as mock_jpl:
        response = client.post(
            "/scripts/generate",
            headers={"X-API-Key": "clave-incorrecta-123"},
            json={
                "start_date": "2026-09-10",
                "end_date": "2026-09-20",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_jpl.assert_not_called()
