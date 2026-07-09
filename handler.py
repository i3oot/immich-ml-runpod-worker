import os
import time
from typing import Any

import runpod


IMMICH_VERSION = os.getenv("IMMICH_VERSION", "v3.0.0")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/cache")
WORKER_VERSION = os.getenv("WORKER_VERSION", "dev")


def _health() -> dict[str, Any]:
    return {
        "ok": True,
        "worker": "immich-ml-runpod-worker",
        "workerVersion": WORKER_VERSION,
        "immichVersion": IMMICH_VERSION,
        "modelCacheDir": MODEL_CACHE_DIR,
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
    job_input = job.get("input") or {}
    operation = str(job_input.get("operation", "health"))

    if operation == "health":
        return _health()

    return _unsupported(operation)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
