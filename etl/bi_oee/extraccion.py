"""Extraccion: hojas del Excel  ->  esquema stg.

JUSTIFICACION DE LA HERRAMIENTA ELEGIDA  (requisito del proyecto)
-----------------------------------------------------------------
Se eligio PYTHON + openpyxl + psycopg (COPY) frente a las alternativas:

  Power Query / Flujos de datos
      Descartado: la transformacion central es un DESPIVOTE de 18 pares de
      columnas con reglas condicionales por codigo y un mapeo de dos
      taxonomias historicas. En M eso queda ilegible y, sobre todo, NO es
      versionable de forma revisable en Git ni ejecutable sin interfaz
      grafica, por lo que rompe el requisito de reproducibilidad con un solo
      comando dentro de un contenedor.

  SQL puro
      Descartado como herramienta unica: no puede leer un .xlsm. Habria que
      exportar manualmente a CSV, lo que introduce un paso humano no
      reproducible y pierde la trazabilidad del hash del archivo fuente.
      SI se usa SQL para lo que SQL hace mejor: las agregaciones, las vistas
      analiticas y las funciones de ventana viven en la base de datos.

  Python
      Elegido porque (a) lee el .xlsm directamente y calcula su hash SHA-256
      para demostrar que la carga corresponde al archivo entregado; (b) las
      reglas de limpieza quedan en codigo versionado y con pruebas; (c) corre
      sin interfaz grafica dentro del contenedor, cumpliendo el despliegue
      reproducible; (d) openpyxl expone las celdas en modo de solo lectura con
      consumo de memoria constante.

NOTA SOBRE LA LECTURA DEL ARCHIVO: se abre con data_only=True para obtener el
VALOR calculado de las formulas (no su texto). Esto es indispensable porque
columnas como "Codigo N en horas" y "Tiempo de Paro" son formulas.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import openpyxl

from . import catalogos as cat
from .conexion import copiar

log = logging.getLogger("bi_oee")

# --- Geometria de la hoja "Base De Datos" ----------------------------------
HOJA_HECHOS = "Base De Datos"
FILA_ENCABEZADO = 9            # el encabezado NO esta en la fila 1
FILA_PRIMER_DATO = 10

# Columnas (base 1) de la hoja de hechos, segun el perfilado de la fuente.
COL = {
    "fecha": 1, "mes": 2, "anio": 3, "maquina": 4, "operario": 5,
    "referencia": 6, "unid_min": 7, "unid_display": 8, "display_paca": 9,
    "pacas": 10, "horas_trab": 11, "turno": 12, "horas_no_trab": 13,
    "tipo_paro": 14, "obs_paro": 15,
    "cod05_area": 29, "cod05_personal": 30,
    "tiempo_paro": 57, "observaciones": 58,
}

# Para cada codigo de paro: (columna de minutos, columna de subcodigo, columna de horas)
# La fuente alterna pares <minutos, horas> y solo los codigos 1, 3 y 5 traen
# una columna de subcodigo intercalada.
COLS_PARO: dict[str, tuple[int, int | None, int]] = {
    "01": (16, 17, 18),
    "02": (19, None, 20),
    "03": (21, 22, 23),
    "04": (24, None, 25),
    "05": (26, 27, 28),
    "06": (31, None, 32),
    "07": (33, None, 34),
    "08": (35, None, 36),
    "09": (37, None, 38),
    "10": (39, None, 40),
    "11": (41, None, 42),
    "12": (43, None, 44),
    "13": (45, None, 46),
    "14": (47, None, 48),
    "15": (49, None, 50),
    "16": (51, None, 52),
    "17": (53, None, 54),
    "18": (55, None, 56),
}


def hash_archivo(ruta: Path) -> str:
    """SHA-256 del archivo fuente: evidencia de que se cargo ese Excel exacto."""
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _hash_fila(valores) -> str:
    return hashlib.sha256(
        "\x1f".join("" if v is None else str(v) for v in valores).encode("utf-8")
    ).hexdigest()


def _texto(valor):
    """Convierte cualquier celda a texto para staging, preservando el dato."""
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


class Extractor:
    """Lee el libro de Excel una sola vez y lo deja disponible en memoria."""

    def __init__(self, ruta: Path):
        self.ruta = ruta
        log.info("  Abriendo %s", ruta.name)
        # read_only=True mantiene el consumo de memoria acotado;
        # data_only=True entrega el valor calculado de las formulas.
        self.libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
        self.hash = hash_archivo(ruta)
        log.info("  SHA-256 del archivo fuente: %s", self.hash)

    def cerrar(self):
        self.libro.close()

    # -------------------------------------------------------------------
    def filas_hechos(self) -> list[tuple[int, tuple]]:
        """Filas de datos de la hoja principal, con su numero de fila fisica."""
        hoja = self.libro[HOJA_HECHOS]
        salida = []
        for indice, fila in enumerate(
            hoja.iter_rows(min_row=FILA_PRIMER_DATO, values_only=True), FILA_PRIMER_DATO
        ):
            if any(v is not None for v in fila):
                salida.append((indice, fila))
        log.info("  Hoja '%s': %d filas con datos", HOJA_HECHOS, len(salida))
        return salida

    # -------------------------------------------------------------------
    def cargar_staging_hechos(self, conexion, ejecucion_id: int, filas) -> int:
        columnas = [
            "fila_origen", "fecha", "mes_texto", "anio_texto", "maquina", "operario",
            "referencia", "unidades_por_minuto_src", "unidad_por_display_src",
            "display_por_paca_src", "pacas_producidas", "horas_trabajadas", "turno",
            "horas_no_trabajadas", "tipo_paro", "observaciones_paro",
            "cod01_min", "cod01_sub", "cod01_hrs",
            "cod02_min", "cod02_hrs",
            "cod03_min", "cod03_sub", "cod03_hrs",
            "cod04_min", "cod04_hrs",
            "cod05_min", "cod05_sub", "cod05_hrs", "cod05_area", "cod05_personal",
            "cod06_min", "cod06_hrs", "cod07_min", "cod07_hrs",
            "cod08_min", "cod08_hrs", "cod09_min", "cod09_hrs",
            "cod10_min", "cod10_hrs", "cod11_min", "cod11_hrs",
            "cod12_min", "cod12_hrs", "cod13_min", "cod13_hrs",
            "cod14_min", "cod14_hrs", "cod15_min", "cod15_hrs",
            "cod16_min", "cod16_hrs", "cod17_min", "cod17_hrs",
            "cod18_min", "cod18_hrs",
            "tiempo_paro_total", "observaciones",
            "hash_fila", "ejecucion_id",
        ]

        def generar():
            for nro, fila in filas:
                g = lambda c: fila[c - 1] if c - 1 < len(fila) else None  # noqa: E731
                orden = [
                    nro,
                    _texto(g(COL["fecha"])), _texto(g(COL["mes"])), _texto(g(COL["anio"])),
                    _texto(g(COL["maquina"])), _texto(g(COL["operario"])),
                    _texto(g(COL["referencia"])), _texto(g(COL["unid_min"])),
                    _texto(g(COL["unid_display"])), _texto(g(COL["display_paca"])),
                    _texto(g(COL["pacas"])), _texto(g(COL["horas_trab"])),
                    _texto(g(COL["turno"])), _texto(g(COL["horas_no_trab"])),
                    _texto(g(COL["tipo_paro"])), _texto(g(COL["obs_paro"])),
                ]
                for codigo in (
                    "01", "02", "03", "04", "05", "06", "07", "08", "09",
                    "10", "11", "12", "13", "14", "15", "16", "17", "18",
                ):
                    c_min, c_sub, c_hrs = COLS_PARO[codigo]
                    orden.append(_texto(g(c_min)))
                    if c_sub is not None:
                        orden.append(_texto(g(c_sub)))
                    orden.append(_texto(g(c_hrs)))
                    if codigo == "05":
                        orden.append(_texto(g(COL["cod05_area"])))
                        orden.append(_texto(g(COL["cod05_personal"])))
                orden.append(_texto(g(COL["tiempo_paro"])))
                orden.append(_texto(g(COL["observaciones"])))
                orden.append(_hash_fila(fila))
                orden.append(ejecucion_id)
                yield orden

        return copiar(conexion, "stg.base_datos", columnas, generar())

    # -------------------------------------------------------------------
    def cargar_staging_subcodigos(self, conexion, ejecucion_id: int) -> int:
        """Hoja oculta redundante. Se extrae solo para auditoria."""
        hoja = self.libro["Base de datos de Sub codigos"]
        columnas = [
            "fila_origen", "fecha", "mes_texto", "anio_texto", "maquina", "operario",
            "referencia", "pacas_producidas", "turno",
            "cod01_min", "cod01_sub", "cod01_hrs",
            "cod03_min", "cod03_sub", "cod03_hrs",
            "cod05_min", "cod05_sub", "cod05_hrs", "cod05_area", "cod05_personal",
            "hash_fila", "ejecucion_id",
        ]

        def generar():
            for nro, fila in enumerate(hoja.iter_rows(min_row=9, values_only=True), 9):
                if not any(v is not None for v in fila):
                    continue
                vals = [_texto(v) for v in fila[:19]]
                vals += [None] * (19 - len(vals))
                yield [nro] + vals + [_hash_fila(fila), ejecucion_id]

        return copiar(conexion, "stg.base_subcodigos", columnas, generar())

    # -------------------------------------------------------------------
    def cargar_staging_catalogos(self, conexion, ejecucion_id: int) -> dict[str, int]:
        """Extrae los catalogos de la hoja 'Tablas Desplegables'.

        Esa hoja no es una tabla: son varios bloques dispuestos en distintas
        columnas. El bloque maquina x referencia (columnas C a K) se repite
        cuatro veces, una por maquina, con una fila de encabezado intercalada.
        Se detecta por el valor de la columna de maquina, no por su posicion.
        """
        hoja = self.libro["Tablas Desplegables"]
        filas = list(hoja.iter_rows(min_row=1, values_only=True))
        conteos: dict[str, int] = {}

        # --- Bloque de estandares maquina x referencia (columnas 3..9) -----
        def gen_estandar():
            for nro, fila in enumerate(filas, 1):
                maquina = cat.limpiar(fila[2] if len(fila) > 2 else None)
                referencia = cat.limpiar(fila[3] if len(fila) > 3 else None)
                if not maquina or not referencia:
                    continue
                if not maquina.startswith("Vinilos_"):
                    continue  # filas de encabezado del bloque
                yield [
                    nro, maquina, referencia,
                    _texto(fila[4]), _texto(fila[5]), _texto(fila[6]),
                    _texto(fila[7]), _texto(fila[8]),
                    ejecucion_id,
                ]

        conteos["catalogo_estandar"] = copiar(
            conexion, "stg.catalogo_estandar",
            ["fila_origen", "maquina", "referencia", "numero_colores", "pacas",
             "display", "unidades_por_paca", "unidades_por_minuto", "ejecucion_id"],
            gen_estandar(),
        )

        # --- Bloque de codigos de paro (columnas 39..41) -------------------
        def gen_codigos():
            for fila in filas:
                area = cat.limpiar(fila[38] if len(fila) > 38 else None)
                paro = cat.limpiar(fila[39] if len(fila) > 39 else None)
                clave = cat.limpiar(fila[40] if len(fila) > 40 else None)
                if area and paro and area != "AREA DE IMPACTO":
                    yield [area, paro, clave, ejecucion_id]

        conteos["catalogo_codigo_paro"] = copiar(
            conexion, "stg.catalogo_codigo_paro",
            ["area_impacto", "paro_descripcion", "clave", "ejecucion_id"],
            gen_codigos(),
        )

        # --- Bloques de subcodigos (columnas 43/44 para el codigo 01,
        #     46/47 para los codigos 03 y 05) ------------------------------
        def gen_subcodigos():
            for fila in filas:
                sc1 = cat.limpiar(fila[42] if len(fila) > 42 else None)
                nb1 = cat.limpiar(fila[43] if len(fila) > 43 else None)
                if sc1 and nb1 and sc1[0].isdigit():
                    yield ["01", sc1, nb1, ejecucion_id]
                sc2 = cat.limpiar(fila[45] if len(fila) > 45 else None)
                nb2 = cat.limpiar(fila[46] if len(fila) > 46 else None)
                if sc2 and nb2 and sc2[0].isdigit():
                    padre = "03" if sc2.startswith("3") else "05"
                    yield [padre, sc2, nb2, ejecucion_id]

        conteos["catalogo_subcodigo"] = copiar(
            conexion, "stg.catalogo_subcodigo",
            ["codigo_paro_padre", "subcodigo", "subcodigo_nombre", "ejecucion_id"],
            gen_subcodigos(),
        )

        # --- Lista de turnos (columna 16) ---------------------------------
        def gen_turnos():
            for fila in filas:
                t = cat.limpiar(fila[15] if len(fila) > 15 else None)
                if t and t != "Turnos":
                    yield [t, ejecucion_id]

        conteos["catalogo_turno"] = copiar(
            conexion, "stg.catalogo_turno", ["turno", "ejecucion_id"], gen_turnos()
        )

        # --- Lista de operarios (hoja "Tiempos", columna 19) --------------
        hoja_t = self.libro["Tiempos"]

        def gen_operarios():
            for fila in hoja_t.iter_rows(min_row=2, values_only=True):
                o = cat.limpiar(fila[18] if len(fila) > 18 else None)
                if o:
                    yield [o, ejecucion_id]

        conteos["catalogo_operario"] = copiar(
            conexion, "stg.catalogo_operario", ["operario", "ejecucion_id"], gen_operarios()
        )
        return conteos

    # -------------------------------------------------------------------
    def cargar_staging_pivotes(self, conexion, ejecucion_id: int) -> int:
        """Extrae las cifras de las tablas dinamicas actuales del Excel.

        Son el ANCLA DE CONCILIACION: el modelo dimensional debe reproducirlas.
          - Hoja4         : horas trabajadas por maquina, ano 2023
          - TD_prodMaq    : % Productividad mensual de Vinilos_2 en 2024
          - TD_prodCodigo : participacion de cada codigo de paro
        """
        registros: list[list] = []

        # Hoja4: fila 19 trae 'Suma de Horas trabajadas' por maquina (2023).
        hoja4 = self.libro["Hoja4"]
        filas4 = list(hoja4.iter_rows(min_row=1, max_row=20, values_only=True))
        encabezado = filas4[3] if len(filas4) > 3 else ()
        for fila in filas4:
            etiqueta = cat.limpiar(fila[0] if fila else None)
            if etiqueta == "Suma de Horas trabajadas":
                for col in range(1, min(5, len(fila))):
                    maquina = cat.limpiar(encabezado[col]) if col < len(encabezado) else None
                    if maquina and isinstance(fila[col], (int, float)):
                        registros.append(
                            ["Hoja4", "Suma de Horas trabajadas", maquina,
                             float(fila[col]), ejecucion_id]
                        )

        # TD_prodMaq: % Productividad mensual de Vinilos_2 (ano 2024).
        for hoja_nombre, col_etq, col_val in (("TD_prodMaq", 0, 1), ("TD_prodCodigo", 2, 3)):
            hoja = self.libro[hoja_nombre]
            for fila in hoja.iter_rows(values_only=True):
                etiqueta = cat.limpiar(fila[col_etq] if len(fila) > col_etq else None)
                valor = fila[col_val] if len(fila) > col_val else None
                if etiqueta and isinstance(valor, (int, float)):
                    registros.append([hoja_nombre, etiqueta, None, float(valor), ejecucion_id])

        return copiar(
            conexion, "stg.pivote_excel",
            ["hoja", "etiqueta_fila", "etiqueta_col", "valor", "ejecucion_id"],
            registros,
        )
