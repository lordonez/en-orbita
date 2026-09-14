import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

# Esquema de seguridad para OpenAPI / Swagger UI (habilita el botón verde 'Authorize' en /docs)
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: str | None = Depends(api_key_header_scheme)) -> str:
    """Valida la clave API del cliente mediante comparación en tiempo constante.

    Si el encabezado X-API-Key está ausente o es inválido, rechaza con HTTP 401 Unauthorized
    sin realizar llamadas externas ni filtrar detalles internos.
    """
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.APP_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación fallida: X-API-Key ausente o inválida.",
        )
    return x_api_key
