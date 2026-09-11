FROM python:3.12-slim-bookworm
WORKDIR /app
# pyswisseph contains both C and C++ extension sources.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
# Fail the build early if the ephemeris extension cannot run.
RUN python -c "import swisseph as s; p, flags = s.calc_ut(2451545.0, s.SUN, s.FLG_MOSEPH); assert 0 <= p[0] < 360; print('Swiss Ephemeris OK', s.version)"
COPY astro.py main.py features.py providers.py ./
COPY LICENSE NOTICE SOURCE_RELEASE.md THIRD_PARTY.md ./
# Uploaded ZIP files may arrive with owner-only permissions. Normalize them
# before switching users; application code stays owned by root.
RUN useradd --create-home appuser \
    && chmod 755 /app \
    && chmod 644 /app/*.py /app/requirements.txt /app/LICENSE /app/NOTICE /app/*.md \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data \
    && chmod 700 /app/data
USER appuser
# Import the complete application as the runtime user during the build.
RUN python -c "import os,tempfile; t=tempfile.TemporaryDirectory(); os.environ['JYOTI_DB']=t.name+'/check.sqlite3'; import main; assert main.app; t.cleanup()"
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
