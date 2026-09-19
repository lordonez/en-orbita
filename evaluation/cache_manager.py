import hashlib
import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).parent / "cache"


class EvaluationCacheManager:
    """Manejador de caché en disco para resultados de evaluación."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_cache_key(
        self,
        record_id: str,
        request_dict: dict[str, Any],
        fixture_file: str | None,
        generator_model: str,
        judge_model: str,
        applicable_metrics: list[str],
        script_text: str | None = None,
    ) -> str:
        """Calcula un hash SHA-256 único incorporando todos los parámetros relevantes."""
        raw_payload = {
            "record_id": record_id,
            "request": request_dict,
            "fixture": fixture_file or "none",
            "generator_model": generator_model,
            "judge_model": judge_model,
            "metrics": sorted(applicable_metrics),
            "script": script_text or "",
            "metric_version": "deepeval-4.2.3-geval-v2.1",
        }
        serialized = json.dumps(raw_payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Obtiene un resultado desde la caché en disco si existe."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def set(self, cache_key: str, data: dict[str, Any]) -> None:
        """Guarda un resultado en la caché en disco."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
