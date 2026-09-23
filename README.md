# En órbita — Copiloto Editorial para Guiones de Noticias Espaciales

**"En órbita"** es un copiloto editorial estructurado para la generación de guiones divulgativos sobre fenómenos astronómicos basados en datos oficiales de la NASA/JPL y procesados mediante **Amazon Bedrock Runtime (Amazon Nova Lite)**.

---

## 1. Propósito y Alcance del Proyecto

El sistema recibe un rango de fechas y parámetros editoriales (formato, duración, público objetivo y tono), consulta la API de Aproximaciones Cercanas (CAD) de la NASA/JPL, normaliza los datos en unidades legibles (km y Distancias Lunares LD), selecciona determinísticamente la aproximación con menor distancia nominal, y genera un borrador de guion dividido en apertura, desarrollo y cierre con sugerencias visuales.

### Límites del Producto
- **No Generación Audiovisual Directa:** El producto genera guiones en texto y propuestas visuales descriptivas.
- **Sin Invención ni Inferencia Científica:** El sistema no calcula órbitas, no predice trayectorias de impacto ni inventa visibilidad local.
- **Sin Agentes Autónomos:** El patrón arquitectónico es una orquestación determinista por código con llamada directa al LLM.
- **Revisión Editorial Obligatoria:** Todo guion generado se marca con `requires_human_review: true` y estado `draft_pending_review`.

---

## 2. Requisitos y Configuración de Entorno

### Requisitos Previos
- **Python 3.13.0** (o superior compatible).
- **AWS CLI** configurado con el perfil `en-orbita` (`AWS_PROFILE=en-orbita`) y credenciales con permiso de invocación a Amazon Bedrock en `us-east-2`.

### Instalación de Dependencias Reproducibles
```powershell
# En Windows PowerShell / Cmd
pip install -r requirements.txt
```

### Variables de Entorno (`.env`)
Cree un archivo `.env` basado en `.env.example`:
```env
APP_API_KEY=<YOUR_APP_API_KEY>
AWS_PROFILE=en-orbita
AWS_REGION=us-east-2
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0

# Observabilidad Langfuse (Opcional - LANGFUSE_ENABLED=false por defecto)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

> **Importante**: No guarde Access Keys ni Secret Keys de AWS en `.env`. El servicio utiliza la cadena estándar de credenciales de AWS mediante `AWS_PROFILE=en-orbita`.

---

## 3. Ejecución del Servicio Local

Para iniciar el servidor local de desarrollo:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Acceda a la interfaz Swagger interactiva en el navegador:
`http://127.0.0.1:8000/docs`

---

## 4. Uso del Endpoint y Parámetros (`POST /scripts/generate`)

### Encabezados Requeridos
- `X-API-Key`: Clave de autenticación propia del servicio (definida en `APP_API_KEY`).

### Ejemplo de Cuerpo de Solicitud (JSON)
```json
{
  "start_date": "2026-09-08",
  "end_date": "2026-09-30",
  "video_format": "news_brief",
  "duration_seconds": 90,
  "target_audience": "general",
  "tone": "informative"
}
```

### Parámetros Disponibles
- `start_date` / `end_date`: Fechas inicial y final obligatorias (formato `YYYY-MM-DD`, intervalo máximo de 30 días).
- `video_format`: `short` (30-60s), `news_brief` (60-120s, defecto), `explainer` (90-180s).
- `duration_seconds`: Entero entre 30 y 180 (defecto: 90).
- `target_audience`: `children` (8-12 años), `teens`, `general` (defecto), `enthusiasts`.
- `tone`: `informative` (defecto), `friendly`, `intriguing`, `light_humor`.

---

## 5. Pruebas Automatizadas y Calidad

Ejecute la suite de pruebas unitarias e integrales (con mocks, sin consumo de tokens en CI):
```powershell
# Verificación de lint y formato con Ruff
ruff check .
ruff format --check .

# Pruebas deterministas con Pytest
pytest -v
```

---

## 6. Evidencias Reales Generadas (Sesiones 1 a 4)

Ubicación de evidencias reales colectadas:
- `evidencias/sesion-02/consulta_jpl_real.json`: Respuesta y normalización de consulta real a NASA/JPL CAD API.
- `evidencias/sesion-03/respuesta_bedrock_real.json`: Respuesta real completa devuelta por Amazon Bedrock Nova Lite.
- `evidencias/sesion-03/mediciones_sesion3.json`: Mediciones reales consecutivas de latencia cliente (`time.monotonic()`) y tokens.
- `evidencias/sesion-04/traza_langfuse.json` & `traza_langfuse.png`: Traza de observabilidad e imagen del panel de Langfuse.

Para regenerar las evidencias reales:
```powershell
python scripts/generate_session2_evidence.py
python scripts/generate_session3_evidence.py
python scripts/generate_session4_evidence.py
```

---

## 7. Roadmap del Proyecto

- **Sesión 1 & 2 (Completada)**: Ficha del caso, contratos E/S y consulta real a JPL CAD API.
- **Sesión 3 (Completada)**: Flujo JPL → Bedrock Nova Lite, controles de auth (`X-API-Key`), validaciones Pydantic y 3 mediciones reales.
- **Sesión 4 (Completada)**: Arquitectura del servicio y trazabilidad con Langfuse.
- **Sesión 5 (Trabajo Posterior)**: Evaluación con DeepEval (G-Eval) sobre 5 casos de prueba.
- **Sesión 6 (Trabajo Posterior)**: Demostración funcional (5 min), plan de operación final y entrega definitiva.
