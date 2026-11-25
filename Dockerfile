# Stage 1: Build the React frontend
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend-ui

COPY frontend-ui/package.json frontend-ui/package-lock.json ./
RUN npm ci

COPY frontend-ui/ ./
RUN npm run build


# Stage 2: Django runtime
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# CPU-only neural inference runtime
ENV HF_HOME=/opt/prepbuddy/huggingface
ENV HF_HUB_DISABLE_TELEMETRY=1
ENV HF_HUB_DISABLE_IMPLICIT_TOKEN=1
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV TOKENIZERS_PARALLELISM=false

COPY requirements.txt /app/requirements.txt
COPY requirements-ann.txt /app/requirements-ann.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install "torch==2.15.0+cpu" \
        --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install \
        -r /app/requirements.txt \
        -r /app/requirements-ann.txt \
    && python -m pip check

# Package the verified encoder before runtime.
COPY deploy/prepare_e5_model.py /app/deploy/prepare_e5_model.py
COPY deploy/e5_model_manifest.json /app/deploy/e5_model_manifest.json

RUN python /app/deploy/prepare_e5_model.py

# No model downloads during application execution.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Controlled ANN staging defaults.
ENV CHATBOT_BACKEND=ann
ENV ANN_RECORD_EXPERIENCES=False
ENV WHATSAPP_SEND_ENABLED=False

COPY . /app

COPY --from=frontend-build /app/static/react/ /app/static/react/

RUN SECRET_KEY=build-only-placeholder \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 2 --timeout 120"]
