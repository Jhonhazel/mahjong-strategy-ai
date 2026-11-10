# Native build tools are confined to this stage; original PyMahjongGB unmodified.
FROM python:3.12.10-slim-bookworm AS mahjong-wheel
RUN apt-get update && apt-get install -y --no-install-recommends g++ \
    && pip wheel --no-deps PyMahjongGB==1.4.0 --wheel-dir /wheels

FROM python:3.12.10-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY --from=mahjong-wheel /wheels /wheels
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --find-links=/wheels -r requirements-runtime.txt \
    && pip check
COPY main.py .
COPY app app
COPY config/contact_members.public.json config/home_research.public.json ./config/
COPY scripts scripts
COPY training training
COPY docs/ml_artifact_bundle_manifest.json docs/ml_artifact_bundle_manifest.json
COPY artifacts/models/mahjong_discard_mlp_v3.pt artifacts/models/mahjong_discard_mlp_v3.pt
COPY artifacts/models/mahjong_discard_mlp_v3.metadata.json artifacts/models/mahjong_discard_mlp_v3.metadata.json
COPY datasets/expanded_strict_v2/data_contract.json datasets/expanded_strict_v2/data_contract.json
RUN python -m scripts.lecturer_assets && useradd --uid 10001 --create-home mahjong
USER 10001
CMD ["python", "-m", "scripts.lecturer_setup", "--container"]
