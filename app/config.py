from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación cargada desde variables de entorno."""

    APP_API_KEY: str = ""
    AWS_PROFILE: str = "en-orbita"
    AWS_REGION: str = "us-east-2"
    BEDROCK_GENERATOR_MODEL_ID: str = "us.amazon.nova-micro-v1:0"
    BEDROCK_EVALUATOR_MODEL_ID: str = "amazon.nova-lite-v1:0"

    @property
    def BEDROCK_MODEL_ID(self) -> str:
        """Propiedad de compatibilidad que retorna el modelo generador."""
        return self.BEDROCK_GENERATOR_MODEL_ID

    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    JPL_CAD_API_URL: str = "https://ssd-api.jpl.nasa.gov/cad.api"
    JPL_TIMEOUT_SECONDS: float = 10.0
    LLM_TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_required_settings(self) -> None:
        """Valida que las variables obligatorias estén presentes (fail-fast)."""
        if not self.APP_API_KEY or self.APP_API_KEY.strip() == "":
            raise RuntimeError(
                "Configuración inválida: La variable de entorno APP_API_KEY es obligatoria y no puede estar vacía."
            )


# Instancia singleton de configuración
settings = Settings()
