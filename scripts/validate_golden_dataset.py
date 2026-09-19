"""Script de validación de solo lectura para el Golden Dataset v2 de En órbita."""

import hashlib
import json
import sys
from pathlib import Path

from app.schemas.request import ScriptGenerateRequest
from evaluation.schemas import GoldenCaseRecord

DATASET_PATH = Path("D:/Work/En Orbita/evaluation/datasets/en_orbita_golden_v2.jsonl")
FIXTURES_DIR = Path("D:/Work/En Orbita/evaluation/fixtures/jpl")


def compute_semantic_fingerprint(record: GoldenCaseRecord) -> str:
    """Calcula el fingerprint semántico único de un caso."""
    payload = {
        "request": record.request,
        "auth_scenario": record.auth_scenario,
        "jpl_fixture_file": record.jpl_fixture_file or "none",
        "provider_scenario": record.provider_scenario or "none",
        "expected_http_status": record.expected_http_status,
        "expected_app_status": record.expected_app_status,
        "ground_truth": record.ground_truth.model_dump(),
        "applicable_metrics": sorted(record.applicable_metrics),
        "thresholds": record.thresholds,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_dataset() -> bool:
    print("=" * 65)
    print("VALIDACIÓN DE SOLO LECTURA DEL GOLDEN DATASET V2")
    print("=" * 65)

    if not DATASET_PATH.exists():
        print(f"ERROR: Dataset no encontrado en {DATASET_PATH}")
        sys.exit(1)

    records = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = GoldenCaseRecord.model_validate_json(line_str)
                records.append(rec)
            except Exception as exc:
                print(f"ERROR de esquema Pydantic en línea {idx}: {exc}")
                sys.exit(1)

    print(f"1. Total líneas cargadas y validadas con Pydantic: {len(records)}")
    if len(records) != 100:
        print(f"ERROR: Se esperaban 100 casos, se encontraron {len(records)}")
        sys.exit(1)

    # 2. Comprobar IDs únicos
    ids = [r.id for r in records]
    if len(ids) != len(set(ids)):
        dups = [i for i in ids if ids.count(i) > 1]
        print(f"ERROR: IDs duplicados encontrados: {set(dups)}")
        sys.exit(1)
    print("2. IDs únicos verificados (100 IDs distintos).")

    # 3. Comprobar distribución 40/20/20/20
    categories = [r.category for r in records]
    pos_cnt = categories.count("positive")
    var_cnt = categories.count("boundary_variant")
    err_cnt = categories.count("controlled_error")
    adv_cnt = categories.count("adversarial")

    print(
        f"3. Distribución por categoría: positive={pos_cnt}, boundary_variant={var_cnt}, controlled_error={err_cnt}, adversarial={adv_cnt}"
    )
    if (pos_cnt, var_cnt, err_cnt, adv_cnt) != (40, 20, 20, 20):
        print("ERROR: Distribución de categorías incorrecta.")
        sys.exit(1)

    # 4. Fingerprints semánticos únicos (100)
    fingerprints = [compute_semantic_fingerprint(r) for r in records]
    if len(set(fingerprints)) != 100:
        print(f"ERROR: Fingerprints semánticos duplicados ({len(set(fingerprints))} únicos de 100).")
        sys.exit(1)
    print("4. Fingerprints semánticos únicos verificados (100/100).")

    # 5. Cuerpos de solicitud JSON (98 distintos y 2 parejas coincidentes explícitas)
    request_bodies = [json.dumps(r.request, sort_keys=True) for r in records]
    unique_bodies = set(request_bodies)
    print(f"5. Solicitudes JSON distintas: {len(unique_bodies)} de 100.")
    if len(unique_bodies) != 98:
        print(f"ERROR: Se esperaban 98 cuerpos de solicitud distintos, se hallaron {len(unique_bodies)}")
        sys.exit(1)

    # Justificar las dos coincidencias esperadas
    body_map = {}
    for r in records:
        body_str = json.dumps(r.request, sort_keys=True)
        body_map.setdefault(body_str, []).append(r.id)

    duplicated_pairs = [sorted(ids) for ids in body_map.values() if len(ids) > 1]
    expected_pairs = [["TC-ADV-005", "TC-ERR-001"], ["TC-ERR-002", "TC-ERR-019"]]
    for pair in expected_pairs:
        pair.sort()

    if sorted(duplicated_pairs) != sorted(expected_pairs):
        print(f"ERROR: Coincidencias de cuerpos no justificadas: {duplicated_pairs}")
        sys.exit(1)
    print("   Justificación de coincidencias coincidente:")
    print("   - TC-ERR-001 / TC-ADV-005: Mismo cuerpo, diferente auth/fixture/resultado")
    print("   - TC-ERR-002 / TC-ERR-019: Mismo cuerpo, diferente prueba (auth vs timeout)")

    # 6. Fixtures existentes y JSON válidos
    for r in records:
        if r.jpl_fixture_file:
            fx_path = FIXTURES_DIR / r.jpl_fixture_file
            if not fx_path.exists():
                print(f"ERROR: Fixture {r.jpl_fixture_file} referenciado por {r.id} no existe.")
                sys.exit(1)
            try:
                with open(fx_path, "r", encoding="utf-8") as f:
                    json.load(f)
            except Exception as exc:
                print(f"ERROR: Fixture {r.jpl_fixture_file} no es un JSON válido: {exc}")
                sys.exit(1)
    print("6. Todos los fixtures referenciados existen y son JSON válidos.")

    # 7. Validación de solicitudes HTTP 200 y 422 contra ScriptGenerateRequest
    valid_200_count = 0
    invalid_422_count = 0
    for r in records:
        if r.expected_http_status == 200:
            try:
                ScriptGenerateRequest.model_validate(r.request)
                valid_200_count += 1
            except Exception as exc:
                print(f"ERROR: Caso {r.id} espera HTTP 200 pero falló la validación de entrada: {exc}")
                sys.exit(1)
        elif r.expected_http_status == 422:
            try:
                ScriptGenerateRequest.model_validate(r.request)
                print(f"ERROR: Caso {r.id} espera HTTP 422 pero la entrada pasó la validación Pydantic sin error.")
                sys.exit(1)
            except Exception:
                invalid_422_count += 1

    print(
        f"7. Solicitudes de entrada validadas con Pydantic: {valid_200_count} válidas (200) y {invalid_422_count} rechazadas (422)."
    )
    print("=" * 65)
    print("VALIDACIÓN COMPLETADA CON ÉXITO — DATASET V2 VÁLIDO")
    print("=" * 65)
    return True


if __name__ == "__main__":
    validate_dataset()
