# Documento Oficial de Seguimiento del Proyecto: "En órbita"

**Estudiante:** Leonardo Ordóñez  
**Proyecto:** En órbita — Copiloto Editorial para la Generación de Guiones Espaciales Factuales  
**Curso:** Integración de Modelos de Lenguaje  
**Proveedor LLM:** Amazon Bedrock Runtime — Amazon Nova Lite (`boto3.client('bedrock-runtime').converse()`)  
**Autenticación AWS:** Cadena estándar de credenciales AWS (`AWS_PROFILE=en-orbita`, `us-east-2`) (sin Access Keys en `.env`)  
**Repositorio:** https://github.com/lordonez/en-orbita  
**Estado General:** **Sesiones 1, 2, 3 y 4 Completadas y Verificadas con Evidencias Reales**.

---

## 1. Ficha del Proyecto y Caso de Uso

### 1.1 Propósito y Alcance
"En órbita" es un copiloto editorial estructurado que convierte información astronómica oficial (procedente de la API de Aproximaciones Cercanas de la NASA/JPL) en borradores de guiones divulgativos en español adaptados a diferentes formatos de video, duraciones, audiencias y tonos.

### 1.2 Límites del Producto
- **Integración Inicial Exclusiva:** NASA/JPL Close Approach Data (CAD) API (`https://ssd-api.jpl.nasa.gov/cad.api`).
- **Proveedor LLM:** **Amazon Bedrock Runtime** utilizando el modelo **Amazon Nova Lite** (`amazon.nova-lite-v1:0` en `us-east-2`) a través de la API `Converse` de Boto3.
- **Sin Access Keys en `.env`:** Se utiliza la cadena estándar de credenciales de AWS (`AWS_PROFILE=en-orbita`).
- **No Generación Audiovisual Directa:** El producto genera borradores de guion estructurados y sugerencias visuales descriptivas. No produce ni publica archivos de video ni audio.
- **Sin Invención ni Inferencia Científica:** El sistema no calcula órbitas, no predice trayectorias de impacto ni inventa visibilidad local. La información factual proviene estrictamente del código de selección sobre la API oficial.
- **Sin Agentes Autónomos:** El patrón arquitectónico es una orquestación determinista guiada por código con llamada directa al LLM. No se utilizan frameworks de agentes autónomos.
- **Firma / Revisión Humana:** Todo guion generado se marca con `requires_human_review: true` y estado `draft_pending_review`. La aprobación editorial para publicación es un proceso humano externo no automatizado en esta fase.

---

## 2. Arquitectura, Patrón y Responsabilidades

```
[ Cliente HTTP ]
       │  POST /scripts/generate (con X-API-Key)
       ▼
[ FastAPI App (app/main.py) ]
       │
       ├─► [ Security Auth ] (secrets.compare_digest -> HTTP 401 si falla)
       ├─► [ Input Validation ] (schemas/request.py: fechas <= 30d, duracion 30-180s)
       │
       ├─► [ JPL Service (app/services/jpl_service.py) ]
       │      │ GET https://ssd-api.jpl.nasa.gov/cad.api (con timeout de 10s)
       │      └─► Normalización & Selección determinista por menor `dist` (AU -> km/LD)
       │
       ├─► [ Factual Card Builder ] (Código Python genera ficha factual limpia)
       │
       ├─► [ Bedrock Service (app/services/bedrock_service.py) ]
       │      │ boto3.client('bedrock-runtime').converse() en threadpool [Amazon Nova Lite]
       │      └─► Adaptación de guion (Apertura, Desarrollo, Cierre) y validación Pydantic
       │
       └─► [ Metrics & Formatter (app/utils/metrics.py) ]
              │ Conteo de palabras + estimación a 150 palabras/minuto
              └─► JSON Log estructurado (tokens de Bedrock) + Traza Langfuse (request_id)
```

---

## 3. Contratos de Entrada y Salida

### 3.1 Contrato de Entrada (`POST /scripts/generate`)
- **Headers:** `X-API-Key: <APP_API_KEY>`
- **Body JSON:**
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

---

## 4. Estado Actual del Avance por Sesiones

| Sesión | Tema / Entregable | Estado | Evidencias / Enlace |
| :--- | :--- | :---: | :--- |
| **Sesión 1 & 2** | Ficha del caso, contratos de entrada/salida y consulta real a JPL CAD API | **Implementado y Verificado** | [`evidencias/sesion-02/consulta_jpl_real.json`](file:///d:/Work/En%20Orbita/evidencias/sesion-02/consulta_jpl_real.json) |
| **Sesión 3** | Flujo JPL → Bedrock Nova Lite, validación Pydantic, auth (401) y 3 ejecuciones de mediciones | **Implementado y Verificado** | [`evidencias/sesion-03/respuesta_bedrock_real.json`](file:///d:/Work/En%20Orbita/evidencias/sesion-03/respuesta_bedrock_real.json)<br>[`evidencias/sesion-03/mediciones_sesion3.json`](file:///d:/Work/En%20Orbita/evidencias/sesion-03/mediciones_sesion3.json) |
| **Sesión 4** | Diagrama de arquitectura, responsabilidades de patrón y traza real con Langfuse | **Implementado y Verificado** | [`evidencias/sesion-04/traza_langfuse.json`](file:///d:/Work/En%20Orbita/evidencias/sesion-04/traza_langfuse.json)<br>[`evidencias/sesion-04/traza_langfuse.png`](file:///d:/Work/En%20Orbita/evidencias/sesion-04/traza_langfuse.png) |
| **Sesión 5** | 5 Casos de prueba deterministas (pytest) y evaluación de calidad con DeepEval (G-Eval) | **Trabajo Posterior** | `evidencias/sesion-05/evaluacion_deepeval.json` *(pendiente)* |
| **Sesión 6** | Demostración funcional (5 min), plan de operación final y entrega definitiva | **Trabajo Posterior** | `evidencias/final/plan_operacion.md` *(pendiente)* |

---

## 5. Mediciones y Desempeño (Sesión 3 - Resultados Reales Colectados)

- **Objeto espacial seleccionado:** `(2026 RN2)` a 0.001484 AU (221,933.43 km / 0.58 LD).
- **Consumo de tokens por llamada Bedrock (promedio):** ~538 prompt tokens + ~515 completion tokens (~1,050 total tokens).
- **Resultados de las 3 ejecuciones de latencia desde el cliente (`time.monotonic()`):**
  - **Ejecución 1:** 5,681.35 ms
  - **Ejecución 2:** 5,724.09 ms
  - **Ejecución 3:** 5,352.05 ms
  - **Media:** **5,585.83 ms** | **Mínimo:** **5,352.05 ms** | **Máximo:** **5,724.09 ms**

---

## 6. Registro de Cambios y Decisiones Técnicas

- **2026-09-09:** Implementación completa del bloque correspondiente a las Sesiones 1, 2, 3 y 4.
- **Verificación de Seguridad AWS:** Perfil AWS CLI `en-orbita` verificado en región `us-east-2` utilizando el modelo `amazon.nova-lite-v1:0`.
- **Verificación de Calidad:** Pruebas `pytest` (9/9 pasadas) y linters `ruff` (0 errores).
