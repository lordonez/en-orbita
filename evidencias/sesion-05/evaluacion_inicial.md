# Resumen de Evaluación Inicial de Línea Base (Dataset v2 - 100 Casos)

## 1. Resultado Global

| Métrica | Valor |
| :--- | :--- |
| **Casos Procesados** | 100 |
| **Casos Aprobados** | 58 |
| **Casos Fallidos** | 42 |
| **Errores de Evaluación** | 0 |
| **Porcentaje de Aprobación** | 58.00% |
| **Costo Total Observado** | $0.021586 USD |

## 2. Resultado por Categoría

| Categoría | Total | Aprobados | Fallidos | Eval Error | % Aprobación |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `positive` | 40 | 18 | 22 | 0 | 45.00% |
| `boundary_variant` | 20 | 8 | 12 | 0 | 40.00% |
| `controlled_error` | 20 | 20 | 0 | 0 | 100.00% |
| `adversarial` | 20 | 12 | 8 | 0 | 60.00% |

## 3. Resultado por Métrica

| Métrica | Evaluar Totales | Aprobados | Fallidos |
| :--- | :---: | :---: | :---: |
| `deterministic_app_status` | 100 | 99 | 1 |
| `deterministic_http_status` | 100 | 99 | 1 |
| `factual_consistency` | 70 | 30 | 40 |
| `forbidden_claims_check` | 8 | 8 | 0 |
| `no_unexpected_external_calls` | 100 | 100 | 0 |
| `security` | 10 | 10 | 0 |
| `structured_facts_check` | 70 | 68 | 2 |
| `task_completion` | 60 | 57 | 3 |

## 4. Cinco Casos Obligatorios de la Plantilla Académica

### Caso TC-POS-001 (Válido)
- **Categoría:** `positive`
- **Descripción:** Guion valido short para general, tono informative, duracion objetivo 30 s y fixture normal.json.
- **Fuentes de Ejecución:** Invocación real Nova Micro / Nova Lite (Fixture normal.json)
- **Resultado:** `FAILED` (HTTP 200, App draft_pending_review)
- **Costo Observado:** $0.000278 USD (Tokens Micro In/Out: 537/253, Lite In/Out: 1595/534)

### Caso TC-VAR-001 (Variante Válida)
- **Categoría:** `boundary_variant`
- **Descripción:** Intervalo de un solo dia, duracion minima y audiencia infantil.
- **Fuentes de Ejecución:** Invocación real Nova Micro / Nova Lite (Audiencia infantil)
- **Resultado:** `FAILED` (HTTP 200, App draft_pending_review)
- **Costo Observado:** $0.000291 USD (Tokens Micro In/Out: 568/264, Lite In/Out: 1631/566)

### Caso TC-ERR-006 (Datos Faltantes)
- **Categoría:** `controlled_error`
- **Descripción:** Falta start_date.
- **Fuentes de Ejecución:** Mock JPL sin eventos cercanos (no_events)
- **Resultado:** `PASSED` (HTTP 422, App http_error)
- **Costo Observado:** $0.000000 USD (Tokens Micro In/Out: 0/0, Lite In/Out: 0/0)

### Caso TC-ERR-008 (Datos Inválidos)
- **Categoría:** `controlled_error`
- **Descripción:** end_date anterior a start_date.
- **Fuentes de Ejecución:** Validación Pydantic estática 422 (duración < 5s)
- **Resultado:** `PASSED` (HTTP 422, App http_error)
- **Costo Observado:** $0.000000 USD (Tokens Micro In/Out: 0/0, Lite In/Out: 0/0)

### Caso TC-ERR-016 (Proveedor Falla)
- **Categoría:** `controlled_error`
- **Descripción:** Consulta valida cuyo fixture no contiene aproximaciones.
- **Fuentes de Ejecución:** Mock JPL con error 500 del servidor (http_error)
- **Resultado:** `PASSED` (HTTP 200, App no_events)
- **Costo Observado:** $0.000000 USD (Tokens Micro In/Out: 0/0, Lite In/Out: 0/0)

## 5. Telemetría y Costo Observado Real

- **Invocaciones Nova Micro:** 71
- **Invocaciones Nova Lite (Juez):** 71
- **Tokens Observados Nova Micro:** 38361 entrada / 26122 salida
- **Tokens Observados Nova Lite:** 125251 entrada / 37796 salida
- **Casos con Telemetría `unavailable`:** 29
- **Costo Total Observado:** $0.021586 USD
