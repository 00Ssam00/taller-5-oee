"""Transformacion y carga de las tablas de hechos.

Aqui ocurren las dos transformaciones centrales del proyecto:

  1. SEPARACION DE CABECERAS Y FILAS DE CONTINUACION
     La hoja fuente mezcla 5.160 registros de turno reales con 3.048 filas de
     continuacion que el boton "Ingreso subcodigo" del Excel genera repitiendo
     la cabecera. Si se cargaran como turnos, los turnos se duplicarian y la
     disponibilidad se hundiria artificialmente.

  2. DESPIVOTE DE LOS 18 PARES DE COLUMNAS DE PARO
     De formato ancho (18 pares minutos/horas por fila) a formato largo (un
     evento de paro por fila). Es lo que habilita el Pareto de causas y el
     drill-down de la jerarquia, imposibles en el formato original.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict

from . import catalogos as cat
from .conexion import consultar, copiar, ejecutar, truncar
from .extraccion import COLS_PARO

log = logging.getLogger("bi_oee")

# Codigo de paro que representa reproceso de producto ya envasado. Es el unico
# insumo disponible para aproximar el componente Calidad del OEE.
CODIGO_REPROCESO = "11"

# Un rendimiento superior a este multiplo del maximo teorico se considera un
# error de digitacion o un estandar obsoleto, no una linea excepcional.
UMBRAL_RENDIMIENTO_IMPLAUSIBLE = 1.5

# Solo estos tres codigos tienen arbol de subcodigos en el catalogo de la
# fuente. En el resto, la ausencia de subcodigo no es un defecto de registro.
CODIGOS_CON_SUBCODIGO = {"01", "03", "05"}


def _numero(texto):
    """Convierte un valor de staging a float, tolerando texto no numerico."""
    if texto is None:
        return None
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _fecha(texto):
    if texto is None:
        return None
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


class CargadorHechos:
    def __init__(self, conexion, config, indices):
        self.cx = conexion
        self.cfg = config
        self.ix = indices          # indices de dimensiones construidos antes
        self.metricas: dict[str, float] = {}

    # ======================================================================
    def cargar(self, ejecucion_id: int) -> dict[str, int]:
        truncar(self.cx, "dw.hecho_paro", "dw.hecho_produccion_turno")

        filas = consultar(self.cx, """
            SELECT stg_id, fila_origen, fecha, maquina, operario, referencia,
                   unidad_por_display_src, pacas_producidas, horas_trabajadas,
                   turno, horas_no_trabajadas, tipo_paro, observaciones_paro,
                   cod01_min, cod01_sub, cod02_min, cod03_min, cod03_sub,
                   cod04_min, cod05_min, cod05_sub, cod05_area, cod05_personal,
                   cod06_min, cod07_min, cod08_min, cod09_min, cod10_min,
                   cod11_min, cod12_min, cod13_min, cod14_min, cod15_min,
                   cod16_min, cod17_min, cod18_min, tiempo_paro_total, hash_fila
            FROM stg.base_datos
            ORDER BY fila_origen
        """)
        log.info("  Filas en staging: %d", len(filas))

        registros = [self._interpretar(f) for f in filas]

        # --- REGLA DE LIMPIEZA: eliminar duplicados exactos ----------------
        vistos: set[str] = set()
        unicos, duplicados = [], 0
        for r in registros:
            if r["hash"] in vistos:
                duplicados += 1
                continue
            vistos.add(r["hash"])
            unicos.append(r)
        self.metricas["duplicados_exactos"] = duplicados
        log.info("  Duplicados exactos descartados: %d", duplicados)

        cabeceras = [r for r in unicos if r["es_cabecera"]]
        continuaciones = [r for r in unicos if not r["es_cabecera"]]
        log.info("  Cabeceras de turno: %d | Filas de continuacion: %d",
                 len(cabeceras), len(continuaciones))

        self._vincular_continuaciones(cabeceras, continuaciones)
        # _cargar_turnos necesita las continuaciones ya vinculadas para sumar
        # su tiempo de paro al turno al que pertenecen.
        self._continuaciones_cache = continuaciones
        n_turnos = self._cargar_turnos(cabeceras, ejecucion_id)
        n_paros = self._cargar_paros(cabeceras, continuaciones, ejecucion_id)
        self._enlazar_paros_con_turnos()

        return {"turnos": n_turnos, "paros": n_paros,
                "duplicados": duplicados, "continuaciones": len(continuaciones)}

    # ======================================================================
    def _interpretar(self, fila) -> dict:
        """Traduce una fila de staging a una estructura con claves resueltas."""
        (stg_id, fila_origen, fecha_txt, maquina_txt, operario_txt, referencia_txt,
         unid_display, pacas_txt, horas_txt, turno_txt, horas_nt_txt, tipo_paro_txt,
         obs_paro, *resto) = fila
        hash_fila = resto[-1]
        tiempo_paro_src = resto[-2]
        minutos_y_sub = resto[:-2]

        fecha = _fecha(fecha_txt)
        maquina_key = self.ix["maquina"].get(cat.limpiar(maquina_txt) or "")

        # --- REGLA DE LIMPIEZA (DQ-04): turno con columna de respaldo
        # El formulario de captura escribio el turno tambien en "Unidad por
        # display" (col 8) en 687 filas, siempre de forma redundante con la
        # columna correcta. Se prefiere la columna correcta y se deja la otra
        # como respaldo defensivo por si en una carga futura solo viniera esa.
        turno_crudo = cat.limpiar(turno_txt) or cat.limpiar(unid_display)
        turno_key, turno_imputado = cat.resolver_turno(turno_crudo)

        clave_op = cat.clave_comparacion(cat.limpiar(operario_txt))
        operario_key = self.ix["operario"].get(clave_op, 0)

        clave_ref = cat.clave_comparacion(cat.limpiar(referencia_txt))
        if clave_ref in cat.CORRECCION_REFERENCIA:
            clave_ref = cat.clave_comparacion(cat.CORRECCION_REFERENCIA[clave_ref])
        referencia_key = self.ix["referencia"].get(clave_ref, 0)

        pacas = _numero(pacas_txt)
        horas = _numero(horas_txt)

        # --- Despivote de los 18 codigos -----------------------------------
        # El orden de `minutos_y_sub` sigue el SELECT de arriba.
        orden_campos = [
            ("01", True), ("02", False), ("03", True), ("04", False),
            ("05", "con_area"), ("06", False), ("07", False), ("08", False),
            ("09", False), ("10", False), ("11", False), ("12", False),
            ("13", False), ("14", False), ("15", False), ("16", False),
            ("17", False), ("18", False),
        ]
        paros: list[dict] = []
        i = 0
        area_txt = personal_txt = None
        for codigo, extra in orden_campos:
            minutos = _numero(minutos_y_sub[i]); i += 1
            subcodigo_txt = None
            if extra:
                subcodigo_txt = minutos_y_sub[i]; i += 1
                if extra == "con_area":
                    area_txt = minutos_y_sub[i]; i += 1
                    personal_txt = minutos_y_sub[i]; i += 1
            if minutos is None or minutos <= 0:
                continue
            if codigo in CODIGOS_CON_SUBCODIGO:
                sub_codigo, sub_imputado = cat.resolver_subcodigo(subcodigo_txt, codigo)
            else:
                # Los otros 15 codigos no tienen arbol de subcodigos en el
                # catalogo: su ausencia NO es un dato incompleto, por lo que no
                # se marcan como imputados. De lo contrario el indicador de
                # completitud del registro quedaria dominado por falsos
                # positivos (78% de los eventos en vez del 22% real).
                sub_codigo, sub_imputado = "N/A", False
            paro_key = self.ix["paro"].get((codigo, sub_codigo))
            if paro_key is None:   # red de seguridad: cae al miembro de relleno
                paro_key = self.ix["paro"].get((codigo, "SIN-ESP")) \
                        or self.ix["paro"][(codigo, "N/A")]
                sub_imputado = codigo in CODIGOS_CON_SUBCODIGO
            paros.append({
                "codigo": codigo,
                "paro_key": paro_key,
                "minutos": round(minutos, 3),
                "horas": round(minutos / 60.0, 8),
                "sub_imputado": sub_imputado,
                "atipico": minutos > self.cfg.minutos_paro_atipico,
            })

        area_key = self.ix["area"].get(cat.limpiar(area_txt) or "Sin informar", 7)
        personal_key = self.ix["personal"].get(
            cat.clave_comparacion(cat.limpiar(personal_txt)), 0
        )

        return {
            "stg_id": stg_id,
            "fila_origen": fila_origen,
            "hash": hash_fila,
            "fecha": fecha,
            "fecha_key": int(fecha.strftime("%Y%m%d")) if fecha else None,
            "maquina_key": maquina_key,
            "turno_key": turno_key,
            "turno_imputado": turno_imputado,
            "operario_key": operario_key,
            "operario_no_informado": operario_key == 0,
            "referencia_key": referencia_key,
            "referencia_no_informada": referencia_key == 0,
            "tipo_paro_key": cat.resolver_tipo_paro_cabecera(tipo_paro_txt),
            "pacas": pacas,
            "horas": horas,
            "horas_no_prog": _numero(horas_nt_txt),
            "obs_paro": cat.limpiar(obs_paro),
            "area_key": area_key,
            "personal_key": personal_key,
            "paros": paros,
            "tiempo_paro_src": _numero(tiempo_paro_src) or 0.0,
            # Es cabecera de turno si declara produccion u horas asignadas.
            "es_cabecera": pacas is not None or horas is not None,
            "turno_destino": None,   # lo asigna _vincular_continuaciones
        }

    # ======================================================================
    def _vincular_continuaciones(self, cabeceras, continuaciones) -> None:
        """Asocia cada fila de continuacion con su registro de turno.

        CASCADA DE VINCULACION (de la clave mas estricta a la mas laxa):
          1. fecha + maquina + operario + referencia + turno
          2. fecha + maquina + operario + referencia
          3. fecha + maquina
        Dentro de los candidatos se elige el turno con MAS horas programadas,
        porque es el que puede absorber el tiempo de paro sin generar la
        inconsistencia "paro mayor que tiempo programado"; el empate se rompe
        por numero de fila, de modo que el resultado es determinista.
        """
        n1 = defaultdict(list)
        n2 = defaultdict(list)
        n3 = defaultdict(list)
        for c in cabeceras:
            k = (c["fecha_key"], c["maquina_key"])
            n1[k + (c["operario_key"], c["referencia_key"], c["turno_key"])].append(c)
            n2[k + (c["operario_key"], c["referencia_key"])].append(c)
            n3[k].append(c)

        def mejor(candidatos):
            return max(candidatos, key=lambda c: ((c["horas"] or 0), -c["fila_origen"]))

        conteo = {"n1": 0, "n2": 0, "n3": 0, "huerfanas": 0}
        horas_huerfanas = 0.0
        for r in continuaciones:
            k = (r["fecha_key"], r["maquina_key"])
            for nombre, indice, clave in (
                ("n1", n1, k + (r["operario_key"], r["referencia_key"], r["turno_key"])),
                ("n2", n2, k + (r["operario_key"], r["referencia_key"])),
                ("n3", n3, k),
            ):
                if indice.get(clave):
                    r["turno_destino"] = mejor(indice[clave])
                    conteo[nombre] += 1
                    break
            else:
                conteo["huerfanas"] += 1
                horas_huerfanas += sum(p["horas"] for p in r["paros"])

        self.metricas.update({
            "cont_vinculadas_n1": conteo["n1"],
            "cont_vinculadas_n2": conteo["n2"],
            "cont_vinculadas_n3": conteo["n3"],
            "cont_huerfanas": conteo["huerfanas"],
            "horas_paro_huerfanas": round(horas_huerfanas, 5),
        })
        log.info("  Vinculacion de continuaciones: n1=%d n2=%d n3=%d huerfanas=%d (%.3f h)",
                 conteo["n1"], conteo["n2"], conteo["n3"], conteo["huerfanas"],
                 horas_huerfanas)

    # ======================================================================
    def _cargar_turnos(self, cabeceras, ejecucion_id: int) -> int:
        """Calcula las metricas del turno y los componentes del OEE."""
        # Paro aportado por las filas de continuacion vinculadas a cada turno.
        paro_extra: dict[int, list[dict]] = defaultdict(list)
        for r in self._continuaciones_cache:
            if r["turno_destino"] is not None:
                paro_extra[r["turno_destino"]["fila_origen"]].extend(r["paros"])

        naturaleza = self.ix["naturaleza_paro"]   # paro_key -> 'Planeado'/'No planeado'
        unid_paca = self.ix["unidades_por_paca"]  # referencia_key -> unidades por paca

        # El consecutivo distingue dos registros con identica clave de negocio.
        consecutivos: dict[tuple, int] = defaultdict(int)
        filas = []
        self._turno_por_fila: dict[int, tuple] = {}

        for r in sorted(cabeceras, key=lambda x: x["fila_origen"]):
            if r["fecha_key"] is None or r["maquina_key"] is None:
                continue   # sin fecha o maquina no se puede ubicar en el modelo

            todos_los_paros = r["paros"] + paro_extra.get(r["fila_origen"], [])
            horas_prog = round(r["horas"] or 0.0, 6)
            horas_paro = round(sum(p["horas"] for p in todos_los_paros), 6)
            horas_plan = round(
                sum(p["horas"] for p in todos_los_paros
                    if naturaleza.get(p["paro_key"]) == "Planeado"), 6)
            horas_noplan = round(horas_paro - horas_plan, 6)
            horas_oper = round(max(horas_prog - horas_paro, 0.0), 6)

            # --- Produccion en unidades comparables ------------------------
            pacas = int(r["pacas"] or 0)
            u_paca = unid_paca.get(r["referencia_key"])
            unidades = int(pacas * u_paca) if u_paca else 0

            # --- Estandar vigente (SCD2) -----------------------------------
            estandar = self.ix["estandar"].get((r["maquina_key"], r["referencia_key"]))
            estandar_key = tasa = None
            if estandar:
                estandar_key, tasa, _origen = estandar
            tiene_estandar = tasa is not None and tasa > 0 and u_paca is not None

            if tiene_estandar:
                u_teoricas = int(round(tasa * 60 * horas_prog))
                u_posibles = int(round(tasa * 60 * horas_oper))
                u_perdidas = int(round(tasa * 60 * horas_paro))
            else:
                u_teoricas = u_posibles = u_perdidas = None

            # --- COMPONENTES DEL OEE ---------------------------------------
            # Disponibilidad = tiempo operativo / tiempo programado.
            # Reproduce exactamente el "% Productividad" del Excel actual.
            disponibilidad = round(horas_oper / horas_prog, 6) if horas_prog > 0 else None

            # Rendimiento = unidades reales / unidades posibles en el tiempo
            # operativo. Solo se calcula si hay estandar: nunca se inventa.
            rendimiento = (
                round(unidades / u_posibles, 6)
                if (u_posibles and u_posibles > 0) else None
            )

            # Calidad: PROXY. La fuente no mide unidades defectuosas. Se usa
            # el tiempo de reproceso (codigo 11) convertido a unidades
            # equivalentes. Es una COTA INFERIOR de la perdida de calidad.
            calidad = None
            if tiene_estandar and unidades > 0:
                horas_reproceso = sum(
                    p["horas"] for p in todos_los_paros if p["codigo"] == CODIGO_REPROCESO
                )
                u_reproceso = tasa * 60 * horas_reproceso
                calidad = round(max(0.0, min(1.0, 1 - u_reproceso / unidades)), 6)

            # --- Deteccion de rendimiento implausible ---------------------
            # Un rendimiento superior al 150% del maximo teorico no es una
            # linea excepcional: es un dato erroneo. O las pacas se digitaron
            # mal, o las horas trabajadas quedaron subregistradas, o el
            # estandar de ingenieria esta obsoleto. Se marca y se excluye del
            # KPI agregado, pero se conserva el valor para poder auditarlo.
            implausible = rendimiento is not None and rendimiento > UMBRAL_RENDIMIENTO_IMPLAUSIBLE

            oee_ad = (round(disponibilidad * rendimiento, 6)
                      if disponibilidad is not None and rendimiento is not None else None)
            oee_full = (round(oee_ad * calidad, 6)
                        if oee_ad is not None and calidad is not None else None)

            clave = (r["fecha_key"], r["maquina_key"], r["turno_key"],
                     r["operario_key"], r["referencia_key"])
            consecutivos[clave] += 1
            consecutivo = consecutivos[clave]

            filas.append([
                r["fecha_key"], r["maquina_key"], r["turno_key"], r["operario_key"],
                r["referencia_key"], estandar_key, r["tipo_paro_key"],
                consecutivo, r["fila_origen"],
                horas_prog, r["horas_no_prog"],
                horas_paro, horas_plan, horas_noplan, horas_oper,
                len(todos_los_paros),
                pacas, unidades, tasa, u_teoricas, u_posibles, u_perdidas,
                disponibilidad, rendimiento, calidad, oee_ad, oee_full,
                r["pacas"] is not None and r["horas"] is not None,
                tiene_estandar,
                horas_paro > horas_prog > 0,
                horas_prog > 12,
                r["turno_imputado"], r["operario_no_informado"],
                r["referencia_no_informada"], implausible,
                ejecucion_id,
            ])
            self._turno_por_fila[r["fila_origen"]] = clave + (consecutivo,)

        return copiar(
            self.cx, "dw.hecho_produccion_turno",
            ["fecha_key", "maquina_key", "turno_key", "operario_key", "referencia_key",
             "estandar_key", "tipo_paro_key", "consecutivo_registro", "fila_origen_excel",
             "horas_programadas", "horas_no_programadas", "horas_paro_total",
             "horas_paro_planeado", "horas_paro_no_planeado", "horas_operativas",
             "eventos_paro", "pacas_producidas", "unidades_producidas",
             "tasa_ideal_unid_min", "unidades_teoricas", "unidades_posibles",
             "unidades_perdidas_paro", "disponibilidad", "rendimiento", "calidad_proxy",
             "oee_ad", "oee_completo", "es_registro_completo", "tiene_estandar",
             "paro_excede_programado", "horas_fuera_de_rango", "turno_imputado",
             "operario_no_informado", "referencia_no_informada",
             "rendimiento_implausible", "ejecucion_id"],
            filas,
        )

    # ======================================================================
    def _cargar_paros(self, cabeceras, continuaciones, ejecucion_id: int) -> int:
        """Carga el hecho de paros con TODOS los eventos, de cabeceras y de
        filas de continuacion. Ningun minuto de paro de la fuente se pierde."""
        naturaleza = self.ix["naturaleza_paro"]
        estandares = self.ix["estandar"]
        filas = []

        for es_continuacion, grupo in ((False, cabeceras), (True, continuaciones)):
            for r in grupo:
                if r["fecha_key"] is None or r["maquina_key"] is None:
                    continue
                estandar = estandares.get((r["maquina_key"], r["referencia_key"]))
                tasa = estandar[1] if estandar else None
                for p in r["paros"]:
                    u_no_producidas = (
                        int(round(tasa * 60 * p["horas"])) if tasa else None
                    )
                    filas.append([
                        r["fecha_key"], r["maquina_key"], r["turno_key"],
                        r["operario_key"], r["referencia_key"], p["paro_key"],
                        r["area_key"] if p["codigo"] == "05" else None,
                        r["personal_key"] if p["codigo"] == "05" else None,
                        r["fila_origen"], r["obs_paro"],
                        p["minutos"], p["horas"], u_no_producidas,
                        naturaleza.get(p["paro_key"]) == "Planeado",
                        es_continuacion, p["sub_imputado"], p["atipico"],
                        ejecucion_id,
                    ])

        return copiar(
            self.cx, "dw.hecho_paro",
            ["fecha_key", "maquina_key", "turno_key", "operario_key", "referencia_key",
             "paro_key", "area_key", "personal_key", "fila_origen_excel",
             "observacion_paro", "minutos_paro", "horas_paro", "unidades_no_producidas",
             "es_paro_planeado", "proviene_de_continuacion", "subcodigo_imputado",
             "minutos_atipicos", "ejecucion_id"],
            filas,
        )

    # ======================================================================
    def _enlazar_paros_con_turnos(self) -> None:
        """Resuelve la FK hecho_paro -> hecho_produccion_turno.

        Se hace en SQL, por fila de origen del Excel, aprovechando que la
        columna fila_origen_excel esta en ambos hechos. Habilita el
        drill-across entre los dos procesos de negocio.
        """
        ejecutar(self.cx, """
            UPDATE dw.hecho_paro hp
            SET produccion_turno_id = h.produccion_turno_id
            FROM dw.hecho_produccion_turno h
            WHERE h.fila_origen_excel = hp.fila_origen_excel
              AND NOT hp.proviene_de_continuacion
        """)
        # Las filas de continuacion se enlazan por la clave de negocio del
        # turno, reproduciendo en SQL la cascada aplicada en Python.
        ejecutar(self.cx, """
            UPDATE dw.hecho_paro hp
            SET produccion_turno_id = sub.produccion_turno_id
            FROM (
                SELECT DISTINCT ON (fecha_key, maquina_key, operario_key, referencia_key)
                       fecha_key, maquina_key, operario_key, referencia_key,
                       produccion_turno_id
                FROM dw.hecho_produccion_turno
                ORDER BY fecha_key, maquina_key, operario_key, referencia_key,
                         horas_programadas DESC, fila_origen_excel
            ) sub
            WHERE hp.proviene_de_continuacion
              AND hp.produccion_turno_id IS NULL
              AND sub.fecha_key      = hp.fecha_key
              AND sub.maquina_key    = hp.maquina_key
              AND sub.operario_key   = hp.operario_key
              AND sub.referencia_key = hp.referencia_key
        """)
        # Tercer nivel de la cascada: solo fecha + maquina. Sin este paso, las
        # continuaciones que Python vinculo por el nivel mas laxo quedaban con
        # la FK en NULL aunque sus horas SI se hubieran sumado a horas_paro_total
        # del turno, de modo que el detalle y el agregado no coincidian.
        ejecutar(self.cx, """
            UPDATE dw.hecho_paro hp
            SET produccion_turno_id = sub.produccion_turno_id
            FROM (
                SELECT DISTINCT ON (fecha_key, maquina_key)
                       fecha_key, maquina_key, produccion_turno_id
                FROM dw.hecho_produccion_turno
                ORDER BY fecha_key, maquina_key,
                         horas_programadas DESC, fila_origen_excel
            ) sub
            WHERE hp.proviene_de_continuacion
              AND hp.produccion_turno_id IS NULL
              AND sub.fecha_key   = hp.fecha_key
              AND sub.maquina_key = hp.maquina_key
        """)
        ejecutar(self.cx, "ANALYZE dw.hecho_paro")
        ejecutar(self.cx, "ANALYZE dw.hecho_produccion_turno")
