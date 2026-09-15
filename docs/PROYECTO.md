# Proyecto: En órbita

Copia este archivo a docs/PROYECTO.md en tu propio repositorio. Reemplaza los campos entre corchetes; conserva los apartados y actualízalos durante el curso. El trabajo es individual. El calendario y la rúbrica están en la guía del proyecto entregada por el docente.

Estudiante: Leonardo Ordóñez

Repositorio: https://github.com/lordonez/en-orbita

---

## Sesión 1 · Borrador de la ficha, sin entrega formal

- **Usuario**: Creadores de contenido, educadores y periodistas científicos que necesitan guiones divulgativos breves y rigurosos sobre eventos astronómicos espaciales.
- **Problema**: Convertir datos astronómicos crudos y complejos provenientes de agencias oficiales en guiones de video atractivos adaptados a diferentes audiencias, sin incurrir en imprecisiones, cálculos erróneos ni sesgos sensacionalistas.
- **Resultado útil**: Borrador de guion estructurado en español (apertura, desarrollo y cierre) acompañado de propuestas visuales descriptivas y una estimación de tiempo de locución calculada a 150 palabras/minuto.
- **API elegida y documentación**: NASA/JPL Close Approach Data (CAD) API ([https://ssd-api.jpl.nasa.gov/doc/cad.html](https://ssd-api.jpl.nasa.gov/doc/cad.html)).
- **Acceso y límites**: API pública de libre acceso que no requiere clave de autenticación (API Key). Límites revisados: ejecuciones seriadas en código (un solo proceso concurrente en fase académica) para respetar las condiciones de uso de los servidores de la NASA/JPL.
- **Entrada de ejemplo**:
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
- **Salida esperada**: JSON con `request_id`, `status: draft_pending_review`, datos del evento seleccionado `(2026 RN2)`, ficha factual limpia de respaldo, guion dividido en apertura, desarrollo y cierre, sugerencias visuales, conteo de palabras, duración estimada de locución y la marca `requires_human_review: true`.
- **Trabajo del código**: Consulta la API de JPL CAD (`body=Earth`, `dist-max=0.05`, `sort=dist`, `limit=10`), convierte unidades determinísticamente (AU a kilómetros y Distancias Lunares LD), selecciona la aproximación con menor distancia nominal y construye la ficha factual de respaldo.
- **Trabajo del LLM**: Adapta la ficha factual factual al formato (`news_brief`), público objetivo (ej. `children` para niños de 8 a 12 años con lenguaje sencillo), duración y tono deseados en español, generando el guion estructurado y propuestas visuales.
- **Alcance**: Sí resuelve la consulta oficial a la NASA, normalización de datos, selección determinista y generación de borrador de guion con Amazon Bedrock Nova Lite. Queda fuera: generación audiovisual (audio/video), cálculo de órbitas o predicción de impactos, y publicación automatizada.

---

## Sesión 2 · Primer avance: ficha definida, contrato y consulta

- **Ruta de tu servicio**: `POST /scripts/generate`
- **Entrada**:
  - `start_date` (string `YYYY-MM-DD`, obligatorio)
  - `end_date` (string `YYYY-MM-DD`, obligatorio; rango máximo de 30 días)
  - `video_format` (string enum: `short`, `news_brief`, `explainer`; opcional, predeterminado: `news_brief`)
  - `duration_seconds` (integer entre `30` y `180`; opcional, predeterminado: `90`)
  - `target_audience` (string enum: `children` [8-12 años], `teens`, `general`, `enthusiasts`; opcional, predeterminado: `general`)
  - `tone` (string enum: `informative`, `friendly`, `intriguing`, `light_humor`; opcional, predeterminado: `informative`)
- **Salida**: `request_id` (uuid), `status` (`draft_pending_review` o `no_events`), `video_config` (dict), `selected_event` (nombre, fecha TDB, distancia AU/km/LD, velocidad), `selection_criterion` (string), `source_info` (proveedor, endpoint, parámetros, estampa UTC), `factual_card` (dict), `script` (`title`, `opening`, `development`, `closure`), `visual_proposals` (list), `word_count` (int), `estimated_duration_seconds` (float), `reading_speed_wpm` (150), `observations` (list) y `requires_human_review` (bool).
- **Respuestas de error**:
  - `401 Unauthorized`: Encabezado `X-API-Key` ausente o inválido (rechazo de tiempo constante con `secrets.compare_digest` sin llamadas externas).
  - `422 Unprocessable Entity`: Rango de fechas invertido (`end_date < start_date`), intervalo mayor a 30 días o duración fuera del rango `[30, 180]`.
  - `502 Bad Gateway`: Fallo en la comunicación con NASA/JPL CAD API o Amazon Bedrock Runtime.
  - `504 Gateway Timeout`: Timeout al conectar con JPL CAD (10s) o Amazon Bedrock.
  - `500 Internal Server Error`: Error interno no capturado o salida del LLM no conforme con el esquema Pydantic `ScriptStructure`.
- **Consulta real a la API externa**: [`../evidencias/sesion-02/consulta_jpl_real.json`](../evidencias/sesion-02/consulta_jpl_real.json) (Consulta realizada el 2026-09-09 conteniendo la solicitud, respuesta completa de JPL y selección del objeto `(2026 RN2)` a `0.001484 AU` / `221,933.43 km`).
- **Punto de integración del LLM**: Módulo [`../app/services/bedrock_service.py`](../app/services/bedrock_service.py), función `generate_script_with_bedrock` que invoca el método `boto3.client('bedrock-runtime').converse()` en un threadpool (`run_in_threadpool`).

---

## Sesión 3 · Funcionamiento y mediciones

- **Ejecución completa con API externa y LLM**: Evidencia en [`../evidencias/sesion-03/respuesta_bedrock_real.json`](../evidencias/sesion-03/respuesta_bedrock_real.json) (Ejecución realizada el 2026-09-09 utilizando el modelo `amazon.nova-lite-v1:0` en la región `us-east-2`, con `1,010` tokens totales consumidos y guion generado de 176 palabras).
- **Entrada inválida o incompleta**: Pruebas automatizadas en [`../tests/test_generate.py`](../tests/test_generate.py) (`test_invalid_date_range_inverted`, `test_invalid_date_range_exceeds_30_days`, `test_invalid_duration_seconds`) que verifican la respuesta HTTP `422 Unprocessable Entity`.
- **Solicitud sin autorización**: Pruebas automatizadas en [`../tests/test_auth.py`](../tests/test_auth.py) (`test_missing_api_key_returns_401` y `test_invalid_api_key_returns_401`) que rechazan la petición con HTTP `401 Unauthorized` sin invocar APIs externas.
- **Solicitud usada para medir**: [`../evidencias/sesion-03/mediciones_sesion3.json`](../evidencias/sesion-03/mediciones_sesion3.json)
- **Entorno y condiciones**: Servidor FastAPI local en Windows PowerShell con Python 3.13.0, modelo `amazon.nova-lite-v1:0` en AWS `us-east-2` (perfil AWS CLI `en-orbita`), solicitud fija (`news_brief`, 90s, público general, tono informativo, fechas `2026-09-08` a `2026-09-30`), tamaño aproximado de entrada: ~538 prompt tokens.

| Ejecución | Tiempo total | Primer texto, si hay streaming | Resultado o error |
| :---: | :---: | :---: | :--- |
| 1 | 5689.49 ms | No aplica | Exitoso (`draft_pending_review`, request_id: `60a9935f-b176-4655-9b00-fd5a064ab0bf`, 221 palabras) |
| 2 | 5730.07 ms | No aplica | Exitoso (`draft_pending_review`, request_id: `f310c694-d45f-414a-8cd9-080873f4fe41`, 203 palabras) |
| 3 | 5360.76 ms | No aplica | Exitoso (`draft_pending_review`, request_id: `f6ab8133-00da-4cc5-b501-c1b608a63ce9`, 196 palabras) |

- **Conclusión de la medición**: Latencia cliente promedio de **5,593.44 ms** (mínima: 5,360.76 ms, máxima: 5,730.07 ms). El tiempo total está dominado por la llamada síncrona a Amazon Bedrock Nova Lite en threadpool (~4.6s) y la consulta a la API de JPL CAD (~1.0s). La ausencia de streaming se justifica porque el servicio debe estructurar y validar la respuesta JSON completa con Pydantic antes de entregarla al cliente. La muestra de 3 ejecuciones permite observar la estabilidad del flujo inicial en pruebas locales, pero no constituye una prueba de capacidad ni de carga concurrente masiva.

---

## Sesión 4 · Arquitectura y trazabilidad

- **Diagrama**:

```mermaid
graph TD
    A[Cliente HTTP / Swagger UI] -->|POST /scripts/generate X-API-Key| B[FastAPI App app/main.py]
    B -->|1. Autenticar secrets.compare_digest| C{X-API-Key Valido?}
    C -->|No| D[HTTP 401 Unauthorized]
    C -->|Si| E[2. Validar entrada schemas/request.py]
    E -->|3. Consultar JPL CAD| F[JPL Service app/services/jpl_service.py]
    F -->|GET ssd-api.jpl.nasa.gov/cad.api| G[NASA/JPL CAD API]
    G -->|Respuesta JSON| F
    F -->|4. Normalizar & Seleccionar menor dist| H[Factual Card Builder]
    H -->|5. Invocacion asincrona en threadpool| I[Bedrock Service app/services/bedrock_service.py]
    I -->|boto3 converse| J[Amazon Bedrock Runtime Nova Lite us-east-2]
    J -->|Respuesta JSON| I
    I -->|6. Validar Pydantic ScriptStructure| K[Metrics & Formatter app/utils/metrics.py]
    K -->|7. Conteo palabras & 150 wpm| L[JSON Logs & Langfuse Tracer]
    L --> M[Respuesta HTTP 200 OK]
```

- **Patrón elegido**: Orquestación determinista guiada por código con llamada directa al LLM. Corresponde al caso de uso porque la consulta astronómica a la NASA, la normalización de unidades de distancia/velocidad y la selección del evento de menor distancia nominal deben ser 100% exactas y deterministas en Python. El LLM se utiliza exclusivamente para adaptar y narrar la información factual de respaldo.
- **Alternativa considerada**: Patrón de agente autónomo con bucle de razonamiento y selección dinámica de herramientas (Tool Calling / ReAct Agent). No es necesaria ni deseable en esta etapa por introducir latencia no determinista y riesgo de alucinación en la selección de fuentes astronómicas.
- **Responsabilidades**:
  - `app/services/jpl_service.py`: Realiza la consulta HTTP a la API de JPL CAD, mapea la respuesta dinámicamente según `fields`, convierte AU a kilómetros y Distancias Lunares LD, y selecciona el evento con menor distancia nominal.
  - `app/schemas/request.py`: Valida los tipos de datos, fechas (intervalo max. 30 días) y enums editoriales.
  - `app/services/bedrock_service.py`: Construye las instrucciones del sistema y el prompt, invoca a Amazon Bedrock Nova Lite en un threadpool y valida la salida JSON con Pydantic.
  - `app/utils/metrics.py`: Cuenta determinísticamente las palabras de la narración y calcula el tiempo estimado de lectura a 150 wpm.
  - `app/observability/langfuse_tracer.py`: Registra la traza de ejecución completa en Langfuse vinculada al `request_id`.
- **Traza**: Trace ID `b0248daa-dd6d-44bc-8c42-0fa0219a1007`. Archivo JSON: [`../evidencias/sesion-04/traza_langfuse.json`](../evidencias/sesion-04/traza_langfuse.json). Captura visual accesible: [`../evidencias/sesion-04/traza_langfuse.png`](../evidencias/sesion-04/traza_langfuse.png).
- **Qué muestra**: Muestra la solicitud de entrada validada, el span `jpl_cad_query` (1,123.27 ms) con el objeto `(2026 RN2)`, el span `factual_card_builder` (2.15 ms), la generación con Bedrock `bedrock_nova_lite_generation` (4,991.09 ms, 1,010 tokens) y la respuesta JSON final estructurada con estado 200 OK.
- **Si no pudo verificarse**: No aplica; la traza de observabilidad fue verificada y registrada tanto en JSON como en captura de imagen.

---

## Sesión 5 · Evaluación y correcciones

[Pendiente de ejecución para la Sesión 5]

Explica cuáles son ejecuciones reales y cuáles usan dependencias controladas para reproducir un fallo. Los casos deben pertenecer a tu aplicación, no ser resultados copiados del lab.

| Caso | Entrada | Resultado esperado | Resultado obtenido | Evidencia | Conclusión |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Válido | `start_date: 2026-09-08`, `end_date: 2026-09-30`, público general | Guion adaptado con respaldo factual | [Pendiente Sesión 5] | `../evidencias/sesion-05/evaluacion_deepeval.json` | [Pendiente] |
| Variante válida | Mismos datos, `target_audience: children` | Lenguaje adaptado a 8-12 años con analogías sencillas | [Pendiente Sesión 5] | `../evidencias/sesion-05/evaluacion_deepeval.json` | [Pendiente] |
| Datos faltantes | Omisión de `end_date` | Rechazo 422 Unprocessable Entity | [Pendiente Sesión 5] | [`../tests/test_generate.py`](../tests/test_generate.py) | [Pendiente] |
| Datos inválidos | `duration_seconds: 500` o fechas invertidas | Rechazo 422 Unprocessable Entity | [Pendiente Sesión 5] | [`../tests/test_generate.py`](../tests/test_generate.py) | [Pendiente] |
| Proveedor falla o no devuelve resultados | Rango sin eventos coincidentes | Retorno de status `no_events` sin consumir LLM | [Pendiente Sesión 5] | [`../tests/test_generate.py`](../tests/test_generate.py) | [Pendiente] |

- **Pruebas deterministas**: Comando `pytest -v` (ejecuta 9 pruebas unitarias e integrales mockeadas sin consumir API Keys ni tokens externos).
- **Métrica DeepEval**: Métrica G-Eval para medir consistencia factual frente a la ficha factual y adherencia a los parámetros editoriales (umbral propuesto: 0.8).
- **Juez, si se usa**: Proveedor Amazon Bedrock / OpenAI para evaluación con DeepEval.
- **Resultados**: `../evidencias/sesion-05/evaluacion_deepeval.json` *(pendiente de ejecución)*.
- **Corrección realizada**: [Pendiente de registro tras la evaluación de la Sesión 5].

---

## Sesión 6 · Demostración y plan de operación

[Pendiente de ejecución para la Sesión 6]

- **Arranque, prueba y detención**: Ver secciones *"Instalación y Configuración"* y *"Ejecución del Servicio Local"* en [`../README.md`](../README.md).
- **Configuración**: Variables documentadas en [`../.env.example`](../.env.example) (`APP_API_KEY`, `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `LANGFUSE_ENABLED`).
- **Acceso y datos**: El cliente envía los parámetros editoriales a FastAPI mediante el encabezado `X-API-Key`. FastAPI consulta la API pública `https://ssd-api.jpl.nasa.gov/cad.api`. La ficha factual construida en código se envía a Amazon Bedrock Runtime Nova Lite (`us-east-2`). Las credenciales de AWS se manejan vía perfil `en-orbita` de la cadena estándar de AWS (nunca almacenadas en código ni en `.env`).
- **Costo**: Estimación basada en la tarifa oficial de Amazon Nova Lite (región us-east-2): ~$0.00006 por 1,000 input tokens y ~$0.00024 por 1,000 output tokens. Cada generación de guion consume ~1,010 tokens totales con un costo estimado de ~$0.00015 USD por solicitud.
- **Mantenimiento**: Revisar estructura de respuesta ante cambios en la API de JPL CAD (`fields` y esquema JSON) o actualizaciones del modelo `amazon.nova-lite-v1:0` en AWS Bedrock.
- **Responsable**: Leonardo Ordóñez.
- **Ante un fallo**: Errores capturados mediante HTTP exceptions (401, 422, 502, 504, 500) registradas en logs JSON estructurados. Ante un fallo de JPL o Bedrock, el servidor responde con 502/504 evitando reintentos infinitos.
- **Despliegue**: Entorno local comprobado en Windows 11 / Python 3.13 con Uvicorn y FastAPI. Despliegue en la nube fuera del alcance actual.
- **Límites y pendientes reales**: Evaluación automatizada con juez DeepEval (Sesión 5) y demostración final (Sesión 6).
- **Versión final**: Commit `1da47c7e04a25d5deaee03f0ff8237041febd74a` / [`commit 1da47c7`](https://github.com/lordonez/en-orbita/commit/1da47c7e04a25d5deaee03f0ff8237041febd74a).

---

## Entrega definitiva · Domingo posterior a la sesión 6

Entrega hasta las 23:59, hora de Perú. Incluye las correcciones surgidas en la exposición y el paquete completo indicado en la guía del proyecto.

- **Observaciones de la sesión 6**: [Pendiente]
- **Correcciones y comprobación**: [Pendiente]
- **Commit o ZIP definitivo**: [Pendiente]

---

## Registro de avances

Cada fila apunta a una versión revisable. Los enlaces a evidencias deben funcionar para el docente.

| Sesión | Commit o ZIP entregado | Evidencia principal | Observación recibida y cambio realizado |
| :---: | :--- | :--- | :--- |
| **1 · Sin entrega formal** | — | Borrador del caso en `docs/PROYECTO.md` | Sin observación registrada |
| **2** | [`commit 4277e01`](https://github.com/lordonez/en-orbita/commit/4277e0159c5d8d1cb5a6125f9ea4f5893619827d) | [`../evidencias/sesion-02/consulta_jpl_real.json`](../evidencias/sesion-02/consulta_jpl_real.json) | Sin observación registrada |
| **3** | [`commit 4277e01`](https://github.com/lordonez/en-orbita/commit/4277e0159c5d8d1cb5a6125f9ea4f5893619827d) | [`../evidencias/sesion-03/respuesta_bedrock_real.json`](../evidencias/sesion-03/respuesta_bedrock_real.json)<br>[`../evidencias/sesion-03/mediciones_sesion3.json`](../evidencias/sesion-03/mediciones_sesion3.json) | Sin observación registrada |
| **4** | [`commit 4277e01`](https://github.com/lordonez/en-orbita/commit/4277e0159c5d8d1cb5a6125f9ea4f5893619827d) | [`../evidencias/sesion-04/traza_langfuse.json`](../evidencias/sesion-04/traza_langfuse.json)<br>[`../evidencias/sesion-04/traza_langfuse.png`](../evidencias/sesion-04/traza_langfuse.png) | Sin observación registrada |
| **5** | [Pendiente] | `../evidencias/sesion-05/evaluacion_deepeval.json` | [Pendiente] |
| **6 · Exposición** | [Pendiente] | Demo y evidencia final | [Pendiente] |
| **Domingo posterior · Final** | [`commit 1da47c7`](https://github.com/lordonez/en-orbita/commit/1da47c7e04a25d5deaee03f0ff8237041febd74a) | Paquete completo publicado en GitHub | Sin observación registrada |
