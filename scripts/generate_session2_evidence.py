import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.jpl_service import fetch_and_normalize_jpl_cad


async def generate_evidence_session2() -> None:
    """Ejecuta una consulta real a la API JPL CAD y guarda la evidencia completa en evidencias/sesion-02/."""
    print("=== Generando Evidencia de Sesión 2 (Consulta Real a JPL CAD API) ===")

    start_date = date(2026, 9, 8)
    end_date = date(2026, 9, 30)

    start_time = datetime.now(timezone.utc).isoformat()
    event, source_info, factual_card, duration_ms = await fetch_and_normalize_jpl_cad(start_date, end_date)

    evidence_data = {
        "metadata": {
            "session": "Sesión 2: Contrato y Consulta Real JPL",
            "timestamp_utc": start_time,
            "environment": {
                "python_version": "3.13.0",
                "aws_profile": settings.AWS_PROFILE,
                "aws_region": settings.AWS_REGION,
            },
            "query_parameters": source_info.query_params,
            "jpl_duration_ms": duration_ms,
        },
        "source_info": source_info.model_dump(mode="json"),
        "normalized_event": event.model_dump(mode="json") if event else None,
        "factual_card": factual_card,
    }

    output_dir = Path("evidencias/sesion-02")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "consulta_jpl_real.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, ensure_ascii=False, indent=2)

    print(f"Evidencia guardada exitosamente en {output_file.resolve()}")
    if event:
        print(f"Objeto seleccionado: {event.object_fullname}")
        print(f"Distancia nominal: {event.dist_au} AU ({event.dist_km:,.2f} km / {event.dist_ld} LD)")
        print(f"Fecha TDB: {event.cd_date_str}")
    else:
        print("No se encontraron eventos coincidentes.")


if __name__ == "__main__":
    asyncio.run(generate_evidence_session2())
