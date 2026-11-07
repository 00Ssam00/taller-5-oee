"""Configuracion del ETL, tomada exclusivamente de variables de entorno.

No hay ninguna credencial escrita en el codigo: docker-compose las inyecta
desde `.env`, que esta excluido del repositorio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    # --- Conexion a PostgreSQL ---------------------------------------------
    host: str
    puerto: int
    base: str
    usuario: str
    clave: str

    # --- Rutas -------------------------------------------------------------
    ruta_excel: Path
    ruta_salida: Path

    # --- Pseudonimizacion de datos personales ------------------------------
    salt_pseudonimo: str

    # --- Parametros de negocio --------------------------------------------
    # Meta de OEE acordada con la gerencia para el semaforo de los tableros.
    meta_oee: float = 0.65
    # Umbral critico que dispara la alerta de Grafana.
    umbral_oee_critico: float = 0.50
    # Meta de disponibilidad (equivale al "% Productividad" que hoy se reporta).
    meta_disponibilidad: float = 0.80
    # Rango de la dimension de fecha.
    anio_inicio_calendario: int = 2022
    anio_fin_calendario: int = 2026
    # Un paro de mas de estos minutos en un solo codigo se marca como atipico.
    minutos_paro_atipico: int = 480

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.puerto} dbname={self.base} "
            f"user={self.usuario} password={self.clave}"
        )


def cargar_config() -> Config:
    """Construye la configuracion leyendo el entorno, con valores por defecto
    utiles para ejecutar el ETL fuera de Docker (por ejemplo desde DBeaver)."""
    return Config(
        host=os.getenv("PGHOST", "localhost"),
        puerto=int(os.getenv("PGPORT", "5432")),
        base=os.getenv("PGDATABASE", "bi_oee"),
        usuario=os.getenv("PGUSER", "bi_admin"),
        clave=os.getenv("PGPASSWORD", ""),
        ruta_excel=Path(
            os.getenv(
                "ETL_RUTA_EXCEL",
                "/datos/fuente/Seguimiento Temperas y Vinilos Actividad.xlsm",
            )
        ),
        ruta_salida=Path(os.getenv("ETL_RUTA_SALIDA", "/salida")),
        salt_pseudonimo=os.getenv("ETL_SALT_PSEUDONIMO", "semilla-por-defecto-cambiar"),
    )
