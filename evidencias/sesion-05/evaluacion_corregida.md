# Resumen de Evaluación Corregida (Línea Base + Reevaluación de 40 Casos)

## 1. Resultado Global Corregido

| Métrica | Valor |
| :--- | :--- |
| **Casos Procesados** | 100 |
| **Casos Aprobados** | 82 |
| **Casos Fallidos** | 18 |
| **Errores de Evaluación** | 0 |
| **Porcentaje de Aprobación** | 82.00% |
| **Costo Total Consolidado** | $0.022829 USD |

## 2. Resultado por Categoría Corregido

| Categoría | Total | Aprobados | Fallidos | Eval Error | % Aprobación |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `positive` | 40 | 31 | 9 | 0 | 77.50% |
| `boundary_variant` | 20 | 16 | 4 | 0 | 80.00% |
| `controlled_error` | 20 | 20 | 0 | 0 | 100.00% |
| `adversarial` | 20 | 15 | 5 | 0 | 75.00% |

## 3. Resultado por Métrica Corregido

| Métrica | Evaluar Totales | Aprobados | Fallidos |
| :--- | :---: | :---: | :---: |
| `deterministic_app_status` | 100 | 99 | 1 |
| `deterministic_http_status` | 100 | 99 | 1 |
| `factual_consistency` | 70 | 55 | 15 |
| `forbidden_claims_check` | 8 | 8 | 0 |
| `no_unexpected_external_calls` | 100 | 100 | 0 |
| `security` | 10 | 9 | 1 |
| `structured_facts_check` | 70 | 69 | 1 |
| `task_completion` | 60 | 53 | 7 |
