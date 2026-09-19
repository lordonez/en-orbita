import json
from pathlib import Path
from typing import Any, Tuple

from fastapi import HTTPException, status

from app.schemas.response import NormalizedEvent, SourceInfo

FIXTURES_DIR = Path(__file__).parent / "jpl"


def load_jpl_fixture(fixture_filename: str) -> dict[str, Any]:
    """Carga un archivo JSON de fixture JPL desde disk."""
    file_path = FIXTURES_DIR / fixture_filename
    if not file_path.exists():
        raise FileNotFoundError(f"Fixture JPL no encontrado: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def execute_jpl_provider_scenario(
    provider_scenario: str | None,
    jpl_fixture_file: str | None,
) -> Tuple[NormalizedEvent | None, SourceInfo, dict[str, Any] | None, float]:
    """Simula u orquesta la respuesta de JPL según el escenario especificado por la prueba o evaluación.

    Escenarios soportados:
    - 'return_fixture' (o jpl_fixture_file especificado): Retorna datos cargados del fixture.
    - 'raise_timeout': Eleva HTTP 504 Gateway Timeout.
    - 'raise_http_error': Eleva HTTP 502 Bad Gateway.
    - 'return_malformed_payload': Carga malformed.json o eleva HTTP 502.
    - 'return_incomplete_payload': Carga incomplete.json.
    - None o 'real': Ejecuta la llamada viva (solo cuando se autoriza).
    """
    scenario = provider_scenario or "return_fixture"

    if scenario == "raise_timeout":
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout de conexión al consultar la API de NASA/JPL CAD.",
        )

    if scenario in ("raise_http_error", "provider_error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fallo en la comunicación con la API de NASA/JPL CAD.",
        )

    # Si es fixture o escenario de carga
    fixture_file = jpl_fixture_file
    if not fixture_file:
        if scenario == "return_malformed_payload":
            fixture_file = "malformed.json"
        elif scenario == "return_incomplete_payload":
            fixture_file = "incomplete.json"
        else:
            fixture_file = "normal.json"

    raw_data = load_jpl_fixture(fixture_file)

    # Normalizar usando la misma lógica que el servicio de aplicación
    source_info = SourceInfo(
        provider="NASA/JPL SBDB Close-Approach Data API (FIXTURE)",
        endpoint="https://ssd-api.jpl.nasa.gov/cad.api",
        query_params={"fixture": fixture_file},
        retrieved_at="2026-09-17T12:00:00Z",
    )

    fields = raw_data.get("fields", [])
    count = int(raw_data.get("count", 0)) if isinstance(raw_data.get("count"), (str, int)) else 0
    rows = raw_data.get("data", [])

    if count == 0 or not rows or not fields:
        return None, source_info, None, 5.0

    field_map = {name: idx for idx, name in enumerate(fields)}
    best_row = rows[0]

    def safe_get(field_name: str, default: Any = None) -> Any:
        idx = field_map.get(field_name)
        if idx is not None and idx < len(best_row):
            val = best_row[idx]
            return val if val is not None else default
        return default

    des = str(safe_get("des", "Objeto espacial")).strip()
    fullname = str(safe_get("fullname", des)).strip()
    cd_date = str(safe_get("cd", "Fecha no especificada")).strip()

    try:
        dist_au = float(safe_get("dist", 0.0))
    except (ValueError, TypeError):
        dist_au = 0.0

    try:
        v_rel = float(safe_get("v_rel", 0.0))
    except (ValueError, TypeError):
        v_rel = 0.0

    v_inf_val = safe_get("v_inf")
    try:
        v_inf = float(v_inf_val) if v_inf_val is not None else None
    except (ValueError, TypeError):
        v_inf = None

    h_val = safe_get("h")
    try:
        h_mag = float(h_val) if h_val is not None else None
    except (ValueError, TypeError):
        h_mag = None

    KM_PER_AU = 149_597_870.7
    KM_PER_LD = 384_400.0

    dist_km = round(dist_au * KM_PER_AU, 2)
    dist_ld = round((dist_au * KM_PER_AU) / KM_PER_LD, 2)

    normalized_event = NormalizedEvent(
        object_fullname=fullname,
        cd_date_str=f"{cd_date} TDB",
        dist_au=round(dist_au, 6),
        dist_km=dist_km,
        dist_ld=dist_ld,
        v_rel_kms=round(v_rel, 2),
        v_inf_kms=round(v_inf, 2) if v_inf is not None else None,
        h_mag=round(h_mag, 2) if h_mag is not None else None,
    )

    factual_card: dict[str, Any] = {
        "objeto": normalized_event.object_fullname,
        "fecha_aproximacion_tdb": normalized_event.cd_date_str,
        "distancia_nominal_au": normalized_event.dist_au,
        "distancia_nominal_km": normalized_event.dist_km,
        "distancia_nominal_ld": normalized_event.dist_ld,
        "velocidad_relativa_kms": normalized_event.v_rel_kms,
        "velocidad_infinito_kms": normalized_event.v_inf_kms,
        "magnitud_absoluta_h": normalized_event.h_mag,
        "cuerpo_central": "Tierra",
        "escala_tiempo": "TDB (Barycentric Dynamical Time - JPL)",
        "fuente": "NASA/JPL Small-Body Database Close-Approach Data API (FIXTURE)",
    }

    return normalized_event, source_info, factual_card, 5.0
