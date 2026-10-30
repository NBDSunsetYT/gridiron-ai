FROM python:3.12-slim
WORKDIR /app
COPY modeling/requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi \
    && pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 1001 gridiron \
    && useradd --system --uid 1001 --gid 1001 gridiron
COPY --chown=gridiron:gridiron modeling /app/modeling
COPY --chown=gridiron:gridiron deployment/render/start.py /app/start.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
USER gridiron
EXPOSE 10000
CMD ["python", "/app/start.py"]
