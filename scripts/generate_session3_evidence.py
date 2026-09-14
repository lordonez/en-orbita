import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def generate_session3_evidences() -> None:
    """Genera las evidencias reales para la Sesión 3: respuesta completa Bedrock y 3 mediciones reales."""
    print("=== Generando Evidencias de Sesión 3 (Respuesta Bedrock Real & 3 Mediciones) ===")

    client = TestClient(app)
    headers = {"X-API-Key": settings.APP_API_KEY}

    payload = {
        "start_date": "2026-09-08",
        "end_date": "2026-09-30",
        "video_format": "news_brief",
        "duration_seconds": 90,
        "target_audience": "general",
        "tone": "informative",
    }

    # 1. Generar respuesta real completa de Bedrock
    print("\n--- Ejecutando solicitud real a Amazon Bedrock Nova Lite ---")
    response1 = client.post("/scripts/generate", headers=headers, json=payload)
    assert response1.status_code == 200, f"Error HTTP: {response1.text}"

    data1 = response1.json()

    evidence_bedrock = {
        "metadata": {
            "session": "Sesión 3: Flujo JPL -> Bedrock Nova Lite",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "python_version": "3.13.0",
                "aws_profile": settings.AWS_PROFILE,
                "aws_region": settings.AWS_REGION,
                "model_id": settings.BEDROCK_MODEL_ID,
            },
            "input_payload": payload,
            "http_status": response1.status_code,
        },
        "response": data1,
    }

    dir_s3 = Path("evidencias/sesion-03")
    dir_s3.mkdir(parents=True, exist_ok=True)
    file_bedrock = dir_s3 / "respuesta_bedrock_real.json"

    with open(file_bedrock, "w", encoding="utf-8") as f:
        json.dump(evidence_bedrock, f, ensure_ascii=False, indent=2)

    print(f"Respuesta real de Bedrock guardada en {file_bedrock.resolve()}")
    print(f"Título del guion: '{data1['script']['title']}'")
    print(f"Palabras: {data1['word_count']} | Duración estimada: {data1['estimated_duration_seconds']}s")
    print(f"Revisión humana obligatoria: {data1['requires_human_review']}")

    # 2. Ejecutar 3 mediciones reales consecutivas de la misma solicitud con reloj monotónico
    print("\n--- Ejecutando 3 mediciones reales de latencia desde el cliente ---")
    runs = []

    for i in range(1, 4):
        print(f"Ejecutando medición {i}/3...")
        start_client_mono = time.monotonic()
        resp = client.post("/scripts/generate", headers=headers, json=payload)
        client_duration_ms = round((time.monotonic() - start_client_mono) * 1000, 2)
        assert resp.status_code == 200, f"Fallo en medición {i}: {resp.text}"
        res_json = resp.json()

        runs.append(
            {
                "run_index": i,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "client_latency_ms": client_duration_ms,
                "request_id": res_json["request_id"],
                "status": res_json["status"],
                "word_count": res_json["word_count"],
                "estimated_duration_seconds": res_json["estimated_duration_seconds"],
                "selected_object": res_json["selected_event"]["object_fullname"]
                if res_json.get("selected_event")
                else None,
            }
        )
        time.sleep(0.5)

    client_latencies = [r["client_latency_ms"] for r in runs]
    mean_latency = round(sum(client_latencies) / len(client_latencies), 2)
    min_latency = min(client_latencies)
    max_latency = max(client_latencies)

    evidence_mediciones = {
        "metadata": {
            "session": "Sesión 3: Protocolo Oficial de 3 Mediciones Reales",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "environment": {
                "python_version": "3.13.0",
                "aws_profile": settings.AWS_PROFILE,
                "aws_region": settings.AWS_REGION,
                "model_id": settings.BEDROCK_MODEL_ID,
            },
            "fixed_input": payload,
            "total_runs": 3,
            "client_timer_type": "time.monotonic()",
            "streaming_used": False,
            "streaming_justification": (
                "Se requiere recibir y validar la estructura JSON completa mediante Pydantic "
                "antes de retornar el guion estructurado al cliente."
            ),
        },
        "summary": {
            "mean_client_latency_ms": mean_latency,
            "min_client_latency_ms": min_latency,
            "max_client_latency_ms": max_latency,
            "successful_runs": 3,
            "failed_runs": 0,
        },
        "runs": runs,
    }

    file_mediciones = dir_s3 / "mediciones_sesion3.json"
    with open(file_mediciones, "w", encoding="utf-8") as f:
        json.dump(evidence_mediciones, f, ensure_ascii=False, indent=2)

    print(f"Mediciones guardadas exitosamente en {file_mediciones.resolve()}")
    print(
        f"Resumen Latencias Cliente (3 ejecuciones): Media={mean_latency}ms | Mín={min_latency}ms | Máx={max_latency}ms"
    )


if __name__ == "__main__":
    generate_session3_evidences()
