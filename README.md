# Immich ML RunPod Worker

RunPod Serverless GPU worker image for the Immich ML gateway.

> AI-generated disclosure: this repository was scaffolded and documented with
> OpenAI Codex under human direction. Treat it as project-specific integration
> code, not as an official Immich or RunPod artifact.

## Status

This repository is public so RunPod can pull the worker image from GHCR without
private registry credentials. Do not add secrets, tokens, customer data, or
private model files to this repository or image.

The worker supports the health operation and an Immich-compatible `predict`
operation for CLIP visual embeddings, face detection/recognition, and OCR.
Unsupported operations return explicit errors.

This repo builds a custom worker image on top of:

```text
ghcr.io/immich-app/immich-machine-learning:v3.0.2-cuda
```

The worker is intentionally a thin RunPod handler. Immich itself will not call this endpoint directly. A Kubernetes gateway will translate Immich ML HTTP requests into RunPod jobs and translate RunPod results back into Immich-compatible responses.

## Architecture

Immich does not call this endpoint directly. The intended flow is:

```text
Immich server -> Kubernetes ML gateway -> RunPod Serverless worker
```

The Kubernetes gateway is responsible for translating Immich's machine-learning
HTTP API into RunPod jobs and translating worker results back into
Immich-compatible responses.

## Supported Operations

### `health`

Input:

```json
{
  "input": {
    "operation": "health"
  }
}
```

Output includes the worker name, configured Immich version, configured cache
path, supported operations, and a Unix timestamp.

### `predict`

The gateway sends the Immich ML pipeline plus either a base64 encoded image or
text. The worker executes the pipeline with the bundled Immich ML runtime and
returns the native Immich response under `result`.

### Unsupported Operations

Any other operation returns:

```json
{
  "ok": false,
  "error": "unsupported_operation"
}
```

This is intentional. New operation adapters should be added only after the
gateway request and response contract is defined.

## Build Locally

```powershell
docker build --platform linux/amd64 -t ghcr.io/i3oot/immich-ml-runpod-worker:v3.0.0-dev .
```

## Test Locally

```powershell
docker run --rm ghcr.io/i3oot/immich-ml-runpod-worker:v3.0.0-dev
```

The RunPod SDK reads `test_input.json` by default for local handler testing.

## Test Without Docker

```powershell
python -m unittest discover -s tests -v
```

## RunPod Endpoint

Create a Serverless endpoint from the published image:

```text
ghcr.io/i3oot/immich-ml-runpod-worker:<version>
```

Recommended initial endpoint settings:

- Endpoint type: `Queue`
- GPU: `RTX 4090`, `RTX A5000`, or `RTX 3090`
- GPUs per worker: `1`
- Active workers: `0` for lowest cost, `1` to avoid cold starts
- Max workers: `1-2`
- Idle timeout: `60-300s`
- Execution timeout: `600-1800s`
- FlashBoot: enabled

Environment variables:

```text
IMMICH_VERSION=v3.0.2
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

## Security And Privacy

- Image previews or derived ML inputs may be sent to RunPod once operation
  adapters are implemented.
- The worker image is public. Keep all runtime secrets in RunPod endpoint
  environment variables or Kubernetes secrets, never in this repository.
- The current scaffold does not expose an HTTP server; it only runs a RunPod
  Serverless handler.
- Pin immutable image tags such as `sha-<git-sha>` for endpoint deployments.

## Ownership

This is a project-specific integration repository for `i3oot`. It is not
affiliated with or endorsed by Immich, RunPod, or OpenAI.
