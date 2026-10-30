# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY modeling/requirements.txt ./requirements.txt
RUN --mount=type=secret,id=system_ca if [ -f /run/secrets/system_ca ]; then PIP_CERT=/run/secrets/system_ca pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi
RUN groupadd --system --gid 1001 gridiron && useradd --system --uid 1001 --gid 1001 gridiron
COPY --chown=gridiron:gridiron modeling ./modeling
COPY --chown=gridiron:gridiron deployment/railway/start_quant.py ./deployment/start_quant.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
USER gridiron
EXPOSE 8080
CMD ["python", "deployment/start_quant.py"]
