import asyncio
import base64
import dataclasses
import json
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time
from typing import Any

import runpod


IMMICH_VERSION = os.getenv("IMMICH_VERSION", "v3.0.2")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/cache")


def _json_safe(value: Any) -> Any:
    """Round-trip inference output through JSON using explicit NumPy handling."""

    def default(item: Any) -> Any:
        if hasattr(item, "tolist"):
            return item.tolist()
        if dataclasses.is_dataclass(item):
            return dataclasses.asdict(item)
        if hasattr(item, "__dict__"):
            return vars(item)
        raise TypeError(f"Unsupported inference result type: {type(item).__name__}")

    return json.loads(json.dumps(value, default=default, allow_nan=False))
WORKER_VERSION = os.getenv("WORKER_VERSION", "dev")
WORKER_NAME = "immich-ml-runpod-worker"
SUPPORTED_OPERATIONS = {"health", "predict"}


def _health() -> dict[str, Any]:
    return {
        "ok": True,
        "worker": WORKER_NAME,
        "workerVersion": WORKER_VERSION,
        "immichVersion": IMMICH_VERSION,
        "modelCacheDir": MODEL_CACHE_DIR,
        "supportedOperations": sorted(SUPPORTED_OPERATIONS),
        "time": int(time.time()),
    }


def _unsupported(operation: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "unsupported_operation",
        "operation": operation,
        "message": (
            "The container and RunPod handler are scaffolded. Add operation adapters "
            "once the Kubernetes gateway request and response contract is finalized."
        ),
    }


def _predict(job_input: dict[str, Any]) -> dict[str, Any]:
    # Import the Immich ML runtime lazily so the lightweight contract tests can
    # run without downloading the CUDA worker image.
    from immich_ml.main import run_inference
    from immich_ml.models import get_model_deps
    from immich_ml.models.transforms import decode_pil
    from immich_ml.schemas import ModelTask, ModelType

    request = job_input.get("entries")
    if not isinstance(request, dict):
        return {"ok": False, "error": "invalid_entries", "message": "entries must be an Immich ML pipeline object."}

    image_base64 = job_input.get("imageBase64")
    image_path = job_input.get("imagePath")
    text = job_input.get("text")
    if not image_base64 and not image_path and not isinstance(text, str):
        return {"ok": False, "error": "missing_input", "message": "imageBase64, imagePath, or text is required."}

    without_deps: list[dict[str, Any]] = []
    with_deps: list[dict[str, Any]] = []
    try:
        for task_name, types in request.items():
            task = ModelTask(task_name)
            for type_name, entry in types.items():
                parsed = {
                        "name": entry["modelName"],
                        "task": task,
                        "type": ModelType(type_name),
                        "options": entry.get("options", {}),
                    }
                (with_deps if get_model_deps(parsed["name"], parsed["type"], parsed["task"]) else without_deps).append(parsed)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return {"ok": False, "error": "invalid_entries", "message": str(exc)}

    cleanup_path: Path | None = None
    last_error: Exception | None = None
    try:
        if image_path:
            root = Path("/runpod-volume").resolve()
            candidate = (root / str(image_path).lstrip("/\\")).resolve()
            if root not in candidate.parents or not str(candidate).startswith("/runpod-volume/immich/"):
                return {"ok": False, "error": "invalid_image_path", "message": "imagePath is outside the temporary Immich volume prefix."}
            cleanup_path = candidate
            payload = decode_pil(candidate.read_bytes())
        elif image_base64:
            payload = decode_pil(base64.b64decode(image_base64, validate=True))
        else:
            payload = text

        for attempt in range(3):
            try:
            # RunPod may invoke a synchronous handler from its asyncio loop. Run
            # the Immich async inference pipeline in a dedicated event loop.
                with ThreadPoolExecutor(max_workers=1) as executor:
                    result = executor.submit(asyncio.run, run_inference(payload, (without_deps, with_deps))).result()
                safe_result = _json_safe(result)
                print("Inference result converted to JSON-safe output", flush=True)
                return {"ok": True, "result": safe_result}
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(30 * (attempt + 1))
        return {"ok": False, "error": "inference_failed", "message": str(last_error)}
    except Exception as exc:
        return {"ok": False, "error": "invalid_image", "message": str(exc)}
    finally:
        if cleanup_path:
            try:
                cleanup_path.unlink(missing_ok=True)
                print(f"Removed temporary image {cleanup_path}", flush=True)
            except Exception as exc:
                print(f"Failed to remove temporary image {cleanup_path}: {exc}", flush=True)


def handler(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict):
        return {
            "ok": False,
            "error": "invalid_job",
            "message": "RunPod job payload must be a JSON object.",
        }

    job_input = job.get("input") or {}
    if not isinstance(job_input, dict):
        return {
            "ok": False,
            "error": "invalid_input",
            "message": "RunPod job input must be a JSON object.",
        }

    operation = str(job_input.get("operation", "health")).strip().lower()

    if operation == "health":
        return _health()
    if operation == "predict":
        return _predict(job_input)

    return _unsupported(operation)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
