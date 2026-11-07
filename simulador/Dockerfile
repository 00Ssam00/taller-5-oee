# Simulador de telemetria hora a hora.
# Imagen minima: solo necesita Python y el cliente de PostgreSQL.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Bogota

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulador.py .

# Usuario sin privilegios: el contenedor no necesita root para nada.
RUN useradd --create-home --shell /usr/sbin/nologin sim
USER sim

ENTRYPOINT ["python", "-u", "simulador.py"]
