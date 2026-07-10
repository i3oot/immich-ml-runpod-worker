import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import os
import time
from typing import Any

import runpod


IMMICH_VERSION = os.getenv("IMMICH_VERSION", "v3.0.2")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/cache")


def _json_safe(value: Any) -> Any:
    """Convert Immich/NumPy inference results into RunPod-serializable JSON."""
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
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
    text = job_input.get("text")
    if not image_base64 and not isinstance(text, str):
        return {"ok": False, "error": "missing_input", "message": "imageBase64 or text is required."}

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

    if image_base64:
        try:
            payload = decode_pil(base64.b64decode(image_base64, validate=True))
        except Exception as exc:
            return {"ok": False, "error": "invalid_image", "message": str(exc)}
    else:
        payload = text

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            # RunPod may invoke a synchronous handler from its asyncio loop. Run
            # the Immich async inference pipeline in a dedicated event loop.
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(asyncio.run, run_inference(payload, (without_deps, with_deps))).result()
            return {"ok": True, "result": _json_safe(result)}
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(30 * (attempt + 1))

    return {"ok": False, "error": "inference_failed", "message": str(last_error)}


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
