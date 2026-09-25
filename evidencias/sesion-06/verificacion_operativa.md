# Evidencia de Verificación Operativa — Sesión 6

**Proyecto:** En órbita — Copiloto Editorial para Guiones Espaciales Factuales
**Fecha de verificación:** 24 de septiembre de 2026 (11:37:49 COT / 16:37:49 UTC)
**Entorno de ejecución:** Local — Windows 11 Pro, PowerShell 7 / Windows Terminal
**Versión de Python:** Python 3.13.0 (64-bit)
**Proveedor LLM:** Amazon Bedrock Runtime — Región `us-east-2` (Ohio)
**Perfil AWS:** `en-orbita` (`AWS_PROFILE=en-orbita`)
**Modelo generador:** Amazon Nova Micro (`us.amazon.nova-micro-v1:0`)

---

## 1. Comandos de Verificación del Entorno y Dependencias

Se ejecutaron las siguientes instrucciones en PowerShell para validar el entorno y la reproducibilidad:

```powershell
# 1. Comprobación de versión de Python
python --version
# Salida: Python 3.13.0

# 2. Comprobación de integridad de dependencias
python -m pip check
# Salida: No broken requirements found.

# 3. Verificación de estilo y formato
python -m ruff check .
# Salida: All checks passed!
python -m ruff format --check .
# Salida: 34 files already formatted

# 4. Suite automatizada de pruebas deterministas
python -m pytest -v
# Salida: 32 passed, 1 warning in 6.00s
```

---

## 2. Comprobación de Arranque y Disponibilidad de Endpoints

El servicio FastAPI se inició localmente con Uvicorn en el puerto 8000:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Se verificó la respuesta HTTP de las rutas de documentación y especificación OpenAPI:

| Endpoint | Método | Código HTTP | Resultado |
| :--- | :---: | :---: | :--- |
| `/docs` | GET | `200 OK` | Interfaz interactiva Swagger UI disponible y operativa. |
| `/openapi.json` | GET | `200 OK` | Esquema OpenAPI 3.1.0 expuesto correctamente. |
| `/health` | — | N/A | No implementado (no existe endpoint de salud dedicado en el diseño actual). |

---

## 3. Protocolo de Demostración Operativa

### Caso A: Solicitud sin autorización (HTTP 401)
* **Petición:** `POST /scripts/generate` sin la cabecera `X-API-Key`.
* **Cuerpo enviado:**
  ```json
  {
    "start_date": "2026-09-08",
    "end_date": "2026-09-30"
  }
  ```
* **Código HTTP obtenido:** `401 Unauthorized`.
* **Cuerpo de respuesta:**
  ```json
  {
    "detail": "Autenticación fallida: X-API-Key ausente o inválida."
  }
  ```
* **Comprobación:** El servicio rechazó inmediatamente la solicitud a nivel de dependencia de FastAPI (`verify_api_key`), garantizando **cero llamadas externas** a NASA/JPL CAD API o Amazon Bedrock.

---

### Caso B: Entrada con parámetros inválidos (HTTP 422)
* **Petición:** `POST /scripts/generate` con fechas invertidas (`end_date` anterior a `start_date`) y cabecera de autenticación válida.
* **Cuerpo enviado:**
  ```json
  {
    "start_date": "2026-09-30",
    "end_date": "2026-09-08",
    "video_format": "news_brief",
    "duration_seconds": 90
  }
  ```
* **Código HTTP obtenido:** `422 Unprocessable Entity`.
* **Cuerpo de respuesta (resumen):**
  ```json
  {
    "detail": [
      {
        "type": "value_error",
        "loc": ["body"],
        "msg": "Value error, La fecha final (end_date) no puede ser anterior a la fecha inicial (start_date)."
      }
    ]
  }
  ```
* **Comprobación:** La validación estricta de Pydantic (`validate_date_range`) capturó la anomalía en el contrato de entrada antes de cualquier procesamiento posterior, consumiendo **cero llamadas externas**.

---

### Caso C: Ejecución válida real (HTTP 200)
* **Petición:** `POST /scripts/generate` con parámetros editoriales completos (caso idéntico al evaluado en Sesión 3).
* **Cuerpo enviado:**
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
* **Código HTTP obtenido:** `200 OK`.
* **Resumen estructurado de la respuesta:**
  * **`request_id`:** `366243f3-0eb0-4cfc-b39c-5ae84bb2175b`
  * **`status`:** `draft_pending_review`
  * **`requires_human_review`:** `true` (invariante de revisión editorial garantizada)
  * **Objeto seleccionado por JPL:** `(2026 RT34)`
  * **Fecha nominal de aproximación (TDB):** `2026-Sep-13 09:08 TDB`
  * **Distancia nominal mínima:** `0.00014 AU` (`20,965.13 km` / `0.05 LD`)
  * **Velocidad relativa:** `13.08 km/s` (velocidad al infinito: `11.53 km/s`)
  * **Magnitud absoluta ($H$):** `30.36`
  * **Título del guion:** *"Próxima aproximación del objeto (2026 RT34) a la Tierra"*
  * **Palabras totales:** `150` palabras
  * **Duración estimada:** `60.0` segundos (tasa de lectura: 150 wpm)
  * **Propuestas visuales:** 3 propuestas descriptivas generadas sin alucinación.
* **Nota sobre la duración:** La ejecución válida respondió correctamente a nivel técnico, pero el guion generado tuvo 150 palabras y una duración estimada de 60 segundos frente a los 90 segundos solicitados. Esto evidencia que el generador todavía puede incumplir parcialmente parámetros editoriales y justifica la revisión humana obligatoria.

---

## 4. Métricas de Rendimiento y Telemetría de Tokens

* **Latencia total medida en cliente:** `7,162.50 ms` (~7.16 s)
* **Latencia JPL CAD API:** ~`1,280 ms`
* **Latencia Amazon Bedrock (Nova Micro):** ~`5,750 ms`
* **Tokens de entrada (Prompt tokens):** `537`
* **Tokens de salida (Completion tokens):** `374`
* **Tokens totales:** `911`
* **Estado de tokens:** `observed` (conteo oficial provisto por la API Converse de Amazon Bedrock, sin estimaciones sintéticas).

---

## 5. Cálculo del Costo Observado

El costo de la ejecución válida se calcula aplicando las tarifas oficiales de AWS Bedrock On-Demand vigentes para **Amazon Nova Micro** en la región **`us-east-2`** (consultadas el 24 de septiembre de 2026 en la documentación oficial: [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)):

* **Modelo:** Amazon Nova Micro (`us.amazon.nova-micro-v1:0`)
* **Región:** `us-east-2` (Ohio)
* **Fecha de consulta de tarifa:** 24 de septiembre de 2026
* **Tarifa de entrada:** USD 0.000035 por 1,000 tokens (USD 0.035 / 1M tokens)
* **Tarifa de salida:** USD 0.000140 por 1,000 tokens (USD 0.140 / 1M tokens)
* **Tokens observados:** 537 tokens de entrada, 374 tokens de salida, 911 tokens totales (estado `observed`)

```text
Costo de entrada = (537 / 1000) × USD 0.000035
                 = USD 0.000018795

Costo de salida  = (374 / 1000) × USD 0.000140
                 = USD 0.000052360

Costo total      = USD 0.000071155
                 ≈ USD 0.000071 por solicitud
```

### Diferenciación con otros costos del proyecto:
1. **Ejecución operativa individual:** Aproximadamente **USD 0.000071** por solicitud válida (una única generación de guion con Nova Micro).
2. **Ciclo de evaluación de la Sesión 5:** Tuvo un costo observado combinado de **USD 0.034837**. Este importe incluye la evaluación inicial de 100 casos y una reevaluación parcial posterior a la corrección de la rúbrica del juez.
3. **Proyección teórica:** Aproximadamente **USD 0.071 por 1,000 solicitudes**, suponiendo que cada solicitud consuma los mismos 537 tokens de entrada y 374 tokens de salida observados en esta ejecución. La proyección excluye otros costos de infraestructura, observabilidad, almacenamiento, transferencia, impuestos y variaciones de uso. (No constituye una medición ni un costo mensual real).

---

## 6. Procedimiento de Detención Limpia

Para finalizar la ejecución del servicio en PowerShell de manera ordenada:

1. En la consola donde se ejecuta Uvicorn, presionar la combinación de teclas:
   ```text
   Ctrl + C
   ```
2. Uvicorn intercepta la señal `SIGINT`, cancela las tareas activas y cierra el bucle de eventos (`asyncio`):
   ```text
   INFO:     Shutting down
   INFO:     Waiting for application shutdown.
   INFO:     Application shutdown complete.
   INFO:     Finished server process
   ```
3. Se comprobó con `netstat -ano | findstr :8000` que el puerto 8000 quedó totalmente liberado sin procesos huérfanos.

---

## 7. Límites Observados y Declaraciones Regulatorias

* **Fidelidad factual y evaluación:** En la evaluación corregida, 79 de 100 casos aprobaron todos los criterios y 21 casos conservaron al menos un criterio no alcanzado. La mayoría de esos 21 resultados correspondió a respuestas generadas que no superaron uno o más umbrales de calidad. Sin embargo, `TC-ADV-004` sí produjo HTTP 502 porque, ante datos externos manipulados, el modelo devolvió una salida incompatible con el esquema esperado. Este resultado se documenta como una limitación de robustez. No hubo errores de ejecución del evaluador (`evaluation_error`).
  - **18 incidencias de fallo** en la métrica de consistencia factual (`factual_consistency`).
  - **3 incidencias de fallo** en cumplimiento de la tarea (`task_completion`).
  - **2 incidencias de fallo** deterministas en hechos estructurados (`structured_facts_check`), superpuestas con casos ya contabilizados como fallidos.
  - **`TC-ADV-004` produjo HTTP 502** y pertenece al conjunto de casos fallidos.
  - **0 errores de ejecución del evaluador** (`evaluation_error`).
* **Incumplimiento de duración observado:** La ejecución válida respondió correctamente a nivel técnico, pero el guion generado tuvo 150 palabras y una duración estimada de 60 segundos frente a los 90 segundos solicitados. Esto evidencia que el generador todavía puede incumplir parcialmente parámetros editoriales y justifica la revisión humana obligatoria.
* **Muestra de rendimiento:** Las mediciones de latencia corresponden a una prueba representativa en entorno local y pueden variar según la latencia de red hacia los endpoints públicos de NASA/JPL y AWS Bedrock `us-east-2`.
* **Declaración de no despliegue:** El servicio fue comprobado en un entorno local. La estrategia futura de despliegue en la nube todavía no ha sido seleccionada ni verificada.
* **Declaración sobre DeepEval:** Para esta verificación de la Sesión 6 **no se ejecutó DeepEval** ni se reevaluó el Golden Dataset de 100 casos, respetando estrictamente el control presupuestario y las evidencias ya consolidadas en la Sesión 5.
* **Declaración sobre Langfuse:** La integración con Langfuse se mantuvo intacta en el código (`app/observability/langfuse_tracer.py`). No se crearon nuevos proyectos, no se modificaron sus módulos ni se regeneraron evidencias de la Sesión 4.
