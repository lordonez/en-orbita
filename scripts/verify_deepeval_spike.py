"""Spike técnico para verificar DeepEval 4.2.3, AWS Boto3 y los modelos Amazon Nova.

Este script ejecuta las validaciones requeridas para el Punto de Control 1:
1. Inspección de versiones de Python y DeepEval.
2. Verificación del adaptador BedrockNovaJudge heredando de DeepEvalBaseLLM.
3. Prueba de conectividad Boto3 con el perfil 'en-orbita' en 'us-east-2'.
4. Invocación mínima a Amazon Nova Micro (us.amazon.nova-micro-v1:0).
5. Invocación mínima a Amazon Nova Lite (amazon.nova-lite-v1:0).
6. Prueba mínima de métrica GEval usando Nova Lite como juez en DeepEval.
7. Registro de tokens e informe del costo observado usando la fórmula oficial.
8. Sanitización de salida (cero secretos).
"""

import sys

import boto3

# Tarifas oficiales de Amazon Bedrock (us-east-2, Sep 2026, On-Demand)
# Fuente: Amazon Bedrock Pricing Page (Consultada: 2026-09-17)
PRECIO_MICRO_ENTRADA_1K = 0.000035
PRECIO_MICRO_SALIDA_1K = 0.00014
PRECIO_LITE_ENTRADA_1K = 0.00006
PRECIO_LITE_SALIDA_1K = 0.00024

AWS_PROFILE = "en-orbita"
AWS_REGION = "us-east-2"
GENERATOR_MODEL_ID = "us.amazon.nova-micro-v1:0"
EVALUATOR_MODEL_ID = "amazon.nova-lite-v1:0"


def run_spike():
    print("=" * 60)
    print("PUNTO DE CONTROL 1: SPIKE TÉCNICO Y MODELOS NOVA")
    print("=" * 60)

    # 1. Versiones
    python_ver = sys.version.split()[0]
    print(f"Versión de Python: {python_ver}")

    try:
        import deepeval
        from deepeval.metrics import GEval
        from deepeval.models.base_model import DeepEvalBaseLLM
        from deepeval.test_case import LLMTestCase, SingleTurnParams

        deepeval_ver = getattr(deepeval, "__version__", "desconocida")
        print(f"Versión instalada de DeepEval: {deepeval_ver}")
    except Exception as e:
        print(f"ERROR al importar DeepEval: {e}")
        sys.exit(1)

    # 2. Definición del adaptador BedrockNovaJudge
    class BedrockNovaJudge(DeepEvalBaseLLM):
        def __init__(self, profile_name=AWS_PROFILE, region_name=AWS_REGION, model_id=None):
            self.profile_name = profile_name
            self.region_name = region_name
            self.model_id = model_id or EVALUATOR_MODEL_ID
            self.session = boto3.Session(profile_name=self.profile_name, region_name=self.region_name)
            self.client = self.session.client("bedrock-runtime")
            self.input_tokens = 0
            self.output_tokens = 0

        def load_model(self):
            return self.client

        def get_model_name(self) -> str:
            return f"Amazon Bedrock ({self.model_id})"

        def generate(self, prompt: str) -> str:
            response = self.client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"temperature": 0.0, "maxTokens": 1000},
            )
            usage = response.get("usage", {})
            in_tok = usage.get("inputTokens", 0)
            out_tok = usage.get("outputTokens", 0)
            self.input_tokens += in_tok
            self.output_tokens += out_tok
            return response["output"]["message"]["content"][0]["text"]

        async def a_generate(self, prompt: str) -> str:
            from starlette.concurrency import run_in_threadpool

            return await run_in_threadpool(self.generate, prompt)

    # 3. Verificación de credenciales AWS STS
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    sts_client = session.client("sts")
    identity = sts_client.get_caller_identity()
    sanitized_arn = identity["Arn"].split("/")[-1]
    print(f"Credenciales AWS verificadas (Perfil: {AWS_PROFILE}, ARN rol/usuario: .../{sanitized_arn})")

    # 4. Invocación mínima a Nova Micro (Generador)
    bedrock_client = session.client("bedrock-runtime")
    print(f"\nProbando invocación directa a Amazon Nova Micro ({GENERATOR_MODEL_ID})...")
    resp_micro = bedrock_client.converse(
        modelId=GENERATOR_MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [{"text": 'Responde con un objeto JSON: {"status": "ok", "model": "nova-micro"}'}],
            }
        ],
        inferenceConfig={"temperature": 0.0, "maxTokens": 100},
    )
    usage_micro = resp_micro.get("usage", {})
    micro_in = usage_micro.get("inputTokens", 0)
    micro_out = usage_micro.get("outputTokens", 0)
    micro_text = resp_micro["output"]["message"]["content"][0]["text"]
    print(f"Respuesta Nova Micro (primeros 60 caracteres): {micro_text[:60]!r}")
    print(f"Tokens Nova Micro - Entrada: {micro_in}, Salida: {micro_out}")

    # 5. Invocación mínima a Nova Lite (Juez) vía Boto3
    print(f"\nProbando invocación directa a Amazon Nova Lite ({EVALUATOR_MODEL_ID})...")
    resp_lite = bedrock_client.converse(
        modelId=EVALUATOR_MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [{"text": "Responde exclusivamente 'LITE_OK'"}],
            }
        ],
        inferenceConfig={"temperature": 0.0, "maxTokens": 50},
    )
    usage_lite = resp_lite.get("usage", {})
    lite_in_direct = usage_lite.get("inputTokens", 0)
    lite_out_direct = usage_lite.get("outputTokens", 0)
    lite_text = resp_lite["output"]["message"]["content"][0]["text"]
    print(f"Respuesta Nova Lite (primeros 60 caracteres): {lite_text[:60]!r}")
    print(f"Tokens Nova Lite directo - Entrada: {lite_in_direct}, Salida: {lite_out_direct}")

    # 6. Prueba mínima de GEval con DeepEval usando BedrockNovaJudge
    print("\nProbando evaluador GEval de DeepEval con BedrockNovaJudge...")
    judge_model = BedrockNovaJudge()

    metric = GEval(
        name="PruebaSpikeConcordancia",
        criteria="Evalúa si la respuesta menciona que el paso del asteroide es seguro.",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        model=judge_model,
    )

    test_case = LLMTestCase(
        input="¿El asteroide 2026 RN2 representa algún riesgo para la Tierra?",
        actual_output="El asteroide 2026 RN2 pasará de manera totalmente segura a 0.001484 AU sin riesgo de colisión.",
    )

    metric.measure(test_case)
    score = metric.score
    reason = metric.reason
    print("Métrica GEval completada con éxito.")
    print(f"Puntaje (Score): {score}")
    print(f"Razón (Reason) (truncada 80 chars): {str(reason)[:80]!r}")
    print(
        f"Tokens acumulados en juez durante GEval - Entrada: {judge_model.input_tokens}, Salida: {judge_model.output_tokens}"
    )

    # Totales de tokens
    total_micro_in = micro_in
    total_micro_out = micro_out
    total_lite_in = lite_in_direct + judge_model.input_tokens
    total_lite_out = lite_out_direct + judge_model.output_tokens

    # 7. Cálculo del costo según la fórmula requerida
    costo_micro_entrada = (total_micro_in / 1000.0) * PRECIO_MICRO_ENTRADA_1K
    costo_micro_salida = (total_micro_out / 1000.0) * PRECIO_MICRO_SALIDA_1K
    costo_lite_entrada = (total_lite_in / 1000.0) * PRECIO_LITE_ENTRADA_1K
    costo_lite_salida = (total_lite_out / 1000.0) * PRECIO_LITE_SALIDA_1K

    costo_total = costo_micro_entrada + costo_micro_salida + costo_lite_entrada + costo_lite_salida

    invocaciones_count = 3  # 1 Nova Micro + 1 Nova Lite directo + 1 GEval Nova Lite

    print("\n" + "=" * 60)
    print("REGISTRO DE COSTOS OBSERVADOS (PUNTO DE CONTROL 1)")
    print("=" * 60)
    print("Fuente oficial de precios: Amazon Bedrock Pricing Page (https://aws.amazon.com/bedrock/pricing/)")
    print("Fecha de consulta: 2026-09-17")
    print("Región / Modalidad: us-east-2 / On-Demand")
    print(f"Número de invocaciones: {invocaciones_count}")
    print(f"Tokens observados Nova Micro - Entrada: {total_micro_in}, Salida: {total_micro_out}")
    print(f"Tokens observados Nova Lite  - Entrada: {total_lite_in}, Salida: {total_lite_out}")
    print(f"Costo observado Nova Micro entrada: ${costo_micro_entrada:.8f}")
    print(f"Costo observado Nova Micro salida:  ${costo_micro_salida:.8f}")
    print(f"Costo observado Nova Lite entrada:  ${costo_lite_entrada:.8f}")
    print(f"Costo observado Nova Lite salida:   ${costo_lite_salida:.8f}")
    print(f"COSTO TOTAL OBSERVADO EN SPIKE:     ${costo_total:.8f}")
    print("=" * 60)
    print("SPIKE FINALIZADO CON ÉXITO")


if __name__ == "__main__":
    run_spike()
