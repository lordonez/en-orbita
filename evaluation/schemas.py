from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AuthScenarioEnum(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    INCORRECT = "incorrect"
    EMPTY = "empty"
    MALFORMED = "malformed"


class ExpectedFactAlternative(BaseModel):
    value: float
    unit: str
    tolerance: float = 0.001


class ExpectedFact(BaseModel):
    name: str
    value: float
    unit: str
    tolerance: float = 0.001
    required: bool = True
    accepted_alternatives: list[ExpectedFactAlternative] = Field(default_factory=list)


class GroundTruth(BaseModel):
    expected_behavior: str
    mandatory_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_editorial_criteria: str = ""
    expected_facts: list[ExpectedFact] = Field(default_factory=list)


class ExecutionSources(BaseModel):
    jpl: Literal["real", "fixture", "not_applicable"]
    generator: Literal["real", "mock", "not_applicable"]
    judge: Literal["real", "mock", "not_applicable"]

    @model_validator(mode="after")
    def validate_coherent_sources(self) -> "ExecutionSources":
        if self.generator == "not_applicable" and self.judge != "not_applicable":
            raise ValueError("Si el generador es 'not_applicable', el juez debe ser 'not_applicable'.")
        if self.jpl == "not_applicable" and self.generator == "real":
            raise ValueError("No se puede ejecutar el generador en 'real' si JPL es 'not_applicable'.")
        return self


class GoldenCaseRecord(BaseModel):
    id: str
    category: Literal["positive", "boundary_variant", "controlled_error", "adversarial"]
    description: str
    request: dict[str, Any]
    auth_scenario: AuthScenarioEnum = AuthScenarioEnum.VALID
    jpl_fixture_file: str | None = None
    provider_scenario: str | None = None
    expected_http_status: int
    expected_app_status: str
    ground_truth: GroundTruth
    execution_sources: ExecutionSources
    applicable_metrics: list[str]
    thresholds: dict[str, float]


class CaseMetricScore(BaseModel):
    metric_name: str
    score: float
    threshold: float
    passed: bool
    reason: str = ""


class EvaluationResult(BaseModel):
    case_id: str
    category: str
    description: str
    status: Literal["passed", "failed", "evaluation_error"]
    http_status_actual: int
    app_status_actual: str
    metrics: list[CaseMetricScore] = Field(default_factory=list)
    execution_sources: ExecutionSources
    tokens_micro_in: int = 0
    tokens_micro_out: int = 0
    tokens_lite_in: int = 0
    tokens_lite_out: int = 0
    tokens_status: Literal["observed", "unavailable"] = "unavailable"
    cost_usd: float = 0.0
    error_message: str | None = None
