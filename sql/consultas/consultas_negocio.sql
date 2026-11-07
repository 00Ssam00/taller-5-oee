-- ===========================================================================
--  consultas_negocio.sql
--  Proyecto BI-OEE  -  consultas analiticas para DBeaver
--
--  Cada consulta declara la PREGUNTA DE NEGOCIO que responde y el USUARIO que
--  la consume. Todas usan agregaciones; las marcadas con [VENTANA] usan
--  funciones de ventana y las marcadas con [PERIODO] comparan periodos.
--
--  Ejecutar en DBeaver conectado a bi_oee. Las consultas son de solo lectura.
-- ===========================================================================


-- ###########################################################################
--  C01  [PERIODO]
--  PREGUNTA   : Como evoluciono el OEE y sus tres componentes por maquina y
--               por anio, y cuanto cambio frente al anio anterior?
--  USUARIO    : Gerencia / Direccion de operaciones (decision de inversion)
--  POR QUE    : Es la pregunta que hoy el Excel no puede responder, porque
--               solo calcula el equivalente a la Disponibilidad.
--  OJO        : el OEE se calcula como razon de sumas y sobre los turnos con
--               estandar de ingenieria y rendimiento plausible, los MISMOS
--               para sus dos factores. La columna cobertura_oee dice que
--               fraccion del anio es esa; en 2022 es cero y el OEE sale nulo,
--               porque ese anio la fuente no registro ninguna meta por hora.
-- ###########################################################################
WITH por_anio AS (
    SELECT
        f.anio,
        m.codigo_maquina,
        sum(h.horas_programadas)                                      AS horas_programadas,
        sum(h.horas_paro_total)                                       AS horas_paro,
        sum(h.horas_operativas)                                       AS horas_operativas,
        sum(h.unidades_producidas) FILTER (
            WHERE h.tiene_estandar AND NOT h.rendimiento_implausible) AS unidades_reales,
        sum(h.unidades_posibles)   FILTER (
            WHERE h.tiene_estandar AND NOT h.rendimiento_implausible) AS unidades_posibles,
        -- Horas del MISMO subconjunto que las unidades. El OEE es el producto
        -- de dos factores, asi que los dos tienen que medir la misma poblacion
        -- de turnos. Ver la cobertura mas abajo: en 2023 solo una quinta parte
        -- de los turnos trae estandar de ingenieria.
        sum(h.horas_operativas)    FILTER (
            WHERE h.tiene_estandar AND NOT h.rendimiento_implausible) AS horas_oper_est,
        sum(h.horas_programadas)   FILTER (
            WHERE h.tiene_estandar AND NOT h.rendimiento_implausible) AS horas_prog_est,
        count(*) FILTER (
            WHERE h.tiene_estandar AND NOT h.rendimiento_implausible) AS turnos_auditables,
        count(*)                                                      AS turnos
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, m.codigo_maquina
),
indicadores AS (
    SELECT
        anio, codigo_maquina, turnos,
        round(horas_programadas, 1)                                   AS horas_programadas,
        round(horas_paro, 1)                                          AS horas_paro,
        -- Disponibilidad sobre TODOS los turnos: solo necesita horas, asi que
        -- se reporta con cobertura total. Es la que reproduce el
        -- "% Productividad" del Excel.
        round(horas_operativas / horas_programadas, 4)                AS disponibilidad,
        round(unidades_reales::numeric / nullif(unidades_posibles, 0), 4) AS rendimiento,
        -- Factor de disponibilidad que entra en el OEE, restringido.
        round(horas_oper_est / nullif(horas_prog_est, 0), 4)          AS disponibilidad_oee,
        round(horas_oper_est / nullif(horas_prog_est, 0)
              * unidades_reales::numeric / nullif(unidades_posibles, 0), 4) AS oee,
        round(turnos_auditables::numeric / turnos, 4)                 AS cobertura_oee
    FROM por_anio
)
SELECT
    anio,
    codigo_maquina,
    turnos,
    horas_programadas,
    horas_paro,
    disponibilidad,
    disponibilidad_oee,
    rendimiento,
    oee,
    -- El OEE se lee SIEMPRE junto a esta cobertura.
    cobertura_oee,
    -- [VENTANA] valor del anio anterior de la MISMA maquina
    lag(oee) OVER (PARTITION BY codigo_maquina ORDER BY anio)          AS oee_anio_anterior,
    -- [PERIODO] variacion absoluta en puntos porcentuales
    round(100 * (oee - lag(oee) OVER (PARTITION BY codigo_maquina ORDER BY anio)), 2)
                                                                       AS variacion_pp,
    -- [VENTANA] ranking de la maquina dentro de cada anio
    rank() OVER (PARTITION BY anio ORDER BY oee DESC NULLS LAST)        AS puesto_en_el_anio
FROM indicadores
ORDER BY codigo_maquina, anio;


-- ###########################################################################
--  C02  [VENTANA]
--  PREGUNTA   : Cuales son las pocas causas de paro que explican el 80% del
--               tiempo perdido en cada maquina? (analisis de Pareto)
--  USUARIO    : Coordinador de mantenimiento (priorizacion del plan)
--  POR QUE    : Permite dejar de repartir esfuerzo entre 18 codigos y
--               concentrarlo en los 3 o 4 que realmente cuestan.
-- ###########################################################################
WITH causas AS (
    SELECT
        m.codigo_maquina,
        p.area_impacto,
        p.etiqueta_codigo_paro,
        p.naturaleza_paro,
        sum(hp.horas_paro)                 AS horas_paro,
        count(*)                           AS eventos,
        sum(hp.unidades_no_producidas)     AS unidades_no_producidas
    FROM dw.hecho_paro hp
    JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
    JOIN dw.dim_paro    p ON p.paro_key    = hp.paro_key
    JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
    WHERE f.anio >= 2024          -- periodo de analisis
    GROUP BY m.codigo_maquina, p.area_impacto, p.etiqueta_codigo_paro, p.naturaleza_paro
)
SELECT
    codigo_maquina,
    etiqueta_codigo_paro,
    area_impacto,
    naturaleza_paro,
    round(horas_paro, 1)                                                AS horas_paro,
    eventos,
    round(horas_paro / eventos, 2)                                      AS horas_por_evento,
    coalesce(unidades_no_producidas, 0)                                 AS unidades_no_producidas,
    -- [VENTANA] participacion de la causa en el total de su maquina
    round(100 * horas_paro / sum(horas_paro) OVER (PARTITION BY codigo_maquina), 2)
                                                                        AS pct_del_total,
    -- [VENTANA] suma acumulada ordenada de mayor a menor = curva de Pareto
    round(100 * sum(horas_paro) OVER (
                    PARTITION BY codigo_maquina
                    ORDER BY horas_paro DESC
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / sum(horas_paro) OVER (PARTITION BY codigo_maquina), 2)  AS pct_acumulado,
    row_number() OVER (PARTITION BY codigo_maquina ORDER BY horas_paro DESC) AS puesto,
    CASE WHEN 100 * sum(horas_paro) OVER (
                        PARTITION BY codigo_maquina
                        ORDER BY horas_paro DESC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / sum(horas_paro) OVER (PARTITION BY codigo_maquina) <= 80
         THEN 'Causa vital (80%)' ELSE 'Causa trivial' END              AS clasificacion_pareto
FROM causas
ORDER BY codigo_maquina, horas_paro DESC;


-- ###########################################################################
--  C03  [VENTANA][PERIODO]
--  PREGUNTA   : Que tendencia mensual sigue el OEE y hay senales de deterioro
--               sostenido que justifiquen intervenir una linea?
--  USUARIO    : Direccion de operaciones
--  TECNICA    : media movil de 3 meses + comparacion con el mismo mes del
--               anio anterior (year over year).
-- ###########################################################################
WITH mensual AS (
    SELECT
        f.anio, f.mes, f.anio_mes, f.etiqueta_anio_mes,
        m.codigo_maquina,
        sum(h.horas_programadas)  AS horas_programadas,
        sum(h.horas_operativas)   AS horas_operativas,
        sum(h.horas_paro_total)   AS horas_paro
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, f.mes, f.anio_mes, f.etiqueta_anio_mes, m.codigo_maquina
),
con_disponibilidad AS (
    SELECT *, round(horas_operativas / horas_programadas, 4) AS disponibilidad
    FROM mensual WHERE horas_programadas > 0
)
SELECT
    codigo_maquina,
    etiqueta_anio_mes,
    round(horas_programadas, 1)   AS horas_programadas,
    round(horas_paro, 1)          AS horas_paro,
    disponibilidad,
    -- [VENTANA] media movil de 3 meses: aisla la tendencia del ruido mensual
    round(avg(disponibilidad) OVER (
              PARTITION BY codigo_maquina ORDER BY anio_mes
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 4)             AS media_movil_3m,
    -- [VENTANA] mes anterior y variacion
    round(disponibilidad - lag(disponibilidad) OVER (
              PARTITION BY codigo_maquina ORDER BY anio_mes), 4)        AS var_vs_mes_anterior,
    -- [PERIODO] mismo mes del anio anterior (12 posiciones atras)
    lag(disponibilidad, 12) OVER (
              PARTITION BY codigo_maquina ORDER BY anio_mes)            AS disp_mismo_mes_anio_ant,
    round(disponibilidad - lag(disponibilidad, 12) OVER (
              PARTITION BY codigo_maquina ORDER BY anio_mes), 4)        AS var_interanual,
    -- [VENTANA] mejor y peor mes historico de la maquina, como referencia
    max(disponibilidad) OVER (PARTITION BY codigo_maquina)              AS mejor_mes_historico,
    min(disponibilidad) OVER (PARTITION BY codigo_maquina)              AS peor_mes_historico
FROM con_disponibilidad
ORDER BY codigo_maquina, anio_mes;


-- ###########################################################################
--  C04
--  PREGUNTA   : Cuanto producto dejamos de envasar por culpa de los paros, y
--               cuanto de esa perdida es evitable (paros NO planeados)?
--  USUARIO    : Gerencia (traduce horas tecnicas a lenguaje de negocio)
--  POR QUE    : "perdimos 1.069 horas" no mueve a nadie; "dejamos de envasar
--               3,9 millones de unidades" si.
-- ###########################################################################
SELECT
    f.anio,
    m.codigo_maquina,
    round(sum(hp.horas_paro) FILTER (WHERE NOT hp.es_paro_planeado), 1) AS horas_no_planeado,
    round(sum(hp.horas_paro) FILTER (WHERE hp.es_paro_planeado), 1)     AS horas_planeado,
    sum(hp.unidades_no_producidas) FILTER (WHERE NOT hp.es_paro_planeado)
                                                                        AS unidades_perdidas_evitables,
    sum(hp.unidades_no_producidas)                                      AS unidades_perdidas_total,
    round(100.0 * sum(hp.horas_paro) FILTER (WHERE NOT hp.es_paro_planeado)
                / sum(hp.horas_paro), 1)                               AS pct_paro_evitable,
    count(*)                                                            AS eventos_paro,
    count(*) FILTER (WHERE NOT hp.es_paro_planeado)                     AS eventos_no_planeados
FROM dw.hecho_paro hp
JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
GROUP BY f.anio, m.codigo_maquina
ORDER BY f.anio, m.codigo_maquina;


-- ###########################################################################
--  C05  [VENTANA]
--  PREGUNTA   : Que SISTEMA FISICO de la maquina nos cuesta mas tiempo, sin
--               importar si el tiempo se perdio por una falla (codigo 01), por
--               un problema de servicios (codigo 03) o por un ajuste
--               operativo (codigo 05)?
--  USUARIO    : Jefe de mantenimiento (decision de repuestos y rediseno)
--  POR QUE    : Es la pregunta que el Excel NO puede responder, porque alli
--               las ramas 1.x, 3.x y 5.x viven en columnas separadas. El
--               atributo conformado dim_paro.codigo_sistema las une.
-- ###########################################################################
SELECT
    p.nombre_sistema,
    round(sum(hp.horas_paro), 1)                                        AS horas_totales,
    round(sum(hp.horas_paro) FILTER (WHERE p.codigo_paro = '01'), 1)    AS por_falla_c01,
    round(sum(hp.horas_paro) FILTER (WHERE p.codigo_paro = '03'), 1)    AS por_servicios_c03,
    round(sum(hp.horas_paro) FILTER (WHERE p.codigo_paro = '05'), 1)    AS por_ajuste_c05,
    count(*)                                                            AS eventos,
    count(DISTINCT hp.maquina_key)                                      AS maquinas_afectadas,
    -- [VENTANA] participacion del sistema sobre el total de los codigos 01/03/05
    round(100 * sum(hp.horas_paro) / sum(sum(hp.horas_paro)) OVER (), 2) AS pct_del_total,
    round(100 * sum(sum(hp.horas_paro)) OVER (
                    ORDER BY sum(hp.horas_paro) DESC
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / sum(sum(hp.horas_paro)) OVER (), 2)                     AS pct_acumulado
FROM dw.hecho_paro hp
JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
WHERE p.codigo_paro IN ('01', '03', '05')
  AND p.codigo_sistema <> 'SYS-NA'
GROUP BY p.nombre_sistema
ORDER BY horas_totales DESC;


-- ###########################################################################
--  C06  [VENTANA]
--  PREGUNTA   : Confiabilidad de cada linea: cada cuantas horas falla (MTBF)
--               y cuanto tarda en volver a producir (MTTR)?
--  USUARIO    : Mantenimiento (dimensionar el equipo de respuesta)
-- ###########################################################################
WITH fallas AS (
    SELECT f.anio, m.codigo_maquina,
           count(*) AS eventos_falla, sum(hp.horas_paro) AS horas_reparacion
    FROM dw.hecho_paro hp
    JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
    JOIN dw.dim_paro    p ON p.paro_key    = hp.paro_key
    WHERE p.codigo_paro IN ('01', '02')   -- falla electromecanica y espera de soporte
    GROUP BY f.anio, m.codigo_maquina
),
operacion AS (
    SELECT f.anio, m.codigo_maquina, sum(h.horas_operativas) AS horas_operativas
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, m.codigo_maquina
)
SELECT
    o.anio,
    o.codigo_maquina,
    round(o.horas_operativas, 1)                                        AS horas_operativas,
    coalesce(fa.eventos_falla, 0)                                       AS fallas,
    round(coalesce(fa.horas_reparacion, 0), 2)                          AS horas_reparacion,
    round(o.horas_operativas / nullif(fa.eventos_falla, 0), 1)          AS mtbf_horas,
    round(fa.horas_reparacion / nullif(fa.eventos_falla, 0), 2)         AS mttr_horas,
    round(o.horas_operativas
          / (o.horas_operativas + coalesce(fa.horas_reparacion, 0)), 4) AS disponibilidad_inherente,
    -- [VENTANA] MTBF del anio anterior, para ver si la confiabilidad mejora
    round(lag(o.horas_operativas / nullif(fa.eventos_falla, 0))
              OVER (PARTITION BY o.codigo_maquina ORDER BY o.anio), 1)  AS mtbf_anio_anterior
FROM operacion o
LEFT JOIN fallas fa ON fa.anio = o.anio AND fa.codigo_maquina = o.codigo_maquina
ORDER BY o.codigo_maquina, o.anio;


-- ###########################################################################
--  C07  [VENTANA]
--  PREGUNTA   : Hay diferencias de desempeno entre turnos que justifiquen
--               revisar la formacion o el acompanamiento en alguno?
--  USUARIO    : Jefe de produccion
--  NOTA DE PRIVACIDAD: se analiza por TURNO, no por persona. La dimension de
--  operario existe pseudonimizada, pero usarla para comparar individuos seria
--  un uso del dato personal distinto al declarado. El analisis por turno
--  responde la misma pregunta de gestion sin ese riesgo.
-- ###########################################################################
SELECT
    t.nombre_turno,
    t.tipo_jornada,
    t.es_nocturno,
    count(*)                                                            AS turnos_registrados,
    round(sum(h.horas_programadas), 1)                                  AS horas_programadas,
    round(sum(h.horas_operativas) / sum(h.horas_programadas), 4)        AS disponibilidad,
    round(sum(h.unidades_producidas) FILTER (
              WHERE h.tiene_estandar AND NOT h.rendimiento_implausible)::numeric
          / nullif(sum(h.unidades_posibles) FILTER (
              WHERE h.tiene_estandar AND NOT h.rendimiento_implausible), 0), 4)
                                                                        AS rendimiento,
    round(sum(h.horas_paro_no_planeado) / sum(h.horas_programadas), 4)  AS tasa_paro_no_planeado,
    -- [VENTANA] desvio de cada turno frente al promedio global de la planta
    round(sum(h.horas_operativas) / sum(h.horas_programadas)
          - avg(sum(h.horas_operativas) / sum(h.horas_programadas)) OVER (), 4)
                                                                        AS desvio_vs_planta
FROM dw.hecho_produccion_turno h
JOIN dw.dim_turno t ON t.turno_key = h.turno_key
WHERE t.es_valido                 -- excluye 'No aplica' y 'Sin informar'
GROUP BY t.nombre_turno, t.tipo_jornada, t.es_nocturno, t.orden_presentacion
ORDER BY t.orden_presentacion;


-- ###########################################################################
--  C08  [VENTANA]
--  PREGUNTA   : Que referencias de producto son mas dificiles de envasar, es
--               decir cuales nos alejan mas del estandar de ingenieria?
--  USUARIO    : Planeacion de produccion y ventas (mezcla de producto)
-- ###########################################################################
SELECT
    r.linea_comercial,
    r.nombre_referencia,
    r.volumen_cc,
    r.numero_colores,
    count(*)                                                            AS turnos,
    sum(h.pacas_producidas)                                             AS pacas,
    sum(h.unidades_producidas)                                          AS unidades,
    round(avg(h.tasa_ideal_unid_min), 2)                                AS estandar_unid_min,
    round(sum(h.unidades_producidas)::numeric
          / nullif(sum(h.unidades_posibles), 0), 4)                     AS rendimiento,
    round(sum(h.horas_paro_total) / sum(h.horas_programadas), 4)        AS tasa_paro,
    -- [VENTANA] ranking de dificultad dentro de la linea comercial
    rank() OVER (PARTITION BY r.linea_comercial
                 ORDER BY sum(h.unidades_producidas)::numeric
                          / nullif(sum(h.unidades_posibles), 0) ASC)    AS puesto_dificultad,
    -- [VENTANA] rendimiento promedio de la linea comercial, como referencia
    round(avg(sum(h.unidades_producidas)::numeric
              / nullif(sum(h.unidades_posibles), 0))
              OVER (PARTITION BY r.linea_comercial), 4)                 AS rendimiento_linea
FROM dw.hecho_produccion_turno h
JOIN dw.dim_referencia r ON r.referencia_key = h.referencia_key
WHERE h.tiene_estandar
  AND NOT h.rendimiento_implausible
  AND NOT r.es_no_aplica
GROUP BY r.linea_comercial, r.nombre_referencia, r.volumen_cc, r.numero_colores
HAVING count(*) >= 5              -- solo referencias con historia suficiente
ORDER BY rendimiento ASC
LIMIT 25;


-- ###########################################################################
--  C09  [PERIODO]
--  PREGUNTA   : Cuanto cuesta el cambio de referencia (codigo 07) y conviene
--               agrupar ordenes para reducirlo?
--  USUARIO    : Planeacion de produccion
--  POR QUE    : Cuantifica el costo oculto de una mezcla de producto muy
--               fragmentada, que hoy nadie mide.
-- ###########################################################################
WITH cambios AS (
    SELECT
        f.anio, f.trimestre, m.codigo_maquina,
        count(*)            AS eventos_cambio,
        sum(hp.horas_paro)  AS horas_cambio
    FROM dw.hecho_paro hp
    JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
    JOIN dw.dim_paro    p ON p.paro_key    = hp.paro_key
    WHERE p.codigo_paro = '07'          -- alistamiento / cambio de referencia
    GROUP BY f.anio, f.trimestre, m.codigo_maquina
),
contexto AS (
    SELECT f.anio, f.trimestre, m.codigo_maquina,
           sum(h.horas_programadas)             AS horas_programadas,
           count(DISTINCT h.referencia_key)     AS referencias_distintas
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, f.trimestre, m.codigo_maquina
)
SELECT
    c.anio, c.trimestre, c.codigo_maquina,
    c.referencias_distintas,
    coalesce(cb.eventos_cambio, 0)                                      AS cambios_de_referencia,
    round(coalesce(cb.horas_cambio, 0), 1)                              AS horas_en_cambios,
    round(cb.horas_cambio / nullif(cb.eventos_cambio, 0), 2)            AS horas_por_cambio,
    round(100 * coalesce(cb.horas_cambio, 0) / c.horas_programadas, 2)  AS pct_del_tiempo,
    -- [PERIODO] mismo trimestre del anio anterior
    lag(round(100 * coalesce(cb.horas_cambio, 0) / c.horas_programadas, 2), 4)
        OVER (PARTITION BY c.codigo_maquina ORDER BY c.anio, c.trimestre)
                                                                        AS pct_mismo_trim_anio_ant
FROM contexto c
LEFT JOIN cambios cb
       ON cb.anio = c.anio AND cb.trimestre = c.trimestre
      AND cb.codigo_maquina = c.codigo_maquina
WHERE c.horas_programadas > 0
ORDER BY c.codigo_maquina, c.anio, c.trimestre;


-- ###########################################################################
--  C10  [VENTANA]
--  PREGUNTA   : Podemos confiar en el dato? Como evoluciona la completitud del
--               diligenciamiento del formato hora a hora?
--  USUARIO    : Coordinador de mantenimiento / Direccion (gobierno del dato)
--  POR QUE    : Es el indicador que explica por que el Rendimiento no es
--               calculable antes de 2023, y la palanca para exigir calidad en
--               la captura. Sin el, cualquier conclusion del tablero es fragil.
-- ###########################################################################
SELECT
    f.anio,
    m.codigo_maquina,
    count(*)                                                            AS turnos,
    round(100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)   / count(*), 1) AS pct_operario,
    round(100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada) / count(*), 1) AS pct_referencia,
    round(100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)          / count(*), 1) AS pct_turno,
    round(100.0 * count(*) FILTER (WHERE h.tiene_estandar)              / count(*), 1) AS pct_estandar,
    round((100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)
         + 100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada)
         + 100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)
         + 100.0 * count(*) FILTER (WHERE h.tiene_estandar))
          / (4 * count(*)), 1)                                          AS indice_completitud,
    -- [VENTANA] mejora frente al anio anterior, en puntos porcentuales
    round((100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)
         + 100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada)
         + 100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)
         + 100.0 * count(*) FILTER (WHERE h.tiene_estandar)) / (4 * count(*))
        - lag((100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)
             + 100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada)
             + 100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)
             + 100.0 * count(*) FILTER (WHERE h.tiene_estandar)) / (4 * count(*)))
              OVER (PARTITION BY m.codigo_maquina ORDER BY f.anio), 1)  AS mejora_pp
FROM dw.hecho_produccion_turno h
JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
GROUP BY f.anio, m.codigo_maquina
ORDER BY m.codigo_maquina, f.anio;


-- ###########################################################################
--  C11  [VENTANA]  -  Drill-down sobre la jerarquia de paros
--  PREGUNTA   : Dentro del ajuste operativo (codigo 05), que causa raiz
--               concreta pesa mas, y quien la atiende?
--  USUARIO    : Supervisor de produccion y mantenimiento
--  DEMUESTRA  : la navegacion de los cuatro niveles de la jerarquia de paros
--               y el uso de la dimension de personal PSEUDONIMIZADA.
-- ###########################################################################
SELECT
    p.area_impacto                                                      AS nivel_1_area,
    p.etiqueta_codigo_paro                                              AS nivel_2_codigo,
    p.nombre_sistema                                                    AS nivel_3_sistema,
    p.nombre_subcodigo                                                  AS nivel_4_causa_raiz,
    a.nombre_area                                                       AS atendido_por,
    count(*)                                                            AS eventos,
    round(sum(hp.horas_paro), 2)                                        AS horas,
    round(avg(hp.horas_paro), 3)                                        AS horas_promedio,
    round(100 * sum(hp.horas_paro) / sum(sum(hp.horas_paro)) OVER (), 2) AS pct_del_codigo,
    -- Cuantos tecnicos distintos (pseudonimizados) intervinieron
    count(DISTINCT hp.personal_key) FILTER (WHERE hp.personal_key > 0)  AS tecnicos_distintos
FROM dw.hecho_paro hp
JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
LEFT JOIN dw.dim_area_involucrada a ON a.area_key = hp.area_key
WHERE p.codigo_paro = '05'
GROUP BY p.area_impacto, p.etiqueta_codigo_paro, p.nombre_sistema,
         p.nombre_subcodigo, a.nombre_area
ORDER BY horas DESC;


-- ###########################################################################
--  C12  -  Utilizacion del calendario (indicador nuevo)
--  PREGUNTA   : Cuanta capacidad instalada estamos dejando sin programar?
--  USUARIO    : Gerencia (decision de contratar un turno vs comprar maquina)
--  POR QUE    : El OEE mide que tan bien usamos el tiempo QUE PROGRAMAMOS.
--               Este indicador mide cuanto tiempo NO programamos, que es una
--               decision comercial, no de mantenimiento. Juntos forman el TEEP.
-- ###########################################################################
WITH calendario AS (
    SELECT
        f.anio,
        m.codigo_maquina,
        sum(h.horas_programadas)                                  AS horas_programadas,
        sum(h.horas_operativas)                                   AS horas_operativas,
        -- Horas de calendario del anio: dias del anio x 24 h por maquina
        (SELECT count(*) FROM dw.dim_fecha d WHERE d.anio = f.anio) * 24.0
                                                                  AS horas_calendario
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, m.codigo_maquina
)
SELECT
    anio,
    codigo_maquina,
    round(horas_calendario)                                       AS horas_calendario,
    round(horas_programadas, 1)                                   AS horas_programadas,
    round(horas_operativas, 1)                                    AS horas_operativas,
    round(100 * horas_programadas / horas_calendario, 1)          AS pct_utilizacion_calendario,
    round(100 * horas_operativas / horas_programadas, 1)          AS pct_disponibilidad,
    -- TEEP = utilizacion del calendario x disponibilidad x rendimiento.
    -- Aqui se muestra su parte medible sin el rendimiento, para no mezclar
    -- anios con y sin cobertura de estandar.
    round(100 * horas_operativas / horas_calendario, 1)           AS pct_teep_parcial
FROM calendario
ORDER BY codigo_maquina, anio;
