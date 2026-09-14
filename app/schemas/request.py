from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class VideoFormat(str, Enum):
    """Formatos de video soportados."""

    SHORT = "short"  # Estructura ultra-dinámica de 30-60 segundos
    NEWS_BRIEF = "news_brief"  # Reporte informativo conciso de 60-120 segundos
    EXPLAINER = "explainer"  # Video explicativo profundo con analogías de 90-180 segundos


class TargetAudience(str, Enum):
    """Público objetivo del video divulgativo."""

    CHILDREN = "children"  # Niños de 8 a 12 años aproximadamente, lenguaje simple y cotidiano
    TEENS = "teens"  # Adolescentes, tono ágil y referencias culturales juveniles
    GENERAL = "general"  # Público general adulto, equilibrio de accesibilidad y rigor
    ENTHUSIASTS = "enthusiasts"  # Aficionados a la astronomía, datos técnicos y terminología precisa


class Tone(str, Enum):
    """Tono del guion divulgativo."""

    INFORMATIVE = "informative"  # Estilo periodístico y objetivo
    FRIENDLY = "friendly"  # Estilo cercano, conversacional y didáctico
    INTRIGUING = "intriguing"  # Estilo de misterio y asombro por el cosmos
    LIGHT_HUMOR = "light_humor"  # Estilo ameno con toques sutiles de humor


class ScriptGenerateRequest(BaseModel):
    """Esquema de entrada para el endpoint POST /scripts/generate."""

    start_date: date = Field(..., description="Fecha inicial del intervalo de búsqueda (YYYY-MM-DD)")
    end_date: date = Field(..., description="Fecha final del intervalo de búsqueda (YYYY-MM-DD)")
    video_format: VideoFormat = Field(
        default=VideoFormat.NEWS_BRIEF,
        description="Formato del video divulgativo",
    )
    duration_seconds: int = Field(
        default=90,
        ge=30,
        le=180,
        description="Duración objetivo del guion en segundos (entre 30 y 180)",
    )
    target_audience: TargetAudience = Field(
        default=TargetAudience.GENERAL,
        description="Público objetivo (children: 8-12 años)",
    )
    tone: Tone = Field(
        default=Tone.INFORMATIVE,
        description="Tono narrativo del guion",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "ScriptGenerateRequest":
        """Valida que la fecha final sea posterior o igual a la inicial y que el rango no supere los 30 días."""
        if self.end_date < self.start_date:
            raise ValueError("La fecha final (end_date) no puede ser anterior a la fecha inicial (start_date).")
        delta = (self.end_date - self.start_date).days
        if delta > 30:
            raise ValueError(f"El intervalo entre fechas no puede superar los 30 días. Rango solicitado: {delta} días.")
        return self
