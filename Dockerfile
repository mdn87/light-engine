FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LIGHT_ENGINE_MODE=simulation
COPY pyproject.toml README.md ./
COPY light_engine ./light_engine
COPY web ./web
RUN pip install --no-cache-dir .
EXPOSE 8765
CMD ["uvicorn", "light_engine.api:app", "--host", "0.0.0.0", "--port", "8765"]
