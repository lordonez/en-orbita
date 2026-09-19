import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import verify_api_key
from app.logger import logger
from app.observability.langfuse_tracer import record_langfuse_trace
from app.schemas.request import ScriptGenerateRequest
from app.schemas.response import (
    ScriptContent,
    ScriptGenerateResponse,
)
from app.services.bedrock_service import generate_script_with_bedrock
from app.services.jpl_service import fetch_and_normalize_jpl_cad
from app.utils.metrics import calculate_estimated_duration, count_words


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida de la aplicación: valida configuraciones al arrancar."""
    settings.validate_required_settings()
    logger.info("Aplicación En órbita iniciada exitosamente con configuración validada.")
    yield


app = FastAPI(
    title="En órbita — Copiloto Editorial Espacial",
    description=(
        "Servicio de generación de guiones divulgativos factuales basados en datos oficiales "
        "de NASA/JPL CAD API y sintetizados mediante Amazon Bedrock Runtime (Amazon Nova Lite)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Manejador de excepciones HTTP para evitar filtración de trazas internas o secretos."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def custom_general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Manejador global de errores no capturados."""
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor. Consulte los registros estructurados."},
    )


@app.post(
    "/scripts/generate",
    response_model=ScriptGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar borrador de guion espacial factual",
    description=(
        "Autentica la solicitud mediante `X-API-Key`, valida los parámetros, consulta la API "
        "de NASA/JPL CAD, selecciona la aproximación con menor distancia nominal y genera un guion "
        "divulgativo en español con Amazon Bedrock Nova Lite."
    ),
)
async def generate_script(
    request: ScriptGenerateRequest,
    api_key: str = Depends(verify_api_key),
) -> ScriptGenerateResponse:
    """Endpoint principal de generación de guiones."""
    start_total_mono = time.monotonic()
    request_id = str(uuid.uuid4())

    # 1. Consultar y normalizar aproximaciones cercanas en JPL CAD API
    selected_event, source_info, factual_card, jpl_duration_ms = await fetch_and_normalize_jpl_cad(
        start_date=request.start_date,
        end_date=request.end_date,
    )

    video_config_dict = request.model_dump(mode="json")

    # 2. Manejo del flujo sin eventos (no_events)
    if selected_event is None or factual_card is None:
        total_duration_ms = round((time.monotonic() - start_total_mono) * 1000, 2)
        response_payload = ScriptGenerateResponse(
            request_id=request_id,
            status="no_events",
            video_config=video_config_dict,
            selected_event=None,
            selection_criterion=None,
            source_info=source_info,
            factual_card=None,
            script=None,
            visual_proposals=None,
            word_count=0,
            estimated_duration_seconds=0.0,
            reading_speed_wpm=150,
            observations=[
                f"No se encontraron aproximaciones cercanas a la Tierra (dist <= 0.05 AU) entre "
                f"{request.start_date} y {request.end_date} en la base de datos de JPL CAD."
            ],
            requires_human_review=False,  # Sin guion pendiente de aprobación
        )

        logger.info(
            "Solicitud procesada con estado no_events",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "status": "no_events",
                    "total_duration_ms": total_duration_ms,
                    "jpl_duration_ms": jpl_duration_ms,
                    "llm_duration_ms": 0.0,
                    "http_status": 200,
                }
            },
        )

        record_langfuse_trace(
            request_id=request_id,
            input_data=video_config_dict,
            status="no_events",
            jpl_data=source_info.model_dump(mode="json"),
            durations={"total_ms": total_duration_ms, "jpl_ms": jpl_duration_ms},
        )

        return response_payload

    # 3. Flujo con eventos: Invocación a Amazon Bedrock Nova Lite
    script_structure, usage, llm_duration_ms = await generate_script_with_bedrock(
        request=request,
        factual_card=factual_card,
    )

    # 4. Cálculo determinista de palabras y duración estimada de locución por código
    script_content = ScriptContent(
        title=script_structure.title,
        opening=script_structure.opening,
        development=script_structure.development,
        closure=script_structure.closure,
    )

    full_text = f"{script_content.title} {script_content.opening} {script_content.development} {script_content.closure}"
    word_count = count_words(full_text)
    estimated_duration = calculate_estimated_duration(word_count, wpm=150)

    total_duration_ms = round((time.monotonic() - start_total_mono) * 1000, 2)

    response_payload = ScriptGenerateResponse(
        request_id=request_id,
        status="draft_pending_review",
        video_config=video_config_dict,
        selected_event=selected_event,
        selection_criterion="Menor distancia nominal (dist) en el rango de fechas consultado",
        source_info=source_info,
        factual_card=factual_card,
        script=script_content,
        visual_proposals=script_structure.visual_proposals,
        word_count=word_count,
        estimated_duration_seconds=estimated_duration,
        reading_speed_wpm=150,
        observations=script_structure.observations,
        requires_human_review=True,  # Borrador sujeto a revisión editorial obligatoria
        telemetry={
            "llm_tokens": usage,
            "tokens_status": usage.get("tokens_status", "observed"),
        },
    )

    logger.info(
        "Guion generado exitosamente",
        extra={
            "extra_data": {
                "request_id": request_id,
                "status": "draft_pending_review",
                "total_duration_ms": total_duration_ms,
                "jpl_duration_ms": jpl_duration_ms,
                "llm_duration_ms": llm_duration_ms,
                "model": settings.BEDROCK_MODEL_ID,
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "word_count": word_count,
                "http_status": 200,
            }
        },
    )

    record_langfuse_trace(
        request_id=request_id,
        input_data=video_config_dict,
        status="draft_pending_review",
        jpl_data=source_info.model_dump(mode="json"),
        factual_card=factual_card,
        output_data=response_payload.model_dump(mode="json"),
        usage=usage,
        durations={
            "total_ms": total_duration_ms,
            "jpl_ms": jpl_duration_ms,
            "llm_ms": llm_duration_ms,
        },
    )

    return response_payload
