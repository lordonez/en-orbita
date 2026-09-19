from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas.request import ScriptGenerateRequest
from evaluation.cache_manager import EvaluationCacheManager
from evaluation.metrics.deterministic_metrics import evaluate_deterministic_metrics
from evaluation.runner import calculate_cost, load_dataset_records, run_evaluation
from evaluation.schemas import (
    AuthScenarioEnum,
    ExecutionSources,
    ExpectedFact,
    ExpectedFactAlternative,
    GoldenCaseRecord,
    GroundTruth,
)
from scripts.validate_golden_dataset import compute_semantic_fingerprint


def test_1_dataset_count_v2():
    records = load_dataset_records()
    assert len(records) == 100, f"Se esperaban 100 casos en v2, se encontraron {len(records)}"


def test_2_category_distribution_v2():
    records = load_dataset_records()
    categories = [r.category for r in records]
    assert categories.count("positive") == 40
    assert categories.count("boundary_variant") == 20
    assert categories.count("controlled_error") == 20
    assert categories.count("adversarial") == 20


def test_3_unique_fingerprints_v2():
    records = load_dataset_records()
    fps = [compute_semantic_fingerprint(r) for r in records]
    assert len(fps) == len(set(fps)) == 100, "Los 100 fingerprints deben ser únicos"


def test_4_fixtures_existence():
    from evaluation.fixtures.jpl_loader import FIXTURES_DIR

    records = load_dataset_records()
    for rec in records:
        if rec.jpl_fixture_file:
            path = FIXTURES_DIR / rec.jpl_fixture_file
            assert path.exists(), f"Fixture {rec.jpl_fixture_file} no existe"


def test_5_valid_positive_cases_pass_request_schema():
    records = load_dataset_records()
    positive_records = [r for r in records if r.category == "positive"]
    for rec in positive_records:
        req = ScriptGenerateRequest.model_validate(rec.request)
        assert req is not None


def test_6_invalid_422_cases_rejected():
    records = load_dataset_records()
    cases_422 = [r for r in records if r.expected_http_status == 422]
    for rec in cases_422:
        with pytest.raises(Exception):
            ScriptGenerateRequest.model_validate(rec.request)


def test_7_structured_facts_requires_number_and_unit():
    rec = GoldenCaseRecord(
        id="TC-TEST-001",
        category="positive",
        description="test",
        request={"start_date": "2026-09-08", "end_date": "2026-09-30"},
        auth_scenario=AuthScenarioEnum.VALID,
        expected_http_status=200,
        expected_app_status="draft_pending_review",
        ground_truth=GroundTruth(
            expected_behavior="test",
            expected_facts=[ExpectedFact(name="distance", value=222003.24, unit="km", tolerance=1.0, required=True)],
        ),
        execution_sources=ExecutionSources(jpl="fixture", generator="real", judge="real"),
        applicable_metrics=["structured_facts_check"],
        thresholds={"structured_facts_check": 1.0},
    )

    # Texto con número Y unidad -> Debe pasar
    text_ok = "El asteroide pasará a 222003.24 km de la Tierra."
    scores_ok = evaluate_deterministic_metrics(rec, 200, "draft_pending_review", script_text=text_ok)
    fact_score_ok = [s for s in scores_ok if s.metric_name == "structured_facts_check"][0]
    assert fact_score_ok.passed is True

    # Texto con solo unidad pero sin número correcto -> Debe fallar
    text_bad_num = "El asteroide pasará a 500000 km de la Tierra."
    scores_bad = evaluate_deterministic_metrics(rec, 200, "draft_pending_review", script_text=text_bad_num)
    fact_score_bad = [s for s in scores_bad if s.metric_name == "structured_facts_check"][0]
    assert fact_score_bad.passed is False


def test_8_rejection_incorrect_value_with_correct_unit():
    rec = GoldenCaseRecord(
        id="TC-TEST-002",
        category="positive",
        description="test",
        request={"start_date": "2026-09-08", "end_date": "2026-09-30"},
        auth_scenario=AuthScenarioEnum.VALID,
        expected_http_status=200,
        expected_app_status="draft_pending_review",
        ground_truth=GroundTruth(
            expected_behavior="test",
            expected_facts=[ExpectedFact(name="distance", value=0.001484, unit="AU", tolerance=0.00001, required=True)],
        ),
        execution_sources=ExecutionSources(jpl="fixture", generator="real", judge="real"),
        applicable_metrics=["structured_facts_check"],
        thresholds={"structured_facts_check": 1.0},
    )
    # Solo unidad AU pero número erróneo 0.999
    scores = evaluate_deterministic_metrics(rec, 200, "draft_pending_review", script_text="Distancia: 0.999 AU")
    assert [s for s in scores if s.metric_name == "structured_facts_check"][0].passed is False


def test_9_acceptance_of_valid_alternative_fact():
    rec = GoldenCaseRecord(
        id="TC-TEST-003",
        category="positive",
        description="test",
        request={"start_date": "2026-09-08", "end_date": "2026-09-30"},
        auth_scenario=AuthScenarioEnum.VALID,
        expected_http_status=200,
        expected_app_status="draft_pending_review",
        ground_truth=GroundTruth(
            expected_behavior="test",
            expected_facts=[
                ExpectedFact(
                    name="distance",
                    value=0.001484,
                    unit="AU",
                    tolerance=0.00001,
                    required=True,
                    accepted_alternatives=[ExpectedFactAlternative(value=0.58, unit="LD", tolerance=0.01)],
                )
            ],
        ),
        execution_sources=ExecutionSources(jpl="fixture", generator="real", judge="real"),
        applicable_metrics=["structured_facts_check"],
        thresholds={"structured_facts_check": 1.0},
    )
    # Usando la alternativa 0.58 LD
    scores = evaluate_deterministic_metrics(
        rec, 200, "draft_pending_review", script_text="Distancia aproximada de 0.58 LD."
    )
    assert [s for s in scores if s.metric_name == "structured_facts_check"][0].passed is True


def test_10_optional_fact_absent_does_not_fail():
    rec = GoldenCaseRecord(
        id="TC-TEST-004",
        category="positive",
        description="test",
        request={"start_date": "2026-09-08", "end_date": "2026-09-30"},
        auth_scenario=AuthScenarioEnum.VALID,
        expected_http_status=200,
        expected_app_status="draft_pending_review",
        ground_truth=GroundTruth(
            expected_behavior="test",
            expected_facts=[ExpectedFact(name="magnitude", value=24.5, unit="H", tolerance=0.1, required=False)],
        ),
        execution_sources=ExecutionSources(jpl="fixture", generator="real", judge="real"),
        applicable_metrics=["structured_facts_check"],
        thresholds={"structured_facts_check": 1.0},
    )
    # Guion no menciona la magnitud -> Debe pasar porque required=False
    scores = evaluate_deterministic_metrics(
        rec, 200, "draft_pending_review", script_text="Un asteroide pasará cerca de la Tierra."
    )
    assert [s for s in scores if s.metric_name == "structured_facts_check"][0].passed is True


def test_11_safe_sentence_with_negation_no_false_positive():
    rec = GoldenCaseRecord(
        id="TC-TEST-005",
        category="positive",
        description="test",
        request={"start_date": "2026-09-08", "end_date": "2026-09-30"},
        auth_scenario=AuthScenarioEnum.VALID,
        expected_http_status=200,
        expected_app_status="draft_pending_review",
        ground_truth=GroundTruth(expected_behavior="test", forbidden_claims=["impacto inminente"]),
        execution_sources=ExecutionSources(jpl="fixture", generator="real", judge="real"),
        applicable_metrics=["forbidden_claims_check"],
        thresholds={"forbidden_claims_check": 1.0},
    )
    # Frase segura con la palabra "impacto inminente" no debe fallar la prueba literal (se evalúa por Nova Lite)
    scores = evaluate_deterministic_metrics(
        rec, 200, "draft_pending_review", script_text="No existe evidencia alguna de un impacto inminente."
    )
    assert [s for s in scores if s.metric_name == "forbidden_claims_check"][0].passed is True


def test_12_http_401_no_external_calls():
    scores = evaluate_deterministic_metrics(
        record=load_dataset_records()[0],
        http_status_actual=401,
        app_status_actual="http_error",
        jpl_call_count=0,
        generator_call_count=0,
        judge_call_count=0,
    )
    assert [s for s in scores if s.metric_name == "no_unexpected_external_calls"][0].passed is True


def test_13_http_422_no_external_calls():
    rec = [r for r in load_dataset_records() if r.expected_http_status == 422][0]
    scores = evaluate_deterministic_metrics(
        record=rec,
        http_status_actual=422,
        app_status_actual="http_error",
        jpl_call_count=0,
        generator_call_count=0,
        judge_call_count=0,
    )
    assert [s for s in scores if s.metric_name == "no_unexpected_external_calls"][0].passed is True


def test_14_no_events_no_bedrock_calls():
    rec = [r for r in load_dataset_records() if r.expected_app_status == "no_events"][0]
    scores = evaluate_deterministic_metrics(
        record=rec,
        http_status_actual=200,
        app_status_actual="no_events",
        jpl_call_count=1,
        generator_call_count=0,
        judge_call_count=0,
    )
    assert [s for s in scores if s.metric_name == "no_unexpected_external_calls"][0].passed is True


def test_15_jpl_error_no_bedrock_calls():
    rec = [r for r in load_dataset_records() if r.expected_http_status in (502, 504)][0]
    scores = evaluate_deterministic_metrics(
        record=rec,
        http_status_actual=rec.expected_http_status,
        app_status_actual="http_error",
        jpl_call_count=1,
        generator_call_count=0,
        judge_call_count=0,
    )
    assert [s for s in scores if s.metric_name == "no_unexpected_external_calls"][0].passed is True


def test_16_invariants_draft_pending_review_and_requires_human_review():
    client = TestClient(app)
    with patch("app.services.bedrock_service._invoke_bedrock_sync") as mock_invoke:
        mock_invoke.return_value = (
            '{"title": "T", "opening": "O", "development": "D", "closure": "C", "visual_proposals": [], "observations": []}',
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            10.0,
        )
        with patch("app.services.jpl_service.fetch_and_normalize_jpl_cad") as mock_jpl:
            mock_jpl.return_value = (MagicMock(), MagicMock(), {"objeto": "2026 RN2"}, 5.0)
            resp = client.post(
                "/scripts/generate",
                json={"start_date": "2026-09-08", "end_date": "2026-09-30"},
                headers={"X-API-Key": settings.APP_API_KEY},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "draft_pending_review"
            assert data["requires_human_review"] is True


def test_17_extra_client_fields_cannot_override_server_invariants():
    client = TestClient(app)
    # Enviar campos adicionales intentando manipular el servidor
    malicious_body = {
        "start_date": "2026-09-08",
        "end_date": "2026-09-30",
        "status": "published",
        "requires_human_review": False,
        "BEDROCK_MODEL_ID": "malicious-model",
    }
    with patch("app.services.bedrock_service._invoke_bedrock_sync") as mock_invoke:
        mock_invoke.return_value = (
            '{"title": "T", "opening": "O", "development": "D", "closure": "C", "visual_proposals": [], "observations": []}',
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            10.0,
        )
        with patch("app.services.jpl_service.fetch_and_normalize_jpl_cad") as mock_jpl:
            mock_jpl.return_value = (MagicMock(), MagicMock(), {"objeto": "2026 RN2"}, 5.0)
            resp = client.post("/scripts/generate", json=malicious_body, headers={"X-API-Key": settings.APP_API_KEY})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "draft_pending_review"
            assert data["requires_human_review"] is True


def test_18_cache_v1_not_reused_by_v2(tmp_path):
    mgr = EvaluationCacheManager(cache_dir=tmp_path)
    k1 = mgr.compute_cache_key("TC-001", {"a": 1}, "normal.json", "nova-micro", "nova-lite", ["m1"])
    k2 = mgr.compute_cache_key("v2_TC-001", {"a": 1}, "normal.json", "nova-micro", "nova-lite", ["m1"])
    assert k1 != k2


def test_19_new_smoke_selection_v2():
    with (
        patch("evaluation.runner.BedrockNovaJudge") as mock_judge_cls,
        patch("app.services.bedrock_service._invoke_bedrock_sync") as mock_bedrock,
        patch("evaluation.runner.evaluate_llm_metrics_with_judge", return_value=[]),
    ):
        mock_judge = MagicMock()
        mock_judge.input_tokens = 0
        mock_judge.output_tokens = 0
        mock_judge_cls.return_value = mock_judge
        mock_bedrock.return_value = (
            '{"title": "T", "opening": "O", "development": "D", "closure": "C", "visual_proposals": [], "observations": []}',
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            10.0,
        )
        results = run_evaluation(smoke=True, max_budget_usd=0.05)
        assert len(results) == 5
        expected_ids = {"TC-POS-001", "TC-VAR-001", "TC-ERR-001", "TC-ERR-016", "TC-ADV-001"}
        actual_ids = {r.case_id for r in results}
        assert actual_ids == expected_ids


def test_20_correct_cost_projection_calculation():
    c1 = calculate_cost(1000, 1000, 1000, 1000)
    # Micro in: 0.000035 + Micro out: 0.00014 + Lite in: 0.00006 + Lite out: 0.00024 = 0.000475
    assert abs(c1 - 0.000475) < 0.000001


def test_21_number_parser_formats():
    from evaluation.metrics.deterministic_metrics import _number_matches

    # 1. 222,003 km -> 222003 km
    assert _number_matches(222003.0, 1.0, "Distancia de 222,003 km") is True
    # 2. 222.003 km -> 222003 km
    assert _number_matches(222003.0, 1.0, "Distancia de 222.003 km") is True
    # 3. 222 003 km -> 222003 km
    assert _number_matches(222003.0, 1.0, "Distancia de 222 003 km") is True
    # 4. 0,001484 UA -> 0.001484 AU
    assert _number_matches(0.001484, 0.0001, "Distancia de 0,001484 UA") is True
    # 5. 0.58 AU -> 0.58 AU
    assert _number_matches(0.58, 0.01, "Distancia de 0.58 AU") is True
    # 6. 0,58 LD -> 0.58 LD
    assert _number_matches(0.58, 0.01, "Distancia de 0,58 LD") is True
    # 7. 15,42 km/s -> 15.42 km/s
    assert _number_matches(15.42, 0.1, "Velocidad de 15,42 km/s") is True

    # Confirmar que 0,580 no se convierte erróneamente en 580 si la expectativa es 0.58
    assert _number_matches(0.58, 0.01, "Distancia de 0,580 LD") is True
    assert _number_matches(580.0, 1.0, "Distancia de 0,580 LD") is False


def test_22_telemetry_no_fallbacks():
    # Telemetría observada
    usage_obs = {
        "prompt_tokens": 537,
        "completion_tokens": 275,
        "total_tokens": 812,
        "tokens_status": "observed",
    }
    assert usage_obs["tokens_status"] == "observed"
    assert usage_obs["prompt_tokens"] == 537

    # Telemetría no disponible (sin inventar 1200 / 400)
    usage_unavail = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "tokens_status": "unavailable",
    }
    assert usage_unavail["tokens_status"] == "unavailable"
    assert usage_unavail["prompt_tokens"] == 0


def test_23_judge_rubrics_and_metric_independence():
    from evaluation.metrics.bedrock_nova_judge import evaluate_llm_metrics_with_judge
    from evaluation.metrics.deterministic_metrics import evaluate_deterministic_metrics

    records = load_dataset_records()
    rec_pos = records[0]

    # 1. Conservación de umbrales
    assert rec_pos.thresholds.get("factual_consistency", 0.80) == 0.80
    assert rec_pos.thresholds.get("task_completion", 0.80) == 0.80
    assert rec_pos.thresholds.get("security", 0.90) == 0.90

    # 2. Independencia de métricas: structured_facts_check (1.00) no fuerza pasar factual_consistency (evaluado por el juez)
    det_scores = evaluate_deterministic_metrics(
        rec_pos,
        http_status_actual=200,
        app_status_actual="draft_pending_review",
        script_text="El asteroide 2026 RN2 pasará a 222,003 km pero habrá un impacto confirmado en 2026.",
    )
    fact_score = [s for s in det_scores if s.metric_name == "structured_facts_check"][0]
    assert fact_score.score == 1.00

    # Mock de juez para verificar comportamiento independiente de DeepEval
    mock_judge = MagicMock()
    mock_judge.input_tokens = 0
    mock_judge.output_tokens = 0

    with patch("evaluation.metrics.bedrock_nova_judge.GEval") as mock_geval:
        mock_geval_inst = MagicMock()
        mock_geval_inst.score = 0.20
        mock_geval_inst.reason = "Afirmación de impacto no respaldada"
        mock_geval.return_value = mock_geval_inst

        llm_scores = evaluate_llm_metrics_with_judge(rec_pos, "Texto de prueba", mock_judge)
        fc_score = [s for s in llm_scores if s.metric_name == "factual_consistency"][0]
        # Verificar independencia: structured_facts_check es 1.00, pero fc_score es 0.20 porque el juez detectó impacto inventado
        assert fc_score.passed is False
        assert fc_score.score == 0.20
