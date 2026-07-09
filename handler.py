import os
import time
from typing import Any

import runpod


IMMICH_VERSION = os.getenv("IMMICH_VERSION", "v3.0.0")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/cache")
WORKER_VERSION = os.getenv("WORKER_VERSION", "dev")
WORKER_NAME = "immich-ml-runpod-worker"
SUPPORTED_OPERATIONS = {"health"}


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

    return _unsupported(operation)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
