from typing import Any

from app.config import settings
from app.logger import logger

_langfuse_client = None

if settings.LANGFUSE_ENABLED and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Cliente de Langfuse inicializado exitosamente.")
    except Exception as exc:
        logger.warning(f"No se pudo inicializar Langfuse: {exc}. Continuando sin trazabilidad externa.")


def record_langfuse_trace(
    request_id: str,
    input_data: dict[str, Any],
    status: str,
    jpl_data: dict[str, Any] | None = None,
    factual_card: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    usage: dict[str, int] | None = None,
    durations: dict[str, float] | None = None,
) -> str | None:
    """Registra una traza de ejecución en Langfuse vinculada al request_id si LANGFUSE_ENABLED está activo.

    Si LANGFUSE_ENABLED=false o faltan credenciales, opera de manera transparente (no-op) sin fallar.
    """
    if not settings.LANGFUSE_ENABLED or _langfuse_client is None:
        return None

    try:
        trace = _langfuse_client.trace(
            id=request_id,
            name="generate_script_flow",
            user_id="academic_user",
            metadata={
                "provider": "Amazon Bedrock Runtime",
                "model": settings.BEDROCK_MODEL_ID,
                "region": settings.AWS_REGION,
                "durations_ms": durations or {},
            },
            input=input_data,
            output=output_data,
        )

        if jpl_data:
            trace.span(
                name="jpl_cad_query",
                input=input_data,
                output=jpl_data,
            )

        if factual_card:
            trace.span(
                name="factual_card_builder",
                input=jpl_data,
                output=factual_card,
            )

        if output_data and usage:
            trace.generation(
                name="bedrock_nova_lite_generation",
                model=settings.BEDROCK_MODEL_ID,
                input=factual_card,
                output=output_data,
                usage={
                    "input": usage.get("prompt_tokens", 0),
                    "output": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                },
            )

        _langfuse_client.flush()
        return request_id
    except Exception as exc:
        logger.warning(f"Error al emitir traza a Langfuse para request_id={request_id}: {exc}")
        return None
