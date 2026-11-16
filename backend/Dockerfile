# API, migrations, worker et tâches planifiées. Une image, trois commandes.
# Le code reste sous backend/ pour que le modèle se range dans
# /opt/axelcompta/_AUDIT_DONNEES/modeles (parents[3] de ml_fallback.py).
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu libgomp1 util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin axel

# Droplets DigitalOcean : amd64. L'empreinte est celle de la release v0.2.33.
ADD --chmod=755 --checksum=sha256:feefa310da569c81b99e1027b86b27b51e6ee9ab647747b49099645120cfc671 \
    https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
    /usr/local/bin/supercronic

WORKDIR /opt/axelcompta/backend

COPY pyproject.toml alembic.ini ./
COPY axelcompta ./axelcompta
COPY migrations ./migrations
COPY docker ./docker

RUN pip install --no-cache-dir -e ".[llm]" \
    && chmod 755 docker/entrypoint.sh \
    && mkdir -p /opt/axelcompta/_AUDIT_DONNEES/modeles \
    && chown axel:axel /opt/axelcompta/_AUDIT_DONNEES/modeles

EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["uvicorn", "axelcompta.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "172.16.0.0/12"]
