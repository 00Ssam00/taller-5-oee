"""Orquestacion del ETL.

Uso:
    python -m bi_oee.cli ejecutar --modo completo

El proceso es IDEMPOTENTE y de CARGA COMPLETA: cada ejecucion reconstruye todo
el modelo desde el Excel dentro de una sola transaccion. Si cualquier paso
falla -incluida una regla de calidad BLOQUEANTE o una conciliacion sin
explicacion- la transaccion se revierte y la base queda en su estado anterior.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from . import VERSION, calidad, conciliacion, dimensiones, hechos
from .catalogos import CODIGOS_PARO, MAQUINAS, AREAS_INVOLUCRADAS
from .conexion import abrir_conexion, consultar, ejecutar, escalar, truncar
from .config import cargar_config
from .extraccion import Extractor

log = logging.getLogger("bi_oee")


def configurar_log() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def titulo(texto: str) -> None:
    log.info("")
    log.info("=" * 78)
    log.info("  %s", texto)
    log.info("=" * 78)


# ===========================================================================
def ejecutar_etl(modo: str) -> int:
    cfg = cargar_config()
    inicio = time.time()

    if not cfg.ruta_excel.exists():
        log.error("No se encuentra el archivo fuente: %s", cfg.ruta_excel)
        return 2

    titulo(f"ETL BI-OEE v{VERSION}  -  modo: {modo}")
    log.info("  Fuente : %s", cfg.ruta_excel)
    log.info("  Destino: %s@%s:%s/%s", cfg.usuario, cfg.host, cfg.puerto, cfg.base)

    extractor = Extractor(cfg.ruta_excel)

    with abrir_conexion(cfg.dsn) as cx:
        # --- Registro de la ejecucion (linaje) -----------------------------
        ejecucion_id = escalar(cx, """
            INSERT INTO aud.ejecucion_etl
                (modo, archivo_fuente, hash_archivo, version_etl, estado)
            VALUES (%s,%s,%s,%s,'EN_CURSO')
            RETURNING ejecucion_id
        """, (modo, str(cfg.ruta_excel), extractor.hash, VERSION))
        log.info("  Ejecucion ETL id = %s", ejecucion_id)

        try:
            # ===============================================================
            titulo("1/6  EXTRACCION  (Excel -> esquema stg)")
            # ===============================================================
            truncar(cx, "stg.base_datos", "stg.base_subcodigos",
                    "stg.catalogo_estandar", "stg.catalogo_codigo_paro",
                    "stg.catalogo_subcodigo", "stg.catalogo_turno",
                    "stg.catalogo_operario", "stg.pivote_excel")

            filas_hechos = extractor.filas_hechos()
            n_stg = extractor.cargar_staging_hechos(cx, ejecucion_id, filas_hechos)
            extractor.cargar_staging_subcodigos(cx, ejecucion_id)
            extractor.cargar_staging_catalogos(cx, ejecucion_id)
            extractor.cargar_staging_pivotes(cx, ejecucion_id)

            # ===============================================================
            titulo("2/6  DIMENSIONES")
            # ===============================================================
            dimensiones.construir_dim_fecha(
                cx, cfg.anio_inicio_calendario, cfg.anio_fin_calendario)
            dimensiones.construir_dim_maquina(cx)
            dimensiones.construir_dim_turno(cx)
            dimensiones.construir_dim_area(cx)
            dimensiones.construir_dim_tipo_paro(cx)
            _, ix_paro = dimensiones.construir_dim_paro(cx)
            _, ix_operario = dimensiones.construir_dim_operario(cx, cfg.salt_pseudonimo)
            _, ix_personal = dimensiones.construir_dim_personal(cx, cfg.salt_pseudonimo)
            _, ix_referencia, unid_paca = dimensiones.construir_dim_referencia(cx)
            _, ix_estandar = dimensiones.construir_dim_estandar(cx, ix_referencia, unid_paca)

            # Indices auxiliares que necesita la carga de hechos.
            indices = {
                "maquina": {codigo: key for key, codigo, *_ in MAQUINAS},
                "paro": ix_paro,
                "operario": ix_operario,
                "personal": ix_personal,
                "referencia": ix_referencia,
                "estandar": ix_estandar,
                "unidades_por_paca": unid_paca,
                "area": {codigo: key for key, codigo, _n, _s in AREAS_INVOLUCRADAS},
                "naturaleza_paro": {
                    key: naturaleza
                    for (key, naturaleza) in consultar(
                        cx, "SELECT paro_key, naturaleza_paro FROM dw.dim_paro")
                },
            }

            # ===============================================================
            titulo("3/6  HECHOS  (separacion de cabeceras + despivote de paros)")
            # ===============================================================
            cargador = hechos.CargadorHechos(cx, cfg, indices)
            resumen = cargador.cargar(ejecucion_id)

            # Enriquecer dim_operario con sus metricas de actividad.
            ejecutar(cx, """
                UPDATE dw.dim_operario o SET
                    primera_aparicion  = s.primera,
                    ultima_aparicion   = s.ultima,
                    turnos_registrados = s.turnos
                FROM (
                    SELECT h.operario_key,
                           min(f.fecha) AS primera, max(f.fecha) AS ultima,
                           count(*)     AS turnos
                    FROM dw.hecho_produccion_turno h
                    JOIN dw.dim_fecha f ON f.fecha_key = h.fecha_key
                    GROUP BY h.operario_key
                ) s
                WHERE s.operario_key = o.operario_key
            """)

            # ===============================================================
            titulo("4/6  REGLAS DE CALIDAD DE DATOS  (conteos antes / despues)")
            # ===============================================================
            registro_calidad = calidad.evaluar_reglas(
                cx, ejecucion_id, {**cargador.metricas, **resumen})

            # ===============================================================
            titulo("5/6  CONCILIACION CONTRA LA FUENTE")
            # ===============================================================
            conciliador = conciliacion.conciliar(
                cx, ejecucion_id, {**cargador.metricas, **resumen})

            # ===============================================================
            titulo("6/6  CIERRE")
            # ===============================================================
            problemas = registro_calidad.fallos_bloqueantes + conciliador.fallos
            if problemas:
                log.error("  ETL ABORTADO. Problemas sin explicacion:")
                for p in problemas:
                    log.error("     - %s", p)
                raise RuntimeError(f"{len(problemas)} verificaciones fallidas")

            duracion = round(time.time() - inicio, 2)
            ejecutar(cx, """
                UPDATE aud.ejecucion_etl SET
                    finalizado_en = now(), estado = 'EXITOSO',
                    filas_extraidas = %s, filas_cargadas_turno = %s,
                    filas_cargadas_paro = %s, duracion_segundos = %s,
                    mensaje = %s
                WHERE ejecucion_id = %s
            """, (n_stg, resumen["turnos"], resumen["paros"], duracion,
                  "Carga completa conciliada contra la fuente", ejecucion_id))

            ejecutar(cx, "ANALYZE")
            cx.commit()

            _escribir_informes(cfg, cx, ejecucion_id)
            _resumen_final(cx, ejecucion_id, duracion)
            return 0

        except Exception as exc:          # noqa: BLE001
            cx.rollback()
            log.exception("ETL FALLIDO: %s", exc)
            # La transaccion principal se revirtio; se registra el fallo en una
            # conexion nueva para que quede constancia en la auditoria.
            with abrir_conexion(cfg.dsn) as cx2:
                ejecutar(cx2, """
                    INSERT INTO aud.ejecucion_etl
                        (modo, archivo_fuente, hash_archivo, version_etl,
                         estado, finalizado_en, mensaje)
                    VALUES (%s,%s,%s,%s,'FALLIDO',now(),%s)
                """, (modo, str(cfg.ruta_excel), extractor.hash, VERSION, str(exc)[:2000]))
                cx2.commit()
            return 1
        finally:
            extractor.cerrar()


# ===========================================================================
def _escribir_informes(cfg, cx, ejecucion_id: int) -> None:
    """Exporta los informes de calidad y conciliacion a archivos versionables.

    Se generan en Markdown y JSON para poder pegarlos en el documento del
    proyecto y para que el repositorio conserve la evidencia de la corrida.
    """
    try:
        cfg.ruta_salida.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("  No se pudo crear %s: %s", cfg.ruta_salida, exc)
        return

    reglas = consultar(cx, """
        SELECT codigo_regla, dimension_calidad, objeto, severidad, resultado,
               filas_antes, filas_afectadas, filas_despues, descripcion, accion_aplicada
        FROM aud.regla_calidad WHERE ejecucion_id = %s ORDER BY codigo_regla
    """, (ejecucion_id,))
    conc = consultar(cx, """
        SELECT prueba, alcance, metrica, valor_fuente, valor_modelo, diferencia,
               resultado, explicacion
        FROM aud.conciliacion WHERE ejecucion_id = %s
        ORDER BY prueba, alcance
    """, (ejecucion_id,))

    # --- Informe de calidad de datos --------------------------------------
    md = ["# Informe de calidad de datos",
          "",
          f"Ejecucion ETL: **{ejecucion_id}**",
          "",
          "| Regla | Dimension | Objeto | Severidad | Resultado | Antes | Afectadas | Despues |",
          "|---|---|---|---|---|---:|---:|---:|"]
    for r in reglas:
        md.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r[0], r[1], r[2], r[3], r[4],
            "-" if r[5] is None else f"{r[5]:,}",
            "-" if r[6] is None else f"{r[6]:,}",
            "-" if r[7] is None else f"{r[7]:,}"))
    md += ["", "## Detalle de cada regla", ""]
    for r in reglas:
        md += [f"### {r[0]} - {r[2]}",
               "",
               f"- **Dimension de calidad:** {r[1]}",
               f"- **Severidad:** {r[3]}  |  **Resultado:** {r[4]}",
               f"- **Problema detectado:** {r[8]}",
               f"- **Accion aplicada:** {r[9]}",
               f"- **Conteos:** antes = {r[5]}, afectadas = {r[6]}, despues = {r[7]}",
               ""]
    (cfg.ruta_salida / "informe_calidad_datos.md").write_text(
        "\n".join(md), encoding="utf-8")

    # --- Informe de conciliacion ------------------------------------------
    md2 = ["# Informe de conciliacion con la fuente",
           "",
           f"Ejecucion ETL: **{ejecucion_id}**",
           "",
           "| Prueba | Alcance | Metrica | Valor fuente | Valor modelo | Diferencia | Resultado |",
           "|---|---|---|---:|---:|---:|---|"]
    for p in conc:
        md2.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            p[0], p[1], p[2],
            f"{float(p[3]):,.6f}" if p[3] is not None else "n/d",
            f"{float(p[4]):,.6f}" if p[4] is not None else "n/d",
            f"{float(p[5]):+,.6f}" if p[5] is not None else "n/d",
            p[6]))
    explicadas = [p for p in conc if p[7]]
    if explicadas:
        md2 += ["", "## Diferencias explicadas", ""]
        for p in explicadas:
            md2 += [f"### {p[0]} - {p[1]}", "", p[7], ""]
    (cfg.ruta_salida / "informe_conciliacion.md").write_text(
        "\n".join(md2), encoding="utf-8")

    # --- Resumen en JSON para automatizaciones ----------------------------
    resumen = {
        "ejecucion_id": ejecucion_id,
        "reglas_calidad": [
            {"codigo": r[0], "dimension": r[1], "objeto": r[2], "severidad": r[3],
             "resultado": r[4], "antes": r[5], "afectadas": r[6], "despues": r[7]}
            for r in reglas
        ],
        "conciliacion": [
            {"prueba": p[0], "alcance": p[1], "metrica": p[2],
             "valor_fuente": float(p[3]) if p[3] is not None else None,
             "valor_modelo": float(p[4]) if p[4] is not None else None,
             "resultado": p[6]}
            for p in conc
        ],
    }
    (cfg.ruta_salida / "resumen_etl.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("  Informes escritos en %s", cfg.ruta_salida)


def _resumen_final(cx, ejecucion_id: int, duracion: float) -> None:
    titulo("RESUMEN DE LA CARGA")
    for etiqueta, sql in (
        ("dim_fecha",                "SELECT count(*) FROM dw.dim_fecha"),
        ("dim_maquina",              "SELECT count(*) FROM dw.dim_maquina"),
        ("dim_turno",                "SELECT count(*) FROM dw.dim_turno"),
        ("dim_operario",             "SELECT count(*) FROM dw.dim_operario"),
        ("dim_referencia",           "SELECT count(*) FROM dw.dim_referencia"),
        ("dim_paro",                 "SELECT count(*) FROM dw.dim_paro"),
        ("dim_estandar (SCD2)",      "SELECT count(*) FROM dw.dim_estandar"),
        ("dim_tipo_paro_cabecera",   "SELECT count(*) FROM dw.dim_tipo_paro_cabecera"),
        ("hecho_produccion_turno",   "SELECT count(*) FROM dw.hecho_produccion_turno"),
        ("hecho_paro",               "SELECT count(*) FROM dw.hecho_paro"),
    ):
        log.info("  %-26s %8s filas", etiqueta, f"{escalar(cx, sql):,}")

    def cuenta(tabla, valor):
        return escalar(cx, f"SELECT count(*) FROM {tabla} "
                           f"WHERE ejecucion_id=%s AND resultado=%s",
                       (ejecucion_id, valor))

    ok_c = cuenta("aud.conciliacion", "OK")
    inf_c = cuenta("aud.conciliacion", "INFORMATIVA")
    fallo_c = cuenta("aud.conciliacion", "FALLO")
    adv = cuenta("aud.regla_calidad", "ADVERTENCIA")
    tot_r = escalar(cx, "SELECT count(*) FROM aud.regla_calidad WHERE ejecucion_id=%s",
                    (ejecucion_id,))
    log.info("")
    log.info("  Conciliacion      : %d pruebas OK, %d informativas, %d fallidas",
             ok_c, inf_c, fallo_c)
    log.info("  Calidad de datos  : %d reglas evaluadas, %d con advertencia", tot_r, adv)
    log.info("  Duracion          : %.2f s", duracion)
    log.info("")
    log.info("  ETL COMPLETADO CORRECTAMENTE")


# ===========================================================================
def main(argv=None) -> int:
    configurar_log()
    parser = argparse.ArgumentParser(
        prog="bi_oee", description="ETL del proyecto BI-OEE")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_ej = sub.add_parser("ejecutar", help="Ejecuta el ETL completo")
    p_ej.add_argument("--modo", default="completo", choices=["completo"],
                      help="Estrategia de carga (solo carga completa por diseno)")
    args = parser.parse_args(argv)
    if args.comando == "ejecutar":
        return ejecutar_etl(args.modo)
    return 2


if __name__ == "__main__":
    sys.exit(main())
