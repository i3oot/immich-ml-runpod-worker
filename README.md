# Immich ML RunPod Worker

RunPod Serverless GPU worker image for the Immich ML gateway.

This repo builds a custom worker image on top of:

```text
ghcr.io/immich-app/immich-machine-learning:v3.0.0-cuda
```

The worker is intentionally a thin RunPod handler. Immich itself will not call this endpoint directly. A Kubernetes gateway will translate Immich ML HTTP requests into RunPod jobs and translate RunPod results back into Immich-compatible responses.

## Current State

The image is scaffolded and supports:

- RunPod handler startup
- `operation: health`
- explicit `unsupported_operation` responses for future operation adapters

The next implementation step is to add adapters for specific gateway operations such as CLIP embedding, face detection, or OCR after the gateway request contract is defined.

## Build Locally

```powershell
docker build --platform linux/amd64 -t ghcr.io/i3oot/immich-ml-runpod-worker:v3.0.0-dev .
```

## Test Locally

```powershell
docker run --rm ghcr.io/i3oot/immich-ml-runpod-worker:v3.0.0-dev
```

The RunPod SDK reads `test_input.json` by default for local handler testing.

## RunPod Endpoint

Create a Serverless endpoint from the published image:

```text
ghcr.io/i3oot/immich-ml-runpod-worker:<version>
```

Recommended initial endpoint settings:

- Endpoint type: `Queue`
- GPU: `NVIDIA L4` or `RTX 4000 Ada`
- GPUs per worker: `1`
- Active workers: `0` for lowest cost, `1` to avoid cold starts
- Max workers: `2`
- Idle timeout: `60-300s`
- Execution timeout: `600-1800s`
- FlashBoot: enabled

Environment variables:

```text
IMMICH_VERSION=v3.0.0
WORKER_VERSION=<image-tag>
MODEL_CACHE_DIR=/cache
TRANSFORMERS_CACHE=/cache/transformers
HF_HOME=/cache/huggingface
HF_XET_CACHE=/cache/huggingface-xet
MPLCONFIGDIR=/cache/matplotlib
```

## Network Volume

A RunPod network volume is optional.

Use one when cold starts are too slow because the worker downloads or rebuilds model caches on each fresh worker. The volume gives `/cache` persistent storage across worker restarts in the same region.

Skip it initially when:

- you are testing the endpoint
- the worker image already contains the models you need
- cost matters more than cold-start latency
- the gateway normally uses local/public CLIP and calls RunPod only for rare batch jobs

If enabled, mount the network volume at:

```text
/cache
```

Suggested size:

```text
50GiB
```
