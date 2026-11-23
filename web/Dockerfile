FROM python:3.12-slim-bookworm
WORKDIR /app/web
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
COPY web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/astro.py backend/providers.py /app/backend/
COPY web/app.py web/ai_reading.py web/vargas.py web/source.zip web/LICENSE web/NOTICE web/THIRD_PARTY.md ./
COPY web/static ./static
RUN useradd --create-home appuser && chmod -R a+rX /app
USER appuser
EXPOSE 8000
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log"]
