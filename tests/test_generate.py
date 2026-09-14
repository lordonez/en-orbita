from unittest.mock import AsyncMock, patch

from fastapi import status


def test_invalid_date_range_inverted(client, valid_headers):
    """Verifica rechazo 422 cuando end_date es anterior a start_date."""
    response = client.post(
        "/scripts/generate",
        headers=valid_headers,
        json={
            "start_date": "2026-09-20",
            "end_date": "2026-09-10",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_date_range_exceeds_30_days(client, valid_headers):
    """Verifica rechazo 422 cuando el intervalo supera los 30 días."""
    response = client.post(
        "/scripts/generate",
        headers=valid_headers,
        json={
            "start_date": "2026-09-01",
            "end_date": "2026-10-15",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_invalid_duration_seconds(client, valid_headers):
    """Verifica rechazo 422 cuando la duración está fuera de [30, 180]."""
    response = client.post(
        "/scripts/generate",
        headers=valid_headers,
        json={
            "start_date": "2026-09-01",
            "end_date": "2026-09-15",
            "duration_seconds": 200,
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_generate_flow_no_events(client, valid_headers):
    """Verifica el flujo con status='no_events' cuando no hay aproximaciones."""
    mock_jpl_response = {
        "signature": {"version": "1.2"},
        "count": "0",
        "fields": ["des", "cd", "dist"],
        "data": [],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: mock_jpl_response

    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        patch("app.services.bedrock_service._invoke_bedrock_sync") as mock_bedrock,
    ):
        response = client.post(
            "/scripts/generate",
            headers=valid_headers,
            json={
                "start_date": "2026-09-01",
                "end_date": "2026-09-15",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "no_events"
        assert data["requires_human_review"] is False
        assert data["selected_event"] is None
        assert data["script"] is None
        # Asegurar que el LLM no fue invocado cuando no hay eventos
        mock_bedrock.assert_not_called()


def test_generate_flow_success(client, valid_headers):
    """Verifica el flujo completo exitoso con mock de JPL y Amazon Bedrock."""
    mock_jpl_response = {
        "count": "1",
        "fields": ["des", "cd", "dist", "v_rel", "v_inf", "h", "fullname"],
        "data": [["2026 AB", "2026-Sep-15 12:30", "0.012345", "14.5", "14.2", "24.1", "(2026 AB)"]],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: mock_jpl_response

    mock_bedrock_text = """{
      "title": "Aproximación cercana del asteroide 2026 AB",
      "opening": "Un objeto espacial pasará cerca de nuestro planeta este mes.",
      "development": "El asteroide 2026 AB transitará a una distancia nominal de 0.012 AU de la Tierra a 14.5 km/s.",
      "closure": "Sigue explorando el cosmos con nosotros en En órbita.",
      "visual_proposals": ["Animación 3D de la órbita de 2026 AB pasando junto a la Tierra"],
      "observations": []
    }"""

    mock_usage = {"prompt_tokens": 300, "completion_tokens": 150, "total_tokens": 450}

    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        patch(
            "app.services.bedrock_service._invoke_bedrock_sync",
            return_value=(mock_bedrock_text, mock_usage, 250.0),
        ),
    ):
        response = client.post(
            "/scripts/generate",
            headers=valid_headers,
            json={
                "start_date": "2026-09-01",
                "end_date": "2026-09-15",
                "video_format": "news_brief",
                "duration_seconds": 90,
                "target_audience": "general",
                "tone": "informative",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "draft_pending_review"
        assert data["requires_human_review"] is True
        assert data["selected_event"]["object_fullname"] == "(2026 AB)"
        assert data["script"]["title"] == "Aproximación cercana del asteroide 2026 AB"
        assert data["word_count"] > 0
        assert data["estimated_duration_seconds"] > 0.0
