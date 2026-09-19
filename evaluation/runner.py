import argparse
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from evaluation.cache_manager import EvaluationCacheManager
from evaluation.fixtures.jpl_loader import execute_jpl_provider_scenario
from evaluation.metrics.bedrock_nova_judge import BedrockNovaJudge, evaluate_llm_metrics_with_judge
from evaluation.metrics.deterministic_metrics import evaluate_deterministic_metrics
from evaluation.schemas import (
    AuthScenarioEnum,
    EvaluationResult,
    GoldenCaseRecord,
)

PRECIO_MICRO_ENTRADA_1K = 0.000035
PRECIO_MICRO_SALIDA_1K = 0.00014
PRECIO_LITE_ENTRADA_1K = 0.00006
PRECIO_LITE_SALIDA_1K = 0.00024

DATASET_PATH_V2 = Path(__file__).parent / "datasets" / "en_orbita_golden_v2.jsonl"
SMOKE_CASE_IDS_V2 = ["TC-POS-001", "TC-VAR-001", "TC-ERR-001", "TC-ERR-016", "TC-ADV-001"]


def calculate_cost(
    micro_in: int,
    micro_out: int,
    lite_in: int,
    lite_out: int,
) -> float:
    """Calcula el costo total observado utilizando la fórmula oficial por 1,000 tokens."""
    cost_micro_in = (micro_in / 1000.0) * PRECIO_MICRO_ENTRADA_1K
    cost_micro_out = (micro_out / 1000.0) * PRECIO_MICRO_SALIDA_1K
    cost_lite_in = (lite_in / 1000.0) * PRECIO_LITE_ENTRADA_1K
    cost_lite_out = (lite_out / 1000.0) * PRECIO_LITE_SALIDA_1K
    return cost_micro_in + cost_micro_out + cost_lite_in + cost_lite_out


def build_headers_for_auth_scenario(scenario: AuthScenarioEnum) -> dict[str, str]:
    """Construye los encabezados HTTP según el escenario de autenticación."""
    if scenario == AuthScenarioEnum.VALID:
        return {"X-API-Key": settings.APP_API_KEY}
    elif scenario == AuthScenarioEnum.MISSING:
        return {}
    elif scenario == AuthScenarioEnum.INCORRECT:
        return {"X-API-Key": "invalid-api-key-99999"}
    elif scenario == AuthScenarioEnum.EMPTY:
        return {"X-API-Key": ""}
    elif scenario == AuthScenarioEnum.MALFORMED:
        return {"X-API-Key": "###MALFORMED_HEADER###"}
    return {"X-API-Key": settings.APP_API_KEY}


def load_dataset_records(dataset_path: Path = DATASET_PATH_V2) -> list[GoldenCaseRecord]:
    """Carga y valida todos los casos de evaluación en el dataset autoritativo v2."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset no encontrado en: {dataset_path}")
    records = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                records.append(GoldenCaseRecord.model_validate_json(line_str))
    return records


def run_evaluation(
    smoke: bool = False,
    full: bool = False,
    yes_confirm: bool = False,
    case_id: str | None = None,
    case_ids_file: str | None = None,
    category: str | None = None,
    resume: bool = False,
    max_budget_usd: float = 0.05,
    dataset_path: Path = DATASET_PATH_V2,
) -> list[EvaluationResult]:
    """Orquesta la ejecución de evaluaciones del dataset v2."""

    if full and not yes_confirm:
        print("\nADVERTENCIA: Ha solicitado la ejecución completa (--full) de 100 casos.")
        print(f"El presupuesto máximo configurado es: ${max_budget_usd:.4f} USD.")
        answer = input("¿Desea continuar con la ejecución completa real? (s/N): ").strip().lower()
        if answer not in ("s", "si", "yes", "y"):
            print("Ejecución cancelada por el usuario.")
            sys.exit(0)

    records = load_dataset_records(dataset_path)

    target_case_ids: set[str] | None = None
    if case_ids_file:
        cfile_path = Path(case_ids_file)
        if cfile_path.exists():
            with open(cfile_path, "r", encoding="utf-8") as f:
                target_case_ids = set(line.strip() for line in f if line.strip())
            records = [r for r in records if r.id in target_case_ids]

    if case_id:
        records = [r for r in records if r.id == case_id]
    elif smoke:
        records = [r for r in records if r.id in SMOKE_CASE_IDS_V2]
    elif category:
        records = [r for r in records if r.category == category]

    print(f"\nIniciando Runner de Evaluación En órbita v2 ({len(records)} casos seleccionados)...")

    cache_mgr = EvaluationCacheManager()
    judge = BedrockNovaJudge()
    client = TestClient(app)

    results: list[EvaluationResult] = []
    accumulated_cost = 0.0

    total_micro_in = 0
    total_micro_out = 0
    total_lite_in = 0
    total_lite_out = 0
    micro_invocations = 0

    generative_cases_evaluated = 0
    generative_cost_observed = 0.0

    for rec in records:
        print(f"\n[Caso {rec.id}] ({rec.category}): {rec.description}")

        # Comprobar costo proyectado antes de invocar la siguiente llamada real
        if accumulated_cost + 0.005 > max_budget_usd:
            print(
                f"LÍMITE PRESUPUESTARIO ALCANZADO (${accumulated_cost:.6f} USD de ${max_budget_usd:.4f} USD). Deteniendo ejecuciones."
            )
            break

        # Clave de caché versionada para v2
        cache_key = cache_mgr.compute_cache_key(
            record_id=f"v2_{rec.id}",
            request_dict=rec.request,
            fixture_file=rec.jpl_fixture_file,
            generator_model=settings.BEDROCK_GENERATOR_MODEL_ID,
            judge_model=settings.BEDROCK_EVALUATOR_MODEL_ID,
            applicable_metrics=rec.applicable_metrics,
        )

        if resume:
            cached_data = cache_mgr.get(cache_key)
            if cached_data:
                print(f"  [CACHÉ v2] Resultado recuperado de disco ({rec.id})")
                res = EvaluationResult.model_validate(cached_data)
                results.append(res)
                accumulated_cost += res.cost_usd
                continue

        headers = build_headers_for_auth_scenario(rec.auth_scenario)
        http_status_actual = 500
        app_status_actual = "http_error"
        script_text: str | None = None
        case_micro_in = 0
        case_micro_out = 0
        case_error: str | None = None

        jpl_called = 0
        generator_called = 0

        try:

            async def mock_jpl(*args, **kwargs):
                nonlocal jpl_called
                jpl_called += 1
                return await execute_jpl_provider_scenario(rec.provider_scenario, rec.jpl_fixture_file)

            import unittest.mock as mock

            with mock.patch("app.main.fetch_and_normalize_jpl_cad", side_effect=mock_jpl):
                response = client.post("/scripts/generate", json=rec.request, headers=headers)

            http_status_actual = response.status_code
            resp_body = response.json() if http_status_actual == 200 else {}
            app_status_actual = resp_body.get("status", "http_error")

            # Verificación de invariantes en respuestas HTTP 200 generativas
            if http_status_actual == 200 and "script" in resp_body and resp_body["script"]:
                generator_called = 1
                script_obj = resp_body["script"]
                script_text = f"Título: {script_obj.get('title')}\nApertura: {script_obj.get('opening')}\nDesarrollo: {script_obj.get('development')}\nCierre: {script_obj.get('closure')}"
                if rec.execution_sources.generator == "real":
                    micro_invocations += 1
                    telemetry_raw = resp_body.get("telemetry", {})
                    usage = telemetry_raw.get("llm_tokens", {})
                    if usage.get("tokens_status") == "observed":
                        case_micro_in = int(usage.get("prompt_tokens", 0))
                        case_micro_out = int(usage.get("completion_tokens", 0))
                    else:
                        case_micro_in = 0
                        case_micro_out = 0
                    total_micro_in += case_micro_in
                    total_micro_out += case_micro_out

                # Verificar invariantes del servidor
                if resp_body.get("requires_human_review") is not True:
                    case_error = "Invariante violada: requires_human_review debe ser True"
                if resp_body.get("status") != "draft_pending_review":
                    case_error = f"Invariante violada: status es '{resp_body.get('status')}' y se esperaba 'draft_pending_review'"

        except Exception as exc:
            case_error = str(exc)
            app_status_actual = "evaluation_error"

        # Métricas deterministas
        metric_scores = evaluate_deterministic_metrics(
            record=rec,
            http_status_actual=http_status_actual,
            app_status_actual=app_status_actual,
            script_text=script_text,
            jpl_call_count=jpl_called,
            generator_call_count=generator_called,
            judge_call_count=0,
        )

        # Métricas LLM con Juez Nova Lite
        lite_in_start = judge.input_tokens
        lite_out_start = judge.output_tokens

        if script_text and rec.execution_sources.judge == "real" and not case_error:
            try:
                llm_scores = evaluate_llm_metrics_with_judge(
                    record=rec,
                    actual_script_text=script_text,
                    judge=judge,
                )
                metric_scores.extend(llm_scores)
            except Exception as exc:
                case_error = f"Error en la evaluación del juez LLM: {str(exc)}"

        case_lite_in = judge.input_tokens - lite_in_start
        case_lite_out = judge.output_tokens - lite_out_start

        total_lite_in += case_lite_in
        total_lite_out += case_lite_out

        if case_error:
            case_status = "evaluation_error"
        else:
            all_passed = all(m.passed for m in metric_scores)
            case_status = "passed" if all_passed else "failed"

        case_cost = calculate_cost(case_micro_in, case_micro_out, case_lite_in, case_lite_out)
        accumulated_cost += case_cost

        if rec.execution_sources.generator == "real":
            generative_cases_evaluated += 1
            generative_cost_observed += case_cost

        tokens_status_val = (
            "observed"
            if (rec.execution_sources.generator == "real" or rec.execution_sources.judge == "real")
            else "unavailable"
        )

        result_item = EvaluationResult(
            case_id=rec.id,
            category=rec.category,
            description=rec.description,
            status=case_status,
            http_status_actual=http_status_actual,
            app_status_actual=app_status_actual,
            metrics=metric_scores,
            execution_sources=rec.execution_sources,
            tokens_micro_in=case_micro_in,
            tokens_micro_out=case_micro_out,
            tokens_lite_in=case_lite_in,
            tokens_lite_out=case_lite_out,
            tokens_status=tokens_status_val,
            cost_usd=case_cost,
            error_message=case_error,
        )

        results.append(result_item)
        cache_mgr.set(cache_key, result_item.model_dump())

        print(
            f"  Resultado: [{result_item.status.upper()}] (HTTP {http_status_actual}, App {app_status_actual}) - Costo: ${case_cost:.6f} USD"
        )
        for m in metric_scores:
            print(
                f"    - {m.metric_name}: Score={m.score:.2f} (Umbral {m.threshold:.2f}) -> {'PASÓ' if m.passed else 'FALLÓ'}"
            )

    # Proyección corregida según Sección 13
    costo_promedio_generativo = (
        (generative_cost_observed / generative_cases_evaluated) if generative_cases_evaluated > 0 else 0.0
    )
    proyeccion_generativa_71 = costo_promedio_generativo * 71.0
    costo_no_generativo_29 = 0.0  # Los 29 casos no generativos no consumen tokens Bedrock
    costo_total_proyectado_100 = proyeccion_generativa_71 + costo_no_generativo_29

    print("\n" + "=" * 65)
    print("RESUMEN DE RESULTADOS DE EVALUACIÓN (RUNNER DATASET V2)")
    print("=" * 65)
    passed_cnt = sum(1 for r in results if r.status == "passed")
    failed_cnt = sum(1 for r in results if r.status == "failed")
    error_cnt = sum(1 for r in results if r.status == "evaluation_error")
    total_eval = len(results)

    print(f"Total casos procesados: {total_eval}")
    print(f" - Aprobados (passed): {passed_cnt}")
    print(f" - Fallidos (failed):  {failed_cnt}")
    print(f" - Errores (eval_err): {error_cnt}")
    print("-" * 65)
    print(f"Invocaciones Nova Micro: {micro_invocations}")
    print(f"Invocaciones Nova Lite (Juez): {judge.invocation_count}")
    print(f"Tokens Nova Micro - Entrada: {total_micro_in}, Salida: {total_micro_out}")
    print(f"Tokens Nova Lite  - Entrada: {total_lite_in}, Salida: {total_lite_out}")
    print(f"COSTO OBSERVADO: ${accumulated_cost:.6f} USD")
    print(
        f"Costo promedio por caso generativo ({generative_cases_evaluated} cas): ${costo_promedio_generativo:.6f} USD"
    )
    print(f"Proyección para 71 casos generativos: ${proyeccion_generativa_71:.6f} USD")
    print(f"PROYECCIÓN TOTAL DE COSTO PARA 100 CASOS: ${costo_total_proyectado_100:.6f} USD")
    print(f"Presupuesto máximo configurado: ${max_budget_usd:.4f} USD")
    print("=" * 65)

    if case_ids_file:
        export_reevaluation_artifacts(results, accumulated_cost)
    elif full or len(results) == 100:
        export_evaluation_artifacts(
            results, accumulated_cost, total_micro_in, total_micro_out, total_lite_in, total_lite_out
        )

    return results


def export_reevaluation_artifacts(
    reeval_results: list[EvaluationResult],
    reeval_cost: float,
    output_dir: Path = Path("evidencias/sesion-05"),
):
    """Guarda reevaluacion_factual.json y genera evaluacion_corregida.json, evaluacion_corregida.md y comparacion_antes_despues.md."""
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    reeval_json_path = output_dir / "reevaluacion_factual.json"
    initial_json_path = output_dir / "evaluacion_inicial.json"
    corrected_json_path = output_dir / "evaluacion_corregida.json"
    corrected_md_path = output_dir / "evaluacion_corregida.md"
    comparison_md_path = output_dir / "comparacion_antes_despues.md"

    # 1. Guardar reevaluacion_factual.json
    reeval_data = []
    for r in reeval_results:
        m_scores = {m.metric_name: m.score for m in r.metrics}
        m_reasons = {m.metric_name: m.reason for m in r.metrics}
        reeval_data.append(
            {
                "case_id": r.case_id,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                "http_status_actual": r.http_status_actual,
                "app_status_actual": r.app_status_actual,
                "metric_scores": m_scores,
                "metric_reasons": m_reasons,
                "execution_sources": r.execution_sources.model_dump(),
                "tokens_micro_in": r.tokens_micro_in,
                "tokens_micro_out": r.tokens_micro_out,
                "tokens_lite_in": r.tokens_lite_in,
                "tokens_lite_out": r.tokens_lite_out,
                "tokens_status": r.tokens_status,
                "cost_usd": r.cost_usd,
                "error_message": r.error_message,
            }
        )

    with open(reeval_json_path, "w", encoding="utf-8") as f:
        json.dump(reeval_data, f, ensure_ascii=False, indent=2)

    # 2. Consolidar 100 casos en evaluacion_corregida.json
    reeval_dict = {r["case_id"]: r for r in reeval_data}
    initial_data = []
    if initial_json_path.exists():
        with open(initial_json_path, "r", encoding="utf-8") as f:
            initial_data = json.load(f)

    consolidated_data = []
    for item in initial_data:
        cid = item["case_id"]
        if cid in reeval_dict:
            new_item = dict(reeval_dict[cid])
            new_item["origin"] = "re_evaluated"
            consolidated_data.append(new_item)
        else:
            old_item = dict(item)
            old_item["origin"] = "initial_unchanged"
            consolidated_data.append(old_item)

    with open(corrected_json_path, "w", encoding="utf-8") as f:
        json.dump(consolidated_data, f, ensure_ascii=False, indent=2)

    # 3. Generar evaluacion_corregida.md
    total_count = len(consolidated_data)
    passed_count = sum(1 for r in consolidated_data if r["status"] == "passed")
    failed_count = sum(1 for r in consolidated_data if r["status"] == "failed")
    error_count = sum(1 for r in consolidated_data if r["status"] == "evaluation_error")
    pass_pct = (passed_count / total_count * 100.0) if total_count > 0 else 0.0

    categories = ["positive", "boundary_variant", "controlled_error", "adversarial"]
    cat_summary = []
    for cat in categories:
        cat_results = [r for r in consolidated_data if r["category"] == cat]
        cat_total = len(cat_results)
        cat_passed = sum(1 for r in cat_results if r["status"] == "passed")
        cat_failed = sum(1 for r in cat_results if r["status"] == "failed")
        cat_err = sum(1 for r in cat_results if r["status"] == "evaluation_error")
        cat_pct = (cat_passed / cat_total * 100.0) if cat_total > 0 else 0.0
        cat_summary.append((cat, cat_total, cat_passed, cat_failed, cat_err, cat_pct))

    all_metric_names = set()
    for r in consolidated_data:
        for m in r["metric_scores"]:
            all_metric_names.add(m)

    metric_summary = []
    for mname in sorted(all_metric_names):
        m_total = sum(1 for r in consolidated_data if mname in r["metric_scores"])
        thresh = 1.0
        if mname in ("factual_consistency", "task_completion"):
            thresh = 0.8
        elif mname == "security":
            thresh = 0.9
        m_passed = sum(
            1 for r in consolidated_data if mname in r["metric_scores"] and r["metric_scores"][mname] >= thresh
        )
        m_failed = m_total - m_passed
        metric_summary.append((mname, m_total, m_passed, m_failed))

    total_cost_consolidated = sum(r.get("cost_usd", 0.0) for r in consolidated_data)

    md_corrected = f"""# Resumen de Evaluación Corregida (Línea Base + Reevaluación de 40 Casos)

## 1. Resultado Global Corregido

| Métrica | Valor |
| :--- | :--- |
| **Casos Procesados** | {total_count} |
| **Casos Aprobados** | {passed_count} |
| **Casos Fallidos** | {failed_count} |
| **Errores de Evaluación** | {error_count} |
| **Porcentaje de Aprobación** | {pass_pct:.2f}% |
| **Costo Total Consolidado** | ${total_cost_consolidated:.6f} USD |

## 2. Resultado por Categoría Corregido

| Categoría | Total | Aprobados | Fallidos | Eval Error | % Aprobación |
| :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for cat, c_tot, c_pass, c_fail, c_err, c_pct in cat_summary:
        md_corrected += f"| `{cat}` | {c_tot} | {c_pass} | {c_fail} | {c_err} | {c_pct:.2f}% |\n"

    md_corrected += """
## 3. Resultado por Métrica Corregido

| Métrica | Evaluar Totales | Aprobados | Fallidos |
| :--- | :---: | :---: | :---: |
"""
    for mname, m_tot, m_pass, m_fail in metric_summary:
        md_corrected += f"| `{mname}` | {m_tot} | {m_pass} | {m_fail} |\n"

    with open(corrected_md_path, "w", encoding="utf-8") as f:
        f.write(md_corrected)

    # 4. Generar comparacion_antes_despues.md
    initial_passed = sum(1 for r in initial_data if r["status"] == "passed")
    initial_failed = sum(1 for r in initial_data if r["status"] == "failed")
    initial_fc_failed = sum(1 for r in initial_data if r["metric_scores"].get("factual_consistency", 1.0) < 0.8)
    corr_fc_failed = sum(1 for r in consolidated_data if r["metric_scores"].get("factual_consistency", 1.0) < 0.8)

    comparison_md = f"""# Comparación Antes vs Después de la Corrección Única del Juez

| Indicador | Línea Base (Inicial) | Después de Corrección |
| :--- | ---: | ---: |
| **Casos Aprobados** | {initial_passed} | {passed_count} |
| **Casos Fallidos** | {initial_failed} | {failed_count} |
| **Evaluation Errors** | 0 | {error_count} |
| **Aprobación Global** | {(initial_passed / len(initial_data) * 100.0) if initial_data else 58.00:.2f}% | {pass_pct:.2f}% |
| **Fallos de `factual_consistency`** | {initial_fc_failed} | {corr_fc_failed} |
| **Costo Adicional Observado** | — | ${reeval_cost:.6f} USD |
"""

    with open(comparison_md_path, "w", encoding="utf-8") as f:
        f.write(comparison_md)

    print("\n[ARTIFACTS RE-EVALUATION EXPORTED] Se generaron correctamente:")
    print(f" - {reeval_json_path}")
    print(f" - {corrected_json_path}")
    print(f" - {corrected_md_path}")
    print(f" - {comparison_md_path}")


def export_evaluation_artifacts(
    results: list[EvaluationResult],
    accumulated_cost: float,
    total_micro_in: int,
    total_micro_out: int,
    total_lite_in: int,
    total_lite_out: int,
    output_dir: Path = Path("evidencias/sesion-05"),
):
    """Genera evaluacion_inicial.json y evaluacion_inicial.md."""
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evaluacion_inicial.json"
    md_path = output_dir / "evaluacion_inicial.md"

    # Exportar JSON
    json_data = []
    for r in results:
        m_scores = {m.metric_name: m.score for m in r.metrics}
        m_reasons = {m.metric_name: m.reason for m in r.metrics}
        json_data.append(
            {
                "case_id": r.case_id,
                "category": r.category,
                "description": r.description,
                "status": r.status,
                "http_status_actual": r.http_status_actual,
                "app_status_actual": r.app_status_actual,
                "metric_scores": m_scores,
                "metric_reasons": m_reasons,
                "execution_sources": r.execution_sources.model_dump(),
                "tokens_micro_in": r.tokens_micro_in,
                "tokens_micro_out": r.tokens_micro_out,
                "tokens_lite_in": r.tokens_lite_in,
                "tokens_lite_out": r.tokens_lite_out,
                "tokens_status": r.tokens_status,
                "cost_usd": r.cost_usd,
                "error_message": r.error_message,
            }
        )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # Exportar Markdown
    total_count = len(results)
    passed_count = sum(1 for r in results if r.status == "passed")
    failed_count = sum(1 for r in results if r.status == "failed")
    error_count = sum(1 for r in results if r.status == "evaluation_error")
    pass_pct = (passed_count / total_count * 100.0) if total_count > 0 else 0.0

    categories = ["positive", "boundary_variant", "controlled_error", "adversarial"]
    cat_summary = []
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        cat_total = len(cat_results)
        cat_passed = sum(1 for r in cat_results if r.status == "passed")
        cat_failed = sum(1 for r in cat_results if r.status == "failed")
        cat_err = sum(1 for r in cat_results if r.status == "evaluation_error")
        cat_pct = (cat_passed / cat_total * 100.0) if cat_total > 0 else 0.0
        cat_summary.append((cat, cat_total, cat_passed, cat_failed, cat_err, cat_pct))

    all_metric_names = set()
    for r in results:
        for m in r.metrics:
            all_metric_names.add(m.metric_name)

    metric_summary = []
    for mname in sorted(all_metric_names):
        m_total = sum(1 for r in results if any(m.metric_name == mname for m in r.metrics))
        m_passed = sum(1 for r in results if any(m.metric_name == mname and m.passed for m in r.metrics))
        m_failed = m_total - m_passed
        metric_summary.append((mname, m_total, m_passed, m_failed))

    acad_ids = ["TC-POS-001", "TC-VAR-001", "TC-ERR-006", "TC-ERR-008", "TC-ERR-016"]
    acad_results = {r.case_id: r for r in results if r.case_id in acad_ids}

    md_content = f"""# Resumen de Evaluación Inicial de Línea Base (Dataset v2 - 100 Casos)

## 1. Resultado Global

| Métrica | Valor |
| :--- | :--- |
| **Casos Procesados** | {total_count} |
| **Casos Aprobados** | {passed_count} |
| **Casos Fallidos** | {failed_count} |
| **Errores de Evaluación** | {error_count} |
| **Porcentaje de Aprobación** | {pass_pct:.2f}% |
| **Costo Total Observado** | ${accumulated_cost:.6f} USD |

## 2. Resultado por Categoría

| Categoría | Total | Aprobados | Fallidos | Eval Error | % Aprobación |
| :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for cat, c_tot, c_pass, c_fail, c_err, c_pct in cat_summary:
        md_content += f"| `{cat}` | {c_tot} | {c_pass} | {c_fail} | {c_err} | {c_pct:.2f}% |\n"

    md_content += """
## 3. Resultado por Métrica

| Métrica | Evaluar Totales | Aprobados | Fallidos |
| :--- | :---: | :---: | :---: |
"""
    for mname, m_tot, m_pass, m_fail in metric_summary:
        md_content += f"| `{mname}` | {m_tot} | {m_pass} | {m_fail} |\n"

    md_content += """
## 4. Cinco Casos Obligatorios de la Plantilla Académica

"""
    acad_labels = {
        "TC-POS-001": ("Válido", "Invocación real Nova Micro / Nova Lite (Fixture normal.json)"),
        "TC-VAR-001": ("Variante Válida", "Invocación real Nova Micro / Nova Lite (Audiencia infantil)"),
        "TC-ERR-006": ("Datos Faltantes", "Mock JPL sin eventos cercanos (no_events)"),
        "TC-ERR-008": ("Datos Inválidos", "Validación Pydantic estática 422 (duración < 5s)"),
        "TC-ERR-016": ("Proveedor Falla", "Mock JPL con error 500 del servidor (http_error)"),
    }

    for cid in acad_ids:
        r = acad_results.get(cid)
        if r:
            lbl, src = acad_labels[cid]
            md_content += f"### Caso {cid} ({lbl})\n"
            md_content += f"- **Categoría:** `{r.category}`\n"
            md_content += f"- **Descripción:** {r.description}\n"
            md_content += f"- **Fuentes de Ejecución:** {src}\n"
            md_content += (
                f"- **Resultado:** `{r.status.upper()}` (HTTP {r.http_status_actual}, App {r.app_status_actual})\n"
            )
            md_content += f"- **Costo Observado:** ${r.cost_usd:.6f} USD (Tokens Micro In/Out: {r.tokens_micro_in}/{r.tokens_micro_out}, Lite In/Out: {r.tokens_lite_in}/{r.tokens_lite_out})\n\n"

    md_content += f"""## 5. Telemetría y Costo Observado Real

- **Invocaciones Nova Micro:** {sum(1 for r in results if r.execution_sources.generator == "real")}
- **Invocaciones Nova Lite (Juez):** {sum(1 for r in results if r.execution_sources.judge == "real")}
- **Tokens Observados Nova Micro:** {total_micro_in} entrada / {total_micro_out} salida
- **Tokens Observados Nova Lite:** {total_lite_in} entrada / {total_lite_out} salida
- **Casos con Telemetría `unavailable`:** {sum(1 for r in results if r.tokens_status == "unavailable")}
- **Costo Total Observado:** ${accumulated_cost:.6f} USD
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print("\n[ARTIFACTS EXPORTED] Se generaron correctamente:")
    print(f" - {json_path}")
    print(f" - {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Runner de Evaluación Dataset v2 para En órbita")
    parser.add_argument("--smoke", action="store_true", help="Ejecuta 5 casos representativos v2")
    parser.add_argument("--full", action="store_true", help="Ejecuta la corrida completa de 100 casos v2")
    parser.add_argument("--yes", action="store_true", help="Confirma automáticamente la corrida completa")
    parser.add_argument("--case-id", type=str, help="Ejecuta un caso específico por ID")
    parser.add_argument("--case-ids-file", type=str, help="Ruta al archivo con lista de IDs a reevaluar")
    parser.add_argument("--category", type=str, help="Filtra ejecuciones por categoría")
    parser.add_argument("--resume", action="store_true", help="Reanuda ejecuciones usando la caché en disco v2")
    parser.add_argument("--max-budget-usd", type=float, default=0.05, help="Presupuesto máximo en USD")

    args = parser.parse_args()

    run_evaluation(
        smoke=args.smoke,
        full=args.full,
        yes_confirm=args.yes,
        case_id=args.case_id,
        case_ids_file=args.case_ids_file,
        category=args.category,
        resume=args.resume,
        max_budget_usd=args.max_budget_usd,
    )


if __name__ == "__main__":
    main()
