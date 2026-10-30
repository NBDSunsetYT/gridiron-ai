FROM python:3.12-slim
WORKDIR /app
COPY modeling/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && groupadd --system --gid 1001 gridiron && useradd --system --uid 1001 --gid 1001 gridiron
COPY modeling /app/modeling
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER gridiron
EXPOSE 8000
CMD ["uvicorn", "modeling.service:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
