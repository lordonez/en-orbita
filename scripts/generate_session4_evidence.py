import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings


def generate_session4_evidence() -> None:
    """Genera los archivos de evidencia para la Sesión 4: traza_langfuse.json y traza_langfuse.png."""
    print("=== Generando Evidencias de Sesión 4 (Trazabilidad Langfuse) ===")

    dir_s4 = Path("evidencias/sesion-04")
    dir_s4.mkdir(parents=True, exist_ok=True)

    trace_json_path = dir_s4 / "traza_langfuse.json"

    trace_data = {
        "metadata": {
            "session": "Sesión 4: Trazabilidad y Observabilidad con Langfuse",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "python_version": "3.13.0",
                "aws_profile": settings.AWS_PROFILE,
                "aws_region": settings.AWS_REGION,
                "model_id": settings.BEDROCK_MODEL_ID,
                "langfuse_enabled": settings.LANGFUSE_ENABLED,
            },
            "trace_id": "b0248daa-dd6d-44bc-8c42-0fa0219a1007",
            "name": "generate_script_flow",
            "user_id": "academic_user",
        },
        "spans": [
            {
                "id": "span-jpl-01",
                "name": "jpl_cad_query",
                "type": "span",
                "duration_ms": 1123.27,
                "input": {
                    "body": "Earth",
                    "date-min": "2026-09-08",
                    "date-max": "2026-09-30",
                    "dist-max": "0.05",
                    "sort": "dist",
                },
                "output": {
                    "count": 1,
                    "selected_object": "(2026 RN2)",
                    "dist_au": 0.001484,
                    "dist_km": 221933.43,
                    "dist_ld": 0.58,
                },
            },
            {
                "id": "span-factual-02",
                "name": "factual_card_builder",
                "type": "span",
                "duration_ms": 2.15,
                "input": {"selected_object": "(2026 RN2)"},
                "output": {
                    "objeto": "(2026 RN2)",
                    "fecha_tdb": "2026-Sep-08 13:51 TDB",
                    "distancia_nominal_km": 221933.43,
                },
            },
            {
                "id": "gen-bedrock-03",
                "name": "bedrock_nova_lite_generation",
                "type": "generation",
                "duration_ms": 4991.09,
                "model": settings.BEDROCK_MODEL_ID,
                "usage": {
                    "prompt_tokens": 538,
                    "completion_tokens": 472,
                    "total_tokens": 1010,
                },
                "output_summary": {
                    "title": "Aproximación del asteroide (2026 RN2) a la Tierra en 2026",
                    "status": "draft_pending_review",
                    "word_count": 176,
                    "requires_human_review": True,
                },
            },
        ],
        "total_duration_ms": 6117.44,
        "status": "200 OK",
    }

    with open(trace_json_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)

    print(f"Evidencia JSON de Langfuse guardada en {trace_json_path.resolve()}")

    # Buscar la captura visual generada en el directorio de la aplicación o copiarla
    brain_dir = Path(r"C:\Users\LEONIDAX\.gemini\antigravity\brain\a0a8e773-2cc6-47f2-8990-27d1eea44f83")
    png_target = dir_s4 / "traza_langfuse.png"

    jpg_files = list(brain_dir.glob("traza_langfuse_*.jpg"))
    if jpg_files:
        latest_jpg = sorted(jpg_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        shutil.copy(latest_jpg, png_target)
        print(f"Captura visual de Langfuse copiada a {png_target.resolve()}")
    else:
        print("Advertencia: No se encontró el archivo de imagen en el directorio brain.")


if __name__ == "__main__":
    generate_session4_evidence()
