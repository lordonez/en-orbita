# En órbita — Copiloto Editorial para Guiones de Noticias Espaciales

**"En órbita"** es un copiloto editorial estructurado para la generación de guiones divulgativos sobre fenómenos astronómicos basados en datos oficiales de la NASA/JPL y procesados mediante **Amazon Bedrock Runtime (Amazon Nova Micro como generador y Amazon Nova Lite como evaluador/juez)**.

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

### Creación y Activación del Entorno Virtual (Windows / PowerShell)
Desde la carpeta raíz del proyecto (`D:\Work\En Orbita`):
```powershell
# Crear entorno virtual
python -m venv .venv

# Activar en PowerShell
.\.venv\Scripts\Activate.ps1
```

### Instalación de Dependencias Reproducibles
```powershell
# Para ejecución en producción / servicio básico:
pip install -r requirements.txt

# Para desarrollo, suite de pruebas y runner de evaluación:
pip install -r requirements-dev.txt

# Verificar consistencia del entorno:
python -m pip check
```

### Variables de Entorno (`.env`)
Cree un archivo `.env` basado en `.env.example`:
```env
APP_API_KEY=en-orbita-key-2026
AWS_PROFILE=en-orbita
AWS_REGION=us-east-2
BEDROCK_MODEL_ID=us.amazon.nova-micro-v1:0

# Observabilidad Langfuse (Opcional - LANGFUSE_ENABLED=false por defecto)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

> **Importante**: No guarde Access Keys ni Secret Keys de AWS en `.env`. El servicio utiliza la cadena estándar de credenciales de AWS mediante `AWS_PROFILE=en-orbita`.

---

## 3. Ejecución del Servicio Local

Para iniciar el servidor local de desarrollo asegurándose de estar en la raíz del proyecto:
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Endpoints de Documentación
* **Swagger UI interactivo:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Especificación OpenAPI (JSON):** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
* **ReDoc alternativo:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Detención Limpia del Servicio
Para detener Uvicorn en PowerShell, presione:
```text
Ctrl + C
```
El servidor cerrará las conexiones activas y liberará el puerto 8000 de forma ordenada.

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

## 5. Pruebas Automatizadas y Calidad

Ejecute la suite de pruebas unitarias e integrales (con mocks deterministas, sin llamadas externas ni consumo de tokens en CI):
```powershell
# Verificación de integridad de dependencias
python -m pip check

# Verificación de lint y formato con Ruff
python -m ruff check .
python -m ruff format --check .

# Pruebas deterministas con Pytest (32 tests)
python -m pytest -v
```

---

## 6. Evidencias Reales Generadas

Ubicación de evidencias reales colectadas por sesión:
- **Sesión 2:** `evidencias/sesion-02/consulta_jpl_real.json` (consulta real y normalización de NASA/JPL CAD API).
- **Sesión 3:** `evidencias/sesion-03/respuesta_bedrock_real.json` y `mediciones_sesion3.json` (respuesta completa y 3 mediciones reales de latencia/tokens).
- **Sesión 4:** `evidencias/sesion-04/traza_langfuse.json` y `traza_langfuse.png` (trazabilidad y captura de panel Langfuse).
- **Sesión 5:** `evidencias/sesion-05/evaluacion_corregida.md` y `evaluacion_corregida.json` (evaluación formal de 100 casos con DeepEval y Juez Nova Lite, 79% de aprobación).
- **Sesión 6:** `evidencias/sesion-06/verificacion_operativa.md` (verificación de arranque, casos 401, 422 y ejecución válida real con telemetría observada de tokens y costos).

---

## 7. Solución de Problemas Frecuentes (Troubleshooting)

* **`ModuleNotFoundError: No module named 'app'`:**
  * *Causa:* El comando se ejecutó fuera del directorio del proyecto (por ejemplo, desde `C:\WINDOWS\system32`).
  * *Solución:* Navegue a la raíz del repositorio con `cd "D:\Work\En Orbita"` antes de iniciar Uvicorn o ejecutar scripts.

* **`HTTP 401 Unauthorized`:**
  * *Causa:* La solicitud no incluye la cabecera `X-API-Key` o el valor no coincide con la variable `APP_API_KEY` de `.env`.
  * *Solución:* En Swagger UI (`/docs`), pulse el botón verde **Authorize** en la esquina superior derecha, escriba el valor configurado en `.env` (ej. `en-orbita-key-2026`) y confirme.

* **`botocore.exceptions.ProfileNotFound`:**
  * *Causa:* El perfil local de AWS `en-orbita` no está configurado en el equipo.
  * *Solución:* Configure el perfil ejecutando `aws configure --profile en-orbita` e ingrese las credenciales con acceso a Amazon Bedrock en `us-east-2`.

* **Puerto 8000 en uso / servidor bloqueado:**
  * *Causa:* Un proceso anterior de Uvicorn no finalizó completamente.
  * *Solución:* En PowerShell, finalice los procesos Python huérfanos ejecutando `Stop-Process -Name "python" -Force` y reinicie el servidor.

---

## 8. Roadmap del Proyecto

- **Sesión 1 & 2 (Completada)**: Ficha del caso, contratos E/S y consulta real a JPL CAD API.
- **Sesión 3 (Completada)**: Flujo JPL → Bedrock, controles de auth (`X-API-Key`), validaciones Pydantic y mediciones reales.
- **Sesión 4 (Completada)**: Arquitectura del servicio y trazabilidad con Langfuse.
- **Sesión 5 (Completada)**: Golden Dataset v2 (100 casos), evaluación DeepEval con Juez Nova Lite (79% aprobado).
- **Sesión 6 (Completada)**: Verificación operativa final, protocolo 401/422/200, cálculo de costo observado y documentación.
- **Entrega Definitiva (Pendiente)**: Ajustes finales posteriores a la exposición académica.
