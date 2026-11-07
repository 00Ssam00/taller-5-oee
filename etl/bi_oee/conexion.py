"""Conexion a PostgreSQL y utilidades de carga masiva."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Sequence

import psycopg

log = logging.getLogger("bi_oee")


@contextmanager
def abrir_conexion(dsn: str):
    """Conexion con transaccion explicita.

    autocommit=False: si cualquier paso del ETL falla, la base queda en el
    estado anterior. Es lo que hace que el proceso sea seguro de reejecutar.
    """
    with psycopg.connect(dsn, autocommit=False) as conexion:
        yield conexion


def copiar(conexion, tabla: str, columnas: Sequence[str], filas: Iterable[Sequence[Any]]) -> int:
    """Carga masiva con COPY.

    Se usa COPY en lugar de INSERT fila a fila porque el volumen (24.000+
    filas de hechos) lo justifica: COPY es entre 10 y 50 veces mas rapido y
    reduce el tiempo total del ETL a unos pocos segundos.
    """
    lista_columnas = ", ".join(f'"{c}"' for c in columnas)
    sentencia = f"COPY {tabla} ({lista_columnas}) FROM STDIN"
    total = 0
    with conexion.cursor() as cur:
        with cur.copy(sentencia) as copy:
            for fila in filas:
                copy.write_row(fila)
                total += 1
    log.info("    COPY %-42s %7d filas", tabla, total)
    return total


def truncar(conexion, *tablas: str) -> None:
    """Vacia tablas respetando las dependencias.

    El ETL es de CARGA COMPLETA (full refresh): en cada ejecucion se
    reconstruye todo el modelo desde el Excel. Es la estrategia correcta aqui
    porque la fuente es un archivo que se reemplaza completo cada mes y el
    volumen es pequeno; evita la complejidad de detectar cambios y garantiza
    que el resultado sea identico ejecucion tras ejecucion (idempotencia).
    """
    with conexion.cursor() as cur:
        for tabla in tablas:
            cur.execute(f"TRUNCATE TABLE {tabla} CASCADE")
    log.info("    TRUNCATE de %d tablas", len(tablas))


def escalar(conexion, sql: str, parametros: Sequence[Any] | None = None):
    with conexion.cursor() as cur:
        cur.execute(sql, parametros)
        fila = cur.fetchone()
        return fila[0] if fila else None


def consultar(conexion, sql: str, parametros: Sequence[Any] | None = None) -> list[tuple]:
    with conexion.cursor() as cur:
        cur.execute(sql, parametros)
        return cur.fetchall()


def ejecutar(conexion, sql: str, parametros: Sequence[Any] | None = None) -> None:
    with conexion.cursor() as cur:
        cur.execute(sql, parametros)
