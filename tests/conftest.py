import os

import pytest
from fastapi.testclient import TestClient

# Configurar variables de entorno de prueba antes de importar app
os.environ["APP_API_KEY"] = "test-secret-key-12345"
os.environ["AWS_PROFILE"] = "en-orbita"
os.environ["AWS_REGION"] = "us-east-2"
os.environ["BEDROCK_MODEL_ID"] = "amazon.nova-lite-v1:0"
os.environ["LANGFUSE_ENABLED"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """Fixture de cliente de pruebas síncrono FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_headers():
    """Encabezados HTTP de autenticación válidos para pruebas."""
    return {"X-API-Key": "test-secret-key-12345"}
