"""Reglas de calidad de datos, con conteos ANTES y DESPUES de cada limpieza.

Cada regla se registra en aud.regla_calidad, que es la evidencia exigida por
el proyecto: "documentacion de las reglas de limpieza aplicadas y de su
efecto, con conteos antes y despues".

Severidades:
  BLOQUEANTE   detiene el ETL (el dato cargado seria incorrecto)
  ALTA         no detiene, pero exige accion de la planta
  MEDIA        se corrige automaticamente y se reporta
  INFORMATIVA  caracteriza la fuente, no requiere accion
"""

from __future__ import annotations

import logging

from .conexion import escalar, ejecutar

log = logging.getLogger("bi_oee")


class RegistroCalidad:
    def __init__(self, conexion, ejecucion_id: int):
        self.cx = conexion
        self.ejecucion_id = ejecucion_id
        self.fallos_bloqueantes: list[str] = []

    def registrar(self, codigo, dimension, objeto, descripcion, accion,
                  antes=None, afectadas=None, despues=None,
                  severidad="MEDIA", resultado="OK"):
        ejecutar(self.cx, """
            INSERT INTO aud.regla_calidad
                (ejecucion_id, codigo_regla, dimension_calidad, objeto, descripcion,
                 accion_aplicada, filas_antes, filas_afectadas, filas_despues,
                 severidad, resultado)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (self.ejecucion_id, codigo, dimension, objeto, descripcion, accion,
              antes, afectadas, despues, severidad, resultado))
        marca = {"OK": "ok", "ADVERTENCIA": "!!", "FALLO": "XX"}[resultado]
        log.info("  [%s] %-7s %-14s %-28s antes=%-7s afect=%-7s desp=%-7s",
                 marca, codigo, dimension, objeto[:28],
                 antes if antes is not None else "-",
                 afectadas if afectadas is not None else "-",
                 despues if despues is not None else "-")
        if resultado == "FALLO" and severidad == "BLOQUEANTE":
            self.fallos_bloqueantes.append(f"{codigo}: {descripcion}")


# ===========================================================================
def evaluar_reglas(conexion, ejecucion_id: int, metricas: dict) -> RegistroCalidad:
    """Ejecuta el catalogo completo de reglas de calidad sobre el dato cargado."""
    reg = RegistroCalidad(conexion, ejecucion_id)
    e = lambda sql: escalar(conexion, sql)  # noqa: E731

    filas_stg = e("SELECT count(*) FROM stg.base_datos")
    turnos = e("SELECT count(*) FROM dw.hecho_produccion_turno")
    paros = e("SELECT count(*) FROM dw.hecho_paro")

    # ---------------------------------------------------------------- DQ-01
    reg.registrar(
        "DQ-01", "Unicidad", "stg.base_datos",
        "Filas identicas en las 58 columnas de la hoja fuente, producidas por "
        "guardar dos veces el mismo registro desde el formulario del Excel.",
        "Se descarta la ocurrencia repetida conservando la primera (deduplicacion "
        "por hash SHA-256 de la fila completa).",
        antes=filas_stg,
        afectadas=metricas.get("duplicados_exactos", 0),
        despues=filas_stg - metricas.get("duplicados_exactos", 0),
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-02
    cont = metricas.get("continuaciones", 0)
    reg.registrar(
        "DQ-02", "Validez", "stg.base_datos",
        "Filas de continuacion generadas por el boton 'Ingreso subcodigo': "
        "repiten la cabecera del turno y no traen pacas ni horas trabajadas. "
        "Cargarlas como turnos duplicaria el tiempo programado.",
        "Se excluyen de hecho_produccion_turno. Sus paros SI se cargan en "
        "hecho_paro y se suman al turno al que pertenecen.",
        antes=filas_stg, afectadas=cont, despues=turnos,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-03
    reg.registrar(
        "DQ-03", "Consistencia", "dw.hecho_paro",
        "Horas de paro en filas de continuacion que no pudieron vincularse a "
        "ningun registro de turno ni por clave exacta ni por fecha y maquina.",
        "Se conservan en hecho_paro (ningun minuto de la fuente se pierde) y se "
        "reportan por separado en la conciliacion.",
        antes=cont,
        afectadas=metricas.get("cont_huerfanas", 0),
        despues=metricas.get("cont_vinculadas_n1", 0)
                + metricas.get("cont_vinculadas_n2", 0)
                + metricas.get("cont_vinculadas_n3", 0),
        severidad="MEDIA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-04
    col8_informada = e("""
        SELECT count(*) FROM stg.base_datos WHERE unidad_por_display_src IS NOT NULL
    """)
    col8_redundante = e("""
        SELECT count(*) FROM stg.base_datos
        WHERE unidad_por_display_src IS NOT NULL AND turno IS NOT NULL
    """)
    reg.registrar(
        "DQ-04", "Exactitud", "columnas 7, 8 y 9 de la hoja fuente",
        f"Las TRES columnas que deberian permitir convertir pacas a unidades "
        f"son inservibles: 'Unidades producidas cada minuto' (col 7) y "
        f"'Display por paca' (col 9) estan 100% VACIAS en las 8.208 filas, y "
        f"'Unidad por display' (col 8) fue reutilizada para guardar el TURNO en "
        f"{col8_informada} filas, de las cuales {col8_redundante} ya traian el "
        f"turno en su columna correcta (las 3 aparentes discrepancias son solo "
        f"variantes de notacion del mismo turno). Sin estas columnas la hoja de "
        f"hechos no permite por si sola expresar la produccion en unidades "
        f"comparables entre referencias de 6 y de 12 colores.",
        "La conversion pacas -> unidades se toma del catalogo maquina x "
        "referencia de la hoja 'Tablas Desplegables' (unidades_por_paca), no de "
        "la hoja de hechos. El valor de turno hallado en la columna 8 se usa "
        "como respaldo defensivo cuando la columna correcta viene vacia. "
        "RECOMENDACION: eliminar las columnas 7 y 9 del formato o poblarlas, y "
        "corregir el formulario para que no escriba el turno en la columna 8.",
        antes=filas_stg, afectadas=col8_informada, despues=filas_stg,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-05
    turno_imputado = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE turno_imputado")
    reg.registrar(
        "DQ-05", "Completitud", "dw.hecho_produccion_turno.turno_key",
        "Registros de turno sin turno diligenciado.",
        "Se asigna el miembro tecnico 'Sin informar' (nunca NULL, para "
        "preservar la integridad referencial) y se marca turno_imputado=true "
        "para que el tablero pueda excluirlos.",
        antes=turnos, afectadas=turno_imputado, despues=turnos,
        severidad="ALTA" if turno_imputado > turnos * 0.2 else "MEDIA",
        resultado="ADVERTENCIA" if turno_imputado else "OK",
    )

    # ---------------------------------------------------------------- DQ-06
    sin_operario = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE operario_no_informado")
    reg.registrar(
        "DQ-06", "Completitud", "dw.hecho_produccion_turno.operario_key",
        "Registros sin operario, o con los marcadores 'No' / 'No aplica'.",
        "Se asigna el miembro tecnico OPR-000 'Sin informar'.",
        antes=turnos, afectadas=sin_operario, despues=turnos,
        severidad="MEDIA", resultado="ADVERTENCIA" if sin_operario else "OK",
    )

    # ---------------------------------------------------------------- DQ-07
    sin_referencia = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE referencia_no_informada")
    reg.registrar(
        "DQ-07", "Completitud", "dw.hecho_produccion_turno.referencia_key",
        "Registros sin referencia de producto. Sin referencia no hay unidades "
        "por paca ni tasa ideal, por lo que no se puede calcular Rendimiento.",
        "Se asigna el miembro 'Sin informar' y el turno queda excluido del "
        "calculo de Rendimiento (tiene_estandar=false).",
        antes=turnos, afectadas=sin_referencia, despues=turnos,
        severidad="ALTA", resultado="ADVERTENCIA" if sin_referencia else "OK",
    )

    # ---------------------------------------------------------------- DQ-08
    variantes = e("SELECT count(*) FROM dw.dim_referencia WHERE variantes_fuente IS NOT NULL")
    total_ref = e("SELECT count(*) FROM dw.dim_referencia")
    reg.registrar(
        "DQ-08", "Consistencia", "dw.dim_referencia",
        "Erratas tipograficas y de espaciado en el nombre de la referencia: "
        "'Alocdor' por 'Alocolor', 'Stilo Kids' por 'Estilo Kids', "
        "'(12col)' por '(12 col)'.",
        "Normalizacion por clave canonica (sin tildes, sin puntuacion, sin "
        "espacios) mas un diccionario de correcciones explicitas. Las variantes "
        "quedan registradas en dim_referencia.variantes_fuente.",
        antes=52, afectadas=variantes, despues=total_ref,
        severidad="MEDIA", resultado="OK",
    )

    # ---------------------------------------------------------------- DQ-09
    #  El denominador son SOLO los eventos de los codigos 01, 03 y 05, que son
    #  los unicos con arbol de subcodigos. Medirlo sobre los 18 codigos daria
    #  un 78% de falsos incompletos.
    paros_con_sub = e("""
        SELECT count(*) FROM dw.hecho_paro hp
        JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
        WHERE p.admite_subcodigo
    """)
    sub_imputado = e("SELECT count(*) FROM dw.hecho_paro WHERE subcodigo_imputado")
    pct = (100.0 * sub_imputado / paros_con_sub) if paros_con_sub else 0
    reg.registrar(
        "DQ-09", "Completitud", "dw.hecho_paro.paro_key (subcodigo)",
        f"Eventos de paro de los codigos 01, 03 y 05 -los unicos que tienen "
        f"arbol de subcodigos- sin causa raiz utilizable: la fuente trae "
        f"'Sin especificar' o un texto no reconocible. Son {sub_imputado} de "
        f"{paros_con_sub} eventos ({pct:.1f}%). Sin subcodigo no hay analisis "
        f"de causa raiz, que es justamente el objetivo del P-MTO-22.",
        "Se asigna el miembro de relleno 'SIN-ESP' de la jerarquia ragged y se "
        "marca subcodigo_imputado=true. Alimenta el indicador de completitud "
        "del registro que se reporta a la gerencia.",
        antes=paros_con_sub, afectadas=sub_imputado,
        despues=paros_con_sub - (sub_imputado or 0),
        severidad="ALTA", resultado="ADVERTENCIA" if sub_imputado else "OK",
    )

    # ---------------------------------------------------------------- DQ-10
    reg.registrar(
        "DQ-10", "Consistencia", "columna 'Subcodigo 5' / 'Sub Codigo de paro 1'",
        "DOS taxonomias de subcodigos conviviendo en la misma columna: la rama "
        "historica '4.x' en mayusculas y la vigente '5.x'. En el codigo 01 hay "
        "45 formas de escribir ~25 subcodigos. Sin unificar, cada causa se "
        "parte en dos y ninguna alcanza el umbral de atencion en el Pareto.",
        "Mapeo de la taxonomia historica a la vigente por PREFIJO NUMERICO "
        "(4.1->5.1 ... 4.4->5.5 ... 4.8->5.9) y correccion de la errata del "
        "propio catalogo fuente ('1.4.3 Sensor' -> '1.4.C').",
        antes=None, afectadas=None, despues=None,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-11
    excede = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE paro_excede_programado")
    reg.registrar(
        "DQ-11", "Validez", "dw.hecho_produccion_turno",
        "Turnos cuyo tiempo de paro supera el tiempo programado (imposible "
        "fisicamente). El caso extremo declara 15,63 h de paro en un turno de 8 h.",
        "Se conserva el dato tal cual para no alterar la conciliacion con la "
        "fuente, pero se marca paro_excede_programado=true y la disponibilidad "
        "se acota a cero (horas_operativas no puede ser negativa).",
        antes=turnos, afectadas=excede, despues=turnos,
        severidad="ALTA", resultado="ADVERTENCIA" if excede else "OK",
    )

    # ---------------------------------------------------------------- DQ-12
    fuera_rango = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE horas_fuera_de_rango")
    reg.registrar(
        "DQ-12", "Validez", "dw.hecho_produccion_turno.horas_programadas",
        "Horas trabajadas fuera del rango plausible de un turno (mas de 12 h).",
        "Se marca horas_fuera_de_rango=true. No se corrige el valor: alterarlo "
        "rompria la conciliacion con la fuente y la decision es del dueno del dato.",
        antes=turnos, afectadas=fuera_rango, despues=turnos,
        severidad="MEDIA", resultado="ADVERTENCIA" if fuera_rango else "OK",
    )

    # ---------------------------------------------------------------- DQ-13
    atipicos = e("SELECT count(*) FROM dw.hecho_paro WHERE minutos_atipicos")
    reg.registrar(
        "DQ-13", "Validez", "dw.hecho_paro.minutos_paro",
        "Eventos de paro atipicos: un solo codigo con mas de 480 minutos "
        "(8 horas) en un unico turno.",
        "Se marca minutos_atipicos=true para que el analisis de causas pueda "
        "aislarlos; el valor se conserva.",
        antes=paros, afectadas=atipicos, despues=paros,
        severidad="MEDIA", resultado="ADVERTENCIA" if atipicos else "OK",
    )

    # ---------------------------------------------------------------- DQ-14
    sin_estandar = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE NOT tiene_estandar")
    inferidos = e("SELECT count(*) FROM dw.dim_estandar WHERE origen_estandar = 'Inferido por referencia'")
    reg.registrar(
        "DQ-14", "Completitud", "dw.dim_estandar",
        "Pares maquina-referencia presentes en los hechos pero ausentes del "
        "catalogo de estandares de la fuente: sin tasa ideal no se puede "
        "calcular el componente Rendimiento del OEE.",
        f"Cascada de resolucion: catalogo exacto; si no, inferencia desde la "
        f"misma referencia en otra maquina ajustada por factor de produccion "
        f"({inferidos} estandares inferidos); si no, el turno se excluye del "
        f"Rendimiento sin inventar ningun dato.",
        antes=turnos, afectadas=sin_estandar, despues=turnos - sin_estandar,
        severidad="ALTA", resultado="ADVERTENCIA" if sin_estandar else "OK",
    )

    # ---------------------------------------------------------------- DQ-15
    hnt_invalida = e("""
        SELECT count(*) FROM stg.base_datos
        WHERE nullif(horas_no_trabajadas,'')::numeric > 24
    """)
    hnt_24 = e("""
        SELECT count(*) FROM stg.base_datos
        WHERE nullif(horas_no_trabajadas,'')::numeric = 24
    """)
    reg.registrar(
        "DQ-15", "Exactitud", "columna 'Horas no trabajadas'",
        f"La columna NO contiene tiempo de paro: {hnt_24} filas traen el valor "
        f"24 y 390 traen 16, es decir 24 menos las horas trabajadas. Representa "
        f"tiempo de CALENDARIO no programado. Su suma (41.519,85 h) supera la de "
        f"horas trabajadas (38.063,35 h), lo que confirma la interpretacion. "
        f"Hay {hnt_invalida} fila con un valor mayor a 24 h, imposible en un dia.",
        "Se carga como horas_no_programadas, se EXCLUYE del calculo del OEE y "
        "se usa para el indicador nuevo de utilizacion del calendario.",
        antes=filas_stg, afectadas=hnt_24, despues=filas_stg,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-16
    tipo_sin = e("""
        SELECT count(*) FROM dw.hecho_produccion_turno h
        JOIN dw.dim_tipo_paro_cabecera t ON t.tipo_paro_key = h.tipo_paro_key
        WHERE t.codigo_tipo = 'TPC-SIN'
    """)
    reg.registrar(
        "DQ-16", "Consistencia", "columna 'Tipo de paro'",
        "Una sola columna mezcla DOS taxonomias historicas: la vigente con "
        "prefijo '[NN]' y la antigua con prefijo 'N.' en mayusculas, con 19 "
        "variantes para 13 conceptos de negocio (p. ej. '[18] Paro de maquina "
        "por ventas' y '17. PARO DE MAQUINA ' son lo mismo).",
        "Consolidacion en dim_tipo_paro_cabecera con 13 miembros y la columna "
        "variantes_fuente que documenta cada equivalencia.",
        antes=turnos, afectadas=tipo_sin, despues=turnos,
        severidad="MEDIA", resultado="ADVERTENCIA" if tipo_sin else "OK",
    )

    # ---------------------------------------------------------------- DQ-17
    sub_redundante = escalar(conexion, "SELECT count(*) FROM stg.base_subcodigos")
    reg.registrar(
        "DQ-17", "Unicidad", "hoja oculta 'Base de datos de Sub codigos'",
        f"Hoja oculta con {sub_redundante} filas (oct-2023 a may-2024) que "
        f"duplica informacion: 982 de ellas ya existen en 'Base De Datos'. "
        f"Cargarla sumaria 679,22 horas de paro inexistentes. Las 270 filas "
        f"restantes no tienen minutos de paro.",
        "Se extrae a staging para auditoria pero NO se carga al modelo "
        "dimensional. Se recomienda a la planta eliminar la hoja o convertirla "
        "en la unica fuente de subcodigos, no en una copia paralela.",
        antes=sub_redundante, afectadas=sub_redundante, despues=0,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    # ---------------------------------------------------------------- DQ-21
    implausibles = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE rendimiento_implausible")
    con_estandar = e("SELECT count(*) FROM dw.hecho_produccion_turno WHERE tiene_estandar")
    peor = e("""
        SELECT round(max(rendimiento) * 100, 1) FROM dw.hecho_produccion_turno
        WHERE rendimiento_implausible
    """)
    reg.registrar(
        "DQ-21", "Validez", "dw.hecho_produccion_turno.rendimiento",
        f"Turnos cuya produccion declarada supera en mas de 50% el maximo "
        f"teorico del estandar. El caso extremo declara un rendimiento de "
        f"{peor}%, es decir produjo supuestamente {float(peor or 0)/100:.0f} veces "
        f"lo que la maquina puede dar en el tiempo disponible. Las causas "
        f"posibles son tres: pacas mal digitadas, horas trabajadas "
        f"subregistradas, o estandar de ingenieria obsoleto para esa referencia.",
        "Se marca rendimiento_implausible=true. El valor se conserva para "
        "poder auditarlo, pero las vistas analiticas lo EXCLUYEN del "
        "Rendimiento y del OEE agregados: un solo turno de este tipo arrastra "
        "el indicador mensual de toda la linea.",
        antes=con_estandar, afectadas=implausibles,
        despues=con_estandar - (implausibles or 0),
        severidad="ALTA", resultado="ADVERTENCIA" if implausibles else "OK",
    )

    # ---------------------------------------------------------------- DQ-18
    #  Regla BLOQUEANTE: integridad interna del modelo cargado.
    inconsistentes = e("""
        SELECT count(*) FROM dw.hecho_produccion_turno
        WHERE abs(horas_paro_total - (horas_paro_planeado + horas_paro_no_planeado)) > 0.0005
           OR abs(horas_operativas - greatest(horas_programadas - horas_paro_total, 0)) > 0.0005
    """)
    reg.registrar(
        "DQ-18", "Consistencia", "dw.hecho_produccion_turno",
        "Coherencia aritmetica interna: el paro total debe igualar la suma de "
        "paro planeado y no planeado, y el tiempo operativo debe ser el "
        "programado menos el paro.",
        "Verificacion posterior a la carga. Si falla, el ETL se detiene y la "
        "transaccion completa se revierte.",
        antes=turnos, afectadas=inconsistentes, despues=turnos,
        severidad="BLOQUEANTE",
        resultado="FALLO" if inconsistentes else "OK",
    )

    # ---------------------------------------------------------------- DQ-19
    huerfanos = e("""
        SELECT count(*) FROM dw.hecho_paro hp
        LEFT JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
        WHERE p.paro_key IS NULL
    """)
    reg.registrar(
        "DQ-19", "Consistencia", "integridad referencial de los hechos",
        "Ningun hecho puede apuntar a una clave de dimension inexistente.",
        "Garantizado por las restricciones FOREIGN KEY del DDL; se verifica "
        "explicitamente despues de la carga.",
        antes=paros, afectadas=huerfanos, despues=paros,
        severidad="BLOQUEANTE",
        resultado="FALLO" if huerfanos else "OK",
    )

    # ---------------------------------------------------------------- DQ-20
    reg.registrar(
        "DQ-20", "Validez", "componente Calidad del OEE",
        "LIMITACION ESTRUCTURAL DE LA FUENTE: no existe ninguna columna de "
        "unidades defectuosas, rechazadas ni reenvasadas. El componente "
        "Calidad del OEE no es medible con el dato actual.",
        "Se calcula un PROXY como cota inferior, convirtiendo el tiempo de "
        "reproceso (codigo 11) en unidades equivalentes. Se reporta siempre el "
        "OEE en dos variantes: oee_ad (Disponibilidad x Rendimiento, auditable) "
        "y oee_completo (con el proxy, para lectura indicativa). "
        "RECOMENDACION A LA GERENCIA: anadir al formato hora a hora una "
        "casilla de unidades no conformes.",
        antes=None, afectadas=None, despues=None,
        severidad="ALTA", resultado="ADVERTENCIA",
    )

    return reg
