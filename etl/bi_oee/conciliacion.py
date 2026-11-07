"""Conciliacion del modelo dimensional contra la fuente Excel.

Requisito del proyecto: "demostrar que los totales cargados (horas, unidades,
tiempo de paro) concuerdan con la fuente, o explicar y justificar las
diferencias".

ESTRATEGIA DE CONCILIACION EN CUATRO BLOQUES
--------------------------------------------
El Excel fuente contiene 42 filas duplicadas exactas. Las tablas dinamicas que
la empresa lleva al comite mensual LAS INCLUYEN, porque una tabla dinamica
suma lo que encuentra. El modelo dimensional, en cambio, las descarta: cargar
dos veces el mismo turno seria un error.

Eso crea una diferencia inevitable y hay que separar dos preguntas distintas:

  BLOQUE 1  "Entiende el modelo el negocio igual que el Excel?"
            Se recalculan los indicadores DESDE STAGING incluyendo las filas
            duplicadas, es decir replicando el comportamiento de la tabla
            dinamica, y se comparan contra las cifras del Excel. Deben
            coincidir a seis decimales. Si coinciden, la formula es la misma.

  BLOQUE 2  "Se cargo todo el dato, sin perder ni duplicar nada?"
            Totales de la fuente MENOS el aporte de los duplicados, contra los
            totales del modelo. Tolerancia estrecha.

  BLOQUE 3  "Cuanto se equivoca hoy el informe del comite?"
            Cuantifica la inflacion que los duplicados introducen en las
            cifras que hoy se reportan a la alta direccion. Es un hallazgo
            para la gerencia, no un fallo del ETL.

  BLOQUE 4  "El despivote de los 18 pares de columnas es exacto?"
            Codigo por codigo, fuente depurada contra hecho_paro.
"""

from __future__ import annotations

import logging

from .conexion import consultar, escalar, ejecutar

log = logging.getLogger("bi_oee")

TOLERANCIA_HORAS = 0.01       # una centesima de hora = 36 segundos
TOLERANCIA_RATIO = 0.000001   # las tablas dinamicas se comparan a 6 decimales
TOLERANCIA_EXACTA = 0.0       # conteos de filas

# --- Expresiones reutilizables sobre staging -------------------------------
#  Staging guarda todo como texto (por diseno, para no rechazar ninguna fila).
#  Estas expresiones lo interpretan sin modificarlo.
NUM = "nullif({col},'')::numeric"
ANIO = "substring(fecha,1,4)::int"
MES = "substring(fecha,6,2)::int"

# Marca las filas duplicadas exactas: la primera ocurrencia (rn = 1) es la que
# el modelo conserva; de rn >= 2 en adelante son las descartadas.
CTE_DUPLICADOS = """
    WITH numeradas AS (
        SELECT stg_id,
               row_number() OVER (PARTITION BY hash_fila ORDER BY fila_origen) AS rn
        FROM stg.base_datos
    )
"""


class Conciliador:
    def __init__(self, conexion, ejecucion_id: int):
        self.cx = conexion
        self.ejecucion_id = ejecucion_id
        self.fallos: list[str] = []

    def comparar(self, prueba, alcance, metrica, valor_fuente, valor_modelo,
                 tolerancia=TOLERANCIA_HORAS, explicacion=None,
                 informativa=False):
        """Registra una prueba de conciliacion.

        informativa=True marca una prueba que NO debe hacer fallar el ETL:
        sirve para cuantificar un hallazgo (por ejemplo, cuanto infla el
        informe actual las cifras del comite).
        """
        if informativa:
            resultado = "INFORMATIVA"
        elif valor_fuente is None or valor_modelo is None:
            resultado = "FALLO"
        else:
            diferencia = abs(float(valor_modelo) - float(valor_fuente))
            resultado = "OK" if diferencia <= tolerancia else "FALLO"

        ejecutar(self.cx, """
            INSERT INTO aud.conciliacion
                (ejecucion_id, prueba, alcance, metrica, valor_fuente, valor_modelo,
                 tolerancia, resultado, explicacion)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (self.ejecucion_id, prueba, alcance, metrica, valor_fuente, valor_modelo,
              tolerancia, resultado, explicacion))

        dif = (float(valor_modelo) - float(valor_fuente)
               if valor_fuente is not None and valor_modelo is not None else None)
        marca = {"OK": "ok", "FALLO": "XX", "INFORMATIVA": "i "}[resultado]
        log.info("  [%s] %-32s %-24s fuente=%14s modelo=%14s dif=%s",
                 marca, prueba[:32], alcance[:24],
                 f"{float(valor_fuente):,.4f}" if valor_fuente is not None else "n/d",
                 f"{float(valor_modelo):,.4f}" if valor_modelo is not None else "n/d",
                 f"{dif:+.6f}" if dif is not None else "n/d")

        if resultado == "FALLO":
            self.fallos.append(f"{prueba} / {alcance}")
        return resultado


# ===========================================================================
def conciliar(conexion, ejecucion_id: int, metricas: dict) -> Conciliador:
    c = Conciliador(conexion, ejecucion_id)
    e = lambda sql, p=None: escalar(conexion, sql, p)  # noqa: E731

    MESES = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12,
    }

    # =======================================================================
    log.info("")
    log.info("  --- BLOQUE 1: la logica del modelo reproduce la del Excel ----------")
    # =======================================================================
    #  Se recalcula el indicador DESDE STAGING incluyendo los duplicados, es
    #  decir imitando exactamente lo que hace la tabla dinamica del Excel.
    #  Coincidir a seis decimales demuestra que el "% Productividad" que la
    #  empresa reporta hoy es, formula por formula, la DISPONIBILIDAD del OEE.

    pivote_mes = consultar(conexion, """
        SELECT etiqueta_fila, valor FROM stg.pivote_excel WHERE hoja = 'TD_prodMaq'
    """)
    for etiqueta, valor in pivote_mes:
        clave = (etiqueta or "").strip().lower()
        if clave == "total general":
            modelo = e(f"""
                SELECT 1 - sum({NUM.format(col='tiempo_paro_total')})
                         / sum({NUM.format(col='horas_trabajadas')})
                FROM stg.base_datos
                WHERE {ANIO} = 2024 AND maquina = 'Vinilos_2'
            """)
            c.comparar("B1 Logica = Excel (TD_prodMaq)", "Vinilos_2 2024 total",
                       "disponibilidad", valor, modelo, TOLERANCIA_RATIO)
        elif clave in MESES:
            modelo = e(f"""
                SELECT 1 - sum({NUM.format(col='tiempo_paro_total')})
                         / sum({NUM.format(col='horas_trabajadas')})
                FROM stg.base_datos
                WHERE {ANIO} = 2024 AND {MES} = %s AND maquina = 'Vinilos_2'
            """, (MESES[clave],))
            c.comparar("B1 Logica = Excel (TD_prodMaq)",
                       f"Vinilos_2 2024-{MESES[clave]:02d}",
                       "disponibilidad", valor, modelo, TOLERANCIA_RATIO)

    # Hoja4: horas trabajadas por maquina en 2023.
    for maquina, valor in consultar(conexion, """
        SELECT etiqueta_col, valor FROM stg.pivote_excel
        WHERE hoja = 'Hoja4' AND etiqueta_fila = 'Suma de Horas trabajadas'
        ORDER BY etiqueta_col
    """):
        modelo = e(f"""
            SELECT coalesce(sum({NUM.format(col='horas_trabajadas')}), 0)
            FROM stg.base_datos WHERE {ANIO} = 2023 AND maquina = %s
        """, (maquina,))
        c.comparar("B1 Logica = Excel (Hoja4 2023)", maquina,
                   "horas trabajadas", valor, modelo, TOLERANCIA_HORAS)

    # TD_prodCodigo: participacion de cada codigo de paro, codigo por codigo.
    base_2024 = e(f"""
        SELECT sum({NUM.format(col='horas_trabajadas')}) FROM stg.base_datos
        WHERE {ANIO} = 2024 AND maquina = 'Vinilos_2'
    """)
    for etiqueta, valor in consultar(conexion, """
        SELECT etiqueta_fila, valor FROM stg.pivote_excel WHERE hoja = 'TD_prodCodigo'
    """):
        texto = (etiqueta or "").strip()
        if not texto.startswith("["):
            continue
        codigo = texto[1:3]
        modelo = e(f"""
            SELECT coalesce(sum({NUM.format(col='cod' + codigo + '_hrs')}), 0) / %s
            FROM stg.base_datos WHERE {ANIO} = 2024 AND maquina = 'Vinilos_2'
        """, (base_2024,))
        c.comparar("B1 Logica = Excel (TD_prodCodigo)", f"Vinilos_2 2024 cod {codigo}",
                   "participacion", valor, modelo, TOLERANCIA_RATIO)

    # =======================================================================
    log.info("")
    log.info("  --- BLOQUE 2: totales fuente depurada vs modelo -------------------")
    # =======================================================================
    #  La "fuente depurada" es el Excel menos el aporte de las 42 filas
    #  duplicadas exactas, que es justamente lo que el modelo carga.

    def fuente_depurada(columna: str) -> float:
        return float(e(f"""
            {CTE_DUPLICADOS}
            SELECT coalesce(sum({NUM.format(col='b.' + columna)}), 0)
            FROM stg.base_datos b
            JOIN numeradas n ON n.stg_id = b.stg_id
            WHERE n.rn = 1
        """) or 0)

    aporte_duplicados = {
        col: float(e(f"""
            {CTE_DUPLICADOS}
            SELECT coalesce(sum({NUM.format(col='b.' + col)}), 0)
            FROM stg.base_datos b
            JOIN numeradas n ON n.stg_id = b.stg_id
            WHERE n.rn > 1
        """) or 0)
        for col in ("horas_trabajadas", "pacas_producidas", "tiempo_paro_total")
    }

    nota_dup = (
        "La fuente se compara DEPURADA: se descuenta el aporte de las 42 filas "
        "duplicadas exactas que el modelo no carga (ver regla DQ-01). El "
        "Bloque 3 cuantifica el efecto de esos duplicados sobre el informe "
        "que hoy se presenta al comite."
    )

    c.comparar("B2 Horas trabajadas", "Total 2022-2025 depurado", "horas",
               fuente_depurada("horas_trabajadas"),
               e("SELECT sum(horas_programadas) FROM dw.hecho_produccion_turno"),
               TOLERANCIA_HORAS, nota_dup)

    c.comparar("B2 Pacas producidas", "Total 2022-2025 depurado", "pacas",
               fuente_depurada("pacas_producidas"),
               e("SELECT sum(pacas_producidas) FROM dw.hecho_produccion_turno"),
               1.0, nota_dup)

    # El tiempo de paro es la prueba del despivote: la fuente lo trae en una
    # columna calculada por fila; el modelo lo reconstruye desde los 18 pares.
    paro_fuente = fuente_depurada("tiempo_paro_total")
    c.comparar("B2 Tiempo de paro (despivote)", "Total 2022-2025 depurado", "horas",
               paro_fuente,
               e("SELECT sum(horas_paro) FROM dw.hecho_paro"),
               TOLERANCIA_HORAS,
               "Prueba del despivote: la fuente trae el total de paro en una "
               "columna calculada por fila; el modelo lo reconstruye sumando "
               "los 18 pares de columnas desplegados en hecho_paro. "
               "Coincidir demuestra que no se perdio ni se duplico un minuto. "
               + nota_dup)

    huerfanas = float(metricas.get("horas_paro_huerfanas", 0) or 0)
    c.comparar("B2 Paro atribuido a turnos", "Total 2022-2025 depurado", "horas",
               paro_fuente - huerfanas,
               e("SELECT sum(horas_paro_total) FROM dw.hecho_produccion_turno"),
               TOLERANCIA_HORAS,
               (f"DIFERENCIA EXPLICADA: {huerfanas:.3f} h de paro provienen de "
                f"filas de continuacion del boton 'Ingreso subcodigo' que no "
                f"pudieron vincularse a ningun registro de turno, porque no "
                f"existe cabecera para esa fecha y maquina. Esas horas SI estan "
                f"en dw.hecho_paro, por lo que el Pareto de causas y el total de "
                f"tiempo perdido son completos; solo no se pueden atribuir a un "
                f"turno concreto. Equivalen al "
                f"{100 * huerfanas / paro_fuente:.4f}% del tiempo de paro total.")
               if huerfanas else nota_dup)

    # --- Trazabilidad fila a fila: ninguna fila queda sin explicacion ------
    filas_stg = int(e("SELECT count(*) FROM stg.base_datos"))
    turnos = int(e("SELECT count(*) FROM dw.hecho_produccion_turno"))
    cont = int(metricas.get("continuaciones", 0) or 0)
    dup = int(metricas.get("duplicados_exactos", 0) or 0)
    c.comparar("B2 Trazabilidad de filas", "stg -> dw", "filas",
               filas_stg, turnos + cont + dup, TOLERANCIA_EXACTA,
               (f"Cuadre completo de la fuente: {filas_stg:,} filas del Excel = "
                f"{turnos:,} registros de turno cargados + {cont:,} filas de "
                f"continuacion (cargadas solo como paros, no como turnos) + "
                f"{dup} duplicados exactos descartados. Ninguna fila de la "
                f"fuente queda sin explicacion."))

    # =======================================================================
    log.info("")
    log.info("  --- BLOQUE 3: impacto de la limpieza sobre el informe actual ------")
    # =======================================================================
    #  Pruebas INFORMATIVAS: cuantifican lo que el informe del comite reporta
    #  de mas por culpa de los duplicados. No hacen fallar el ETL.

    for columna, etiqueta, unidad in (
        ("horas_trabajadas", "Horas trabajadas", "horas"),
        ("pacas_producidas", "Pacas producidas", "pacas"),
        ("tiempo_paro_total", "Tiempo de paro", "horas"),
    ):
        bruto = float(e(f"SELECT coalesce(sum({NUM.format(col=columna)}),0) FROM stg.base_datos"))
        aporte = aporte_duplicados[columna]
        c.comparar(
            "B3 Inflacion por duplicados", etiqueta, unidad,
            bruto, bruto - aporte, informativa=True,
            explicacion=(
                f"El informe mensual actual reporta {bruto:,.2f} {unidad}; el "
                f"valor correcto es {bruto - aporte:,.2f}. Las 42 filas "
                f"duplicadas inflan la cifra en {aporte:,.2f} {unidad} "
                f"({100 * aporte / bruto:.3f}%). Es un error pequeno en "
                f"magnitud pero sistematico: proviene de guardar dos veces el "
                f"mismo registro en el formulario del Excel y no existe ningun "
                f"control que lo impida."
            ),
        )

    # Efecto sobre el indicador que se lleva al comite.
    disp_bruta = e(f"""
        SELECT 1 - sum({NUM.format(col='tiempo_paro_total')})
                 / sum({NUM.format(col='horas_trabajadas')})
        FROM stg.base_datos WHERE {ANIO} = 2024 AND maquina = 'Vinilos_2'
    """)
    disp_modelo = e("""
        SELECT 1 - sum(h.horas_paro_total) / sum(h.horas_programadas)
        FROM dw.hecho_produccion_turno h
        JOIN dw.dim_fecha f   ON f.fecha_key   = h.fecha_key
        JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
        WHERE f.anio = 2024 AND m.codigo_maquina = 'Vinilos_2'
    """)
    c.comparar(
        "B3 Inflacion por duplicados", "% Productividad V2 2024", "disponibilidad",
        disp_bruta, disp_modelo, informativa=True,
        explicacion=(
            f"El Excel reporta {float(disp_bruta):.6f} y el modelo depurado "
            f"{float(disp_modelo):.6f}. La diferencia es de solo "
            f"{abs(float(disp_modelo) - float(disp_bruta)) * 10000:.2f} puntos "
            f"basicos, porque los duplicados afectan numerador y denominador a "
            f"la vez. El dato relevante no es la magnitud sino que el indicador "
            f"que sustenta decisiones de inversion se calcula hoy sobre un "
            f"conjunto con duplicados no detectados."
        ),
    )

    # =======================================================================
    log.info("")
    log.info("  --- BLOQUE 4: exactitud del despivote, codigo por codigo ----------")
    # =======================================================================
    for n in range(1, 19):
        codigo = f"{n:02d}"
        fuente = e(f"""
            {CTE_DUPLICADOS}
            SELECT coalesce(sum({NUM.format(col='b.cod' + codigo + '_hrs')}), 0)
            FROM stg.base_datos b
            JOIN numeradas n ON n.stg_id = b.stg_id
            WHERE n.rn = 1
        """)
        modelo = e("""
            SELECT coalesce(sum(hp.horas_paro), 0)
            FROM dw.hecho_paro hp
            JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
            WHERE p.codigo_paro = %s
        """, (codigo,))
        c.comparar("B4 Despivote por codigo", f"Codigo {codigo}", "horas",
                   fuente, modelo, TOLERANCIA_HORAS)

    return c
