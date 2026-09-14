from typing import Any

from pydantic import BaseModel, Field


class ScriptContent(BaseModel):
    """Estructura del guion dividido en secciones narrativas."""

    title: str = Field(..., description="Título atractivo y adecuado al público objetivo")
    opening: str = Field(..., description="Apertura / Gancho inicial (hook)")
    development: str = Field(..., description="Desarrollo factual y divulgativo")
    closure: str = Field(..., description="Cierre y llamado a la acción o reflexión final")


class ScriptStructure(BaseModel):
    """Esquema interno para la validación Pydantic del JSON generado por Bedrock Nova Lite."""

    title: str
    opening: str
    development: str
    closure: str
    visual_proposals: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)


class NormalizedEvent(BaseModel):
    """Datos normalizados de una aproximación cercana devuelta por la API de JPL CAD."""

    object_fullname: str = Field(..., description="Nombre completo o designación del objeto espacial")
    cd_date_str: str = Field(..., description="Fecha y hora de la aproximación cercana en escala de tiempo TDB (JPL)")
    dist_au: float = Field(..., description="Distancia nominal mínima en Unidades Astronómicas (AU)")
    dist_km: float = Field(..., description="Distancia nominal mínima convertida a kilómetros (km)")
    dist_ld: float = Field(..., description="Distancia nominal mínima convertida a Distancias Lunares (LD)")
    v_rel_kms: float = Field(..., description="Velocidad relativa respecto a la Tierra en km/s")
    v_inf_kms: float | None = Field(default=None, description="Velocidad al infinito en km/s (si está disponible)")
    h_mag: float | None = Field(default=None, description="Magnitud absoluta H del objeto (si está disponible)")


class SourceInfo(BaseModel):
    """Metadatos de la fuente de datos oficial consultada."""

    provider: str = Field(default="NASA/JPL SBDB Close-Approach Data API")
    endpoint: str = Field(default="https://ssd-api.jpl.nasa.gov/cad.api")
    query_params: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: str = Field(..., description="Estampa de tiempo UTC en que se consultó a la API de JPL")


class ScriptGenerateResponse(BaseModel):
    """Esquema de respuesta final devuelto por el servicio `POST /scripts/generate`."""

    request_id: str = Field(..., description="Identificador único de la solicitud (UUID v4)")
    status: str = Field(..., description="Estado del resultado: 'draft_pending_review' o 'no_events'")
    video_config: dict[str, Any] = Field(..., description="Parámetros de configuración del video utilizados")
    selected_event: NormalizedEvent | None = Field(
        default=None,
        description="Evento espacial seleccionado determinísticamente por menor distancia nominal",
    )
    selection_criterion: str | None = Field(
        default=None,
        description="Criterio de selección utilizado (menor distancia nominal en AU)",
    )
    source_info: SourceInfo = Field(..., description="Información y metadatos de la fuente JPL consultada")
    factual_card: dict[str, Any] | None = Field(
        default=None,
        description="Ficha factual construida determinísticamente por código para respaldo del LLM",
    )
    script: ScriptContent | None = Field(
        default=None,
        description="Borrador de guion generado (solamente presente cuando status es 'draft_pending_review')",
    )
    visual_proposals: list[str] | None = Field(
        default=None,
        description="Sugerencias visuales identificadas como propuestas didácticas",
    )
    word_count: int = Field(default=0, description="Número de palabras total de la narración del guion")
    estimated_duration_seconds: float = Field(
        default=0.0,
        description="Duración estimada de lectura calculada por código a 150 palabras/minuto",
    )
    reading_speed_wpm: int = Field(default=150, description="Velocidad de lectura utilizada (palabras por minuto)")
    observations: list[str] = Field(
        default_factory=list,
        description="Observaciones del sistema (ej. datos faltantes en la API, limitaciones de duración)",
    )
    requires_human_review: bool = Field(
        default=True,
        description="Indica si el borrador requiere revisión editorial humana obligatoria antes de su publicación",
    )
