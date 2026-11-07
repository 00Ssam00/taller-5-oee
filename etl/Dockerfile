# ===========================================================================
#  Imagen del proceso ETL.
#  Se elige python:3.12-slim (no alpine) porque las ruedas binarias de psycopg
#  estan compiladas contra glibc; con alpine habria que compilar desde fuente.
# ===========================================================================
FROM python:3.12-slim

# Zona horaria de la planta, para que las marcas de tiempo del linaje coincidan
# con las de PostgreSQL y Grafana.
ENV TZ=America/Bogota \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Capa de dependencias separada del codigo: aprovecha la cache de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bi_oee/ ./bi_oee/

# Usuario sin privilegios: el ETL no necesita root.
RUN useradd --create-home --shell /bin/bash etl && chown -R etl:etl /app
USER etl

ENTRYPOINT []
CMD ["python", "-m", "bi_oee.cli", "ejecutar", "--modo", "completo"]
