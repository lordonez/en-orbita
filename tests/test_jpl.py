from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.jpl_service import fetch_and_normalize_jpl_cad


@pytest.mark.asyncio
async def test_jpl_normalization_success():
    """Prueba la normalización correcta de respuestas válidas de JPL CAD."""
    mock_jpl_response = {
        "signature": {"version": "1.2"},
        "count": "1",
        "fields": ["des", "cd", "dist", "v_rel", "v_inf", "h", "fullname"],
        "data": [["2026 AB", "2026-Sep-15 12:30", "0.012345", "14.5", "14.2", "24.1", "(2026 AB)"]],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: mock_jpl_response

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        event, source_info, factual_card, duration_ms = await fetch_and_normalize_jpl_cad(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 20),
        )

        assert event is not None
        assert event.object_fullname == "(2026 AB)"
        assert event.cd_date_str == "2026-Sep-15 12:30 TDB"
        assert event.dist_au == 0.012345
        assert event.dist_km == round(0.012345 * 149_597_870.7, 2)
        assert event.dist_ld == round((0.012345 * 149_597_870.7) / 384_400.0, 2)
        assert event.v_rel_kms == 14.5
        assert event.h_mag == 24.1
        assert factual_card["objeto"] == "(2026 AB)"
        assert duration_ms >= 0.0


@pytest.mark.asyncio
async def test_jpl_zero_events():
    """Prueba el comportamiento cuando JPL retorna 0 eventos coincidentes."""
    mock_jpl_response = {
        "signature": {"version": "1.2"},
        "count": "0",
        "fields": ["des", "cd", "dist"],
        "data": [],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: mock_jpl_response

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        event, source_info, factual_card, duration_ms = await fetch_and_normalize_jpl_cad(
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 20),
        )

        assert event is None
        assert factual_card is None
        assert source_info.provider == "NASA/JPL SBDB Close-Approach Data API"
        assert duration_ms >= 0.0
