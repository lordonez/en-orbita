import time
from datetime import date, datetime, timezone
from typing import Any, Tuple

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.logger import logger
from app.schemas.response import NormalizedEvent, SourceInfo

# Constantes de conversión de unidades astronómicas
KM_PER_AU = 149_597_870.7  # Kilómetros por Unidad Astronómica (IAU 2012)
KM_PER_LD = 384_400.0  # Kilómetros promedio por Distancia Lunar


class JPLServiceError(Exception):
    """Excepción para errores al consultar la API de NASA/JPL CAD."""

    pass


async def fetch_and_normalize_jpl_cad(
    start_date: date,
    end_date: date,
) -> Tuple[NormalizedEvent | None, SourceInfo, dict[str, Any] | None, float]:
    """Consulta la API de Aproximaciones Cercanas (CAD) de NASA/JPL para la Tierra.

    - Filtra explícitamente por `body=Earth` y `dist-max=0.05` AU.
    - Ordena por `dist` (distancia nominal mínima) y limita a 10 resultados.
    - Normaliza datos conservando unidades oficiales y escala de tiempo TDB (JPL).
    - Selecciona determinísticamente el evento con menor distancia nominal.
    """
    params = {
        "date-min": start_date.isoformat(),
        "date-max": end_date.isoformat(),
        "body": "Earth",
        "dist-max": "0.05",  # Filtro explícito de distancia máxima (~7.48 millones de km)
        "sort": "dist",  # Ordenar determinísticamente por menor distancia nominal
        "limit": "10",  # Límite pequeño de resultados
        "fullname": "true",  # Solicitar nombre/designación completa
    }

    retrieved_at = datetime.now(timezone.utc).isoformat()
    source_info = SourceInfo(
        provider="NASA/JPL SBDB Close-Approach Data API",
        endpoint=settings.JPL_CAD_API_URL,
        query_params=params,
        retrieved_at=retrieved_at,
    )

    start_mono = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=settings.JPL_TIMEOUT_SECONDS) as client:
            response = await client.get(settings.JPL_CAD_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        duration_ms = round((time.monotonic() - start_mono) * 1000, 2)
        logger.error(
            "Timeout al consultar NASA/JPL CAD API",
            extra={"extra_data": {"jpl_duration_ms": duration_ms, "error": str(exc)}},
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout de conexión al consultar la API de NASA/JPL CAD.",
        ) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        duration_ms = round((time.monotonic() - start_mono) * 1000, 2)
        logger.error(
            "Error al consultar NASA/JPL CAD API",
            extra={"extra_data": {"jpl_duration_ms": duration_ms, "error": str(exc)}},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fallo en la comunicación con la API de NASA/JPL CAD.",
        ) from exc

    jpl_duration_ms = round((time.monotonic() - start_mono) * 1000, 2)

    # Validar estructura devuelta por JPL
    fields = data.get("fields", [])
    count = int(data.get("count", 0))
    rows = data.get("data", [])

    if count == 0 or not rows or not fields:
        logger.info(
            "Consulta JPL CAD sin eventos coincidentes en el intervalo",
            extra={"extra_data": {"jpl_duration_ms": jpl_duration_ms, "count": 0}},
        )
        return None, source_info, None, jpl_duration_ms

    # Crear mapeo dinámico de nombres de columnas a índices de la fila
    field_map = {name: idx for idx, name in enumerate(fields)}

    # Seleccionar determinísticamente la primera fila (ya ordenada por 'dist' ascendente en la API)
    best_row = rows[0]

    def safe_get(field_name: str, default: Any = None) -> Any:
        idx = field_map.get(field_name)
        if idx is not None and idx < len(best_row):
            val = best_row[idx]
            return val if val is not None else default
        return default

    # Extraer y limpiar campos
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

    # Conversión determinista de unidades en código
    dist_km = round(dist_au * KM_PER_AU, 2)
    dist_ld = round((dist_au * KM_PER_AU) / KM_PER_LD, 2)

    normalized_event = NormalizedEvent(
        object_fullname=fullname,
        cd_date_str=f"{cd_date} TDB",  # Especificar explícitamente escala TDB (Barycentric Dynamical Time)
        dist_au=round(dist_au, 6),
        dist_km=dist_km,
        dist_ld=dist_ld,
        v_rel_kms=round(v_rel, 2),
        v_inf_kms=round(v_inf, 2) if v_inf is not None else None,
        h_mag=round(h_mag, 2) if h_mag is not None else None,
    )

    # Construir ficha factual rigurosa sin inferencias no sustentadas
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
        "fuente": "NASA/JPL Small-Body Database Close-Approach Data API",
    }

    return normalized_event, source_info, factual_card, jpl_duration_ms
