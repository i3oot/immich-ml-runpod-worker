FROM ghcr.io/immich-app/immich-machine-learning:v3.0.0-cuda

USER root

WORKDIR /worker

COPY requirements.txt /worker/requirements.txt
RUN pip install --no-cache-dir -r /worker/requirements.txt

COPY handler.py /worker/handler.py
COPY test_input.json /worker/test_input.json

ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/cache/transformers
ENV HF_HOME=/cache/huggingface
ENV HF_XET_CACHE=/cache/huggingface-xet
ENV MPLCONFIGDIR=/cache/matplotlib

CMD ["python", "-u", "/worker/handler.py"]
