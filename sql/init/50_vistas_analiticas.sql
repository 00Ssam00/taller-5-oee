-- ===========================================================================
--  50_vistas_analiticas.sql
--
--  Capa semantica en la base de datos. Cumple tres propositos:
--    (a) Grafana consulta vistas, no tablas: si el modelo evoluciona, los
--        paneles no se rompen.
--    (b) Encapsulan la definicion unica del OEE, de modo que Power BI y
--        Grafana no puedan calcularlo distinto.
--    (c) Ninguna vista expone el esquema pii: el rol de lectura solo ve
--        pseudonimos.
-- ===========================================================================

\echo '>> 50: creando vistas analiticas'

-- ===========================================================================
--  v_hecho_turno_detalle
--  Vista plana del hecho de turno con todos sus atributos dimensionales.
--  Es la que importa Power BI cuando se quiere una tabla unica de trabajo y
--  la que usan las consultas ad hoc en DBeaver.
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_hecho_turno_detalle AS
SELECT
    h.produccion_turno_id,
    f.fecha, f.anio, f.trimestre, f.nombre_trimestre, f.mes, f.nombre_mes,
    f.anio_mes, f.etiqueta_anio_mes, f.semana_iso, f.nombre_dia,
    f.es_fin_semana, f.es_festivo, f.es_dia_habil,
    m.codigo_maquina, m.nombre_maquina, m.numero_linea, m.grupo_capacidad,
    t.codigo_turno, t.nombre_turno, t.tipo_jornada, t.es_nocturno,
    o.codigo_operario, o.alias_operario,
    r.codigo_referencia, r.nombre_referencia, r.linea_comercial,
    r.volumen_cc, r.numero_colores, r.unidades_por_paca,
    tp.nombre_tipo            AS tipo_paro_cabecera,
    tp.grupo_tipo             AS grupo_tipo_paro,
    e.unidades_por_minuto     AS estandar_unid_min,
    e.origen_estandar,
    h.horas_programadas, h.horas_no_programadas,
    h.horas_paro_total, h.horas_paro_planeado, h.horas_paro_no_planeado,
    h.horas_operativas, h.eventos_paro,
    h.pacas_producidas, h.unidades_producidas,
    h.tasa_ideal_unid_min, h.unidades_teoricas, h.unidades_posibles,
    h.unidades_perdidas_paro,
    h.disponibilidad, h.rendimiento, h.calidad_proxy, h.oee_ad, h.oee_completo,
    h.es_registro_completo, h.tiene_estandar, h.paro_excede_programado,
    h.turno_imputado, h.operario_no_informado, h.referencia_no_informada
FROM dw.hecho_produccion_turno h
JOIN dw.dim_fecha               f  ON f.fecha_key      = h.fecha_key
JOIN dw.dim_maquina             m  ON m.maquina_key    = h.maquina_key
JOIN dw.dim_turno               t  ON t.turno_key      = h.turno_key
JOIN dw.dim_operario            o  ON o.operario_key   = h.operario_key
JOIN dw.dim_referencia          r  ON r.referencia_key = h.referencia_key
JOIN dw.dim_tipo_paro_cabecera  tp ON tp.tipo_paro_key = h.tipo_paro_key
LEFT JOIN dw.dim_estandar       e  ON e.estandar_key   = h.estandar_key;

COMMENT ON VIEW dw.v_hecho_turno_detalle IS
  'Vista plana del hecho de turno con sus dimensiones. Solo expone '
  'pseudonimos de operario, nunca nombres.';

-- ===========================================================================
--  v_oee_mes_maquina
--  Indicador principal agregado al grano que pide el P-MTO-22
--  (por maquina, mes y anio), con los tres componentes del OEE.
--
--  REGLA DE AGREGACION: el OEE agregado NO es el promedio de los OEE de cada
--  turno. Se recalcula desde los sumandos (suma de horas, suma de unidades),
--  que es la unica forma correcta de agregar un ratio ponderado por tiempo.
--
--  POBLACION: los dos factores del OEE se miden sobre los MISMOS turnos, los
--  que tienen estandar de ingenieria y rendimiento plausible. La columna
--  cobertura_oee dice que fraccion del periodo es esa. La columna
--  disponibilidad, en cambio, se calcula sobre todos los turnos: solo necesita
--  horas, y es la que reproduce el "% Productividad" del Excel.
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_oee_mes_maquina AS
WITH base AS (
    SELECT
        f.anio, f.mes, f.nombre_mes, f.anio_mes, f.etiqueta_anio_mes,
        m.maquina_key, m.codigo_maquina, m.nombre_maquina,
        sum(h.horas_programadas)                              AS horas_programadas,
        sum(h.horas_paro_total)                               AS horas_paro_total,
        sum(h.horas_paro_planeado)                            AS horas_paro_planeado,
        sum(h.horas_paro_no_planeado)                          AS horas_paro_no_planeado,
        sum(h.horas_operativas)                               AS horas_operativas,
        sum(h.pacas_producidas)                               AS pacas_producidas,
        sum(h.unidades_producidas)                            AS unidades_producidas,
        -- Para el Rendimiento solo se consideran los turnos con estandar
        -- conocido Y con produccion plausible. Mezclar los que no tienen
        -- estandar sesgaria el ratio; incluir los implausibles lo destruiria:
        -- un solo turno que declara 16 veces el maximo teorico arrastra el
        -- rendimiento mensual de toda la linea.
        sum(h.unidades_posibles)
            FILTER (WHERE h.tiene_estandar AND NOT h.rendimiento_implausible)
                                                                    AS unidades_posibles,
        sum(h.unidades_producidas)
            FILTER (WHERE h.tiene_estandar AND NOT h.rendimiento_implausible)
                                                                    AS unidades_prod_con_est,
        count(*) FILTER (WHERE h.rendimiento_implausible)           AS turnos_implausibles,
        -- Horas del MISMO subconjunto que el Rendimiento. El OEE multiplica
        -- dos factores, asi que ambos tienen que medir la misma poblacion de
        -- turnos: si la Disponibilidad se toma de todos los turnos y el
        -- Rendimiento solo de los que tienen estandar, el producto no describe
        -- ninguna operacion real. En 2023 eso inflaba el OEE de Vinilos_1 de
        -- 49,7 % a 62,0 %, porque solo el 28 % de sus turnos tiene estandar.
        sum(h.horas_operativas)
            FILTER (WHERE h.tiene_estandar AND NOT h.rendimiento_implausible)
                                                                    AS horas_oper_con_est,
        sum(h.horas_programadas)
            FILTER (WHERE h.tiene_estandar AND NOT h.rendimiento_implausible)
                                                                    AS horas_prog_con_est,
        sum(h.unidades_perdidas_paro)                          AS unidades_perdidas_paro,
        count(*)                                              AS turnos,
        count(*) FILTER (WHERE h.tiene_estandar
                           AND NOT h.rendimiento_implausible)     AS turnos_con_estandar,
        sum(h.eventos_paro)                                   AS eventos_paro
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, f.mes, f.nombre_mes, f.anio_mes, f.etiqueta_anio_mes,
             m.maquina_key, m.codigo_maquina, m.nombre_maquina
)
SELECT
    b.*,
    -- Disponibilidad: equivale al "% Productividad" que reporta hoy el Excel.
    CASE WHEN b.horas_programadas > 0
         THEN round(b.horas_operativas / b.horas_programadas, 6) END  AS disponibilidad,
    -- Variante que no castiga los paros programados (aseo, pausa activa,
    -- mantenimiento preventivo): mide la disponibilidad tecnica real.
    CASE WHEN (b.horas_programadas - b.horas_paro_planeado) > 0
         THEN round((b.horas_programadas - b.horas_paro_total)
                  / (b.horas_programadas - b.horas_paro_planeado), 6) END AS disponibilidad_tecnica,
    CASE WHEN b.unidades_posibles > 0
         THEN round(b.unidades_prod_con_est::numeric / b.unidades_posibles, 6) END AS rendimiento,
    -- Factor de Disponibilidad que entra en el OEE: restringido a los turnos
    -- auditables. Se publica aparte de la columna disponibilidad para que la
    -- diferencia entre ambos quede a la vista.
    CASE WHEN b.horas_prog_con_est > 0
         THEN round(b.horas_oper_con_est / b.horas_prog_con_est, 6) END AS disponibilidad_oee,
    -- OEE auditable, como razon de sumas sobre los turnos auditables.
    CASE WHEN b.horas_prog_con_est > 0 AND b.unidades_posibles > 0
         THEN round((b.horas_oper_con_est / b.horas_prog_con_est)
                  * (b.unidades_prod_con_est::numeric / b.unidades_posibles), 6) END AS oee_ad,
    -- Hay que leer el OEE junto a esta cobertura: dice sobre que fraccion de
    -- los turnos del periodo se calculo.
    CASE WHEN b.turnos > 0
         THEN round(b.turnos_con_estandar::numeric / b.turnos, 6) END AS cobertura_oee,
    CASE WHEN b.horas_programadas > 0
         THEN round(b.horas_paro_no_planeado / b.horas_programadas, 6) END AS tasa_paro_no_planeado,
    CASE WHEN b.turnos > 0
         THEN round(b.turnos_con_estandar::numeric / b.turnos, 6) END    AS cobertura_estandar
FROM base b;

COMMENT ON VIEW dw.v_oee_mes_maquina IS
  'OEE y componentes por maquina, mes y anio: el grano que exige el P-MTO-22. '
  'La columna disponibilidad reproduce exactamente el "% Productividad" del '
  'Excel actual, lo que permite conciliar la solucion contra la fuente.';

-- ===========================================================================
--  v_pareto_paros
--  Analisis de causas con funcion de ventana: horas por causa, participacion
--  y porcentaje acumulado para el corte 80/20.
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_pareto_paros AS
WITH agregado AS (
    SELECT
        f.anio,
        m.codigo_maquina,
        p.area_impacto,
        p.codigo_paro,
        p.etiqueta_codigo_paro,
        p.naturaleza_paro,
        sum(hp.horas_paro) AS horas_paro,
        count(*)           AS eventos
    FROM dw.hecho_paro hp
    JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
    JOIN dw.dim_paro    p ON p.paro_key    = hp.paro_key
    GROUP BY f.anio, m.codigo_maquina, p.area_impacto, p.codigo_paro,
             p.etiqueta_codigo_paro, p.naturaleza_paro
)
SELECT
    a.*,
    round(a.horas_paro / a.eventos, 4)                        AS horas_por_evento,
    -- Participacion de la causa dentro del anio y la maquina
    round(100 * a.horas_paro
            / sum(a.horas_paro) OVER (PARTITION BY a.anio, a.codigo_maquina), 4) AS pct_participacion,
    -- Porcentaje acumulado (Pareto)
    round(100 * sum(a.horas_paro) OVER (
                    PARTITION BY a.anio, a.codigo_maquina
                    ORDER BY a.horas_paro DESC, a.codigo_paro
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / sum(a.horas_paro) OVER (PARTITION BY a.anio, a.codigo_maquina), 4) AS pct_acumulado,
    row_number() OVER (PARTITION BY a.anio, a.codigo_maquina
                       ORDER BY a.horas_paro DESC, a.codigo_paro)                AS ranking
FROM agregado a;

COMMENT ON VIEW dw.v_pareto_paros IS
  'Pareto de causas de paro por anio y maquina, con participacion y '
  'porcentaje acumulado calculados con funciones de ventana. Identifica el '
  '20% de causas que explica el 80% del tiempo perdido.';

-- ===========================================================================
--  v_estado_actual_maquina   (panel "estado actual" de Grafana)
--  Ultima hora registrada por cada linea, con semaforo de OEE.
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_estado_actual_maquina AS
--  RELOJ DE REFERENCIA
--  -------------------
--  La antiguedad del dato NO se mide contra now() sino contra el instante mas
--  reciente que existe en el flujo, tomando el mayor de los dos. Razon:
--    * En produccion, con datos que llegan al ritmo real, el maximo del flujo
--      es anterior a now(), gana now() y el comportamiento es el esperado:
--      "hace cuanto que esta maquina no reporta".
--    * Durante la simulacion acelerada el reloj de produccion corre mas rapido
--      que el reloj de pared. Si se midiera contra now(), todas las lineas
--      apareceran "al dia" y el panel de lineas sin reportar nunca se activaria.
--      Midiendo contra el flujo, una linea que deja de reportar mientras las
--      otras avanzan SI queda detectada, que es el comportamiento que se
--      quiere demostrar.
WITH reloj AS (
    SELECT greatest(now(),
                    coalesce(max(instante), now())) AS referencia
    FROM dw.hecho_produccion_hora
)
SELECT DISTINCT ON (h.maquina_key)
    m.codigo_maquina,
    m.nombre_maquina,
    h.instante,
    round(extract(epoch FROM (reloj.referencia - h.instante))/60.0, 1)
                                     AS minutos_desde_registro,
    t.codigo_turno,
    r.nombre_referencia,
    o.alias_operario,
    coalesce(p.etiqueta_codigo_paro, 'Sin paro en la hora') AS causa_paro_actual,
    h.unidades_producidas,
    h.unidades_rechazadas,
    h.minutos_paro,
    h.minutos_operativos,
    round(h.disponibilidad * 100, 2) AS disponibilidad_pct,
    round(h.rendimiento    * 100, 2) AS rendimiento_pct,
    round(h.calidad        * 100, 2) AS calidad_pct,
    round(h.oee            * 100, 2) AS oee_pct,
    --  Umbrales: 65% es la meta de OEE y 50% el umbral critico que dispara la
    --  alerta de Grafana. Ambos estan justificados en el catalogo de
    --  indicadores: la meta es el promedio que ya alcanzan Vinilos_3 y
    --  Vinilos_4, es decir una meta demostradamente alcanzable con los mismos
    --  equipos, y el umbral critico es el nivel al que una linea deja de
    --  cubrir su costo de operacion.
    CASE WHEN h.oee >= 0.65 THEN 'En meta'
         WHEN h.oee >= 0.50 THEN 'Bajo la meta'
         ELSE 'Critico' END          AS semaforo,
    -- Se considera "en linea" si reporto en los ultimos 90 minutos de reloj
    -- de produccion: hora y media es un turno sin dato, ya es anomalo.
    (reloj.referencia - h.instante) < interval '90 minutes' AS esta_reportando
FROM dw.hecho_produccion_hora h
CROSS JOIN reloj
JOIN dw.dim_maquina    m ON m.maquina_key    = h.maquina_key
JOIN dw.dim_turno      t ON t.turno_key      = h.turno_key
JOIN dw.dim_referencia r ON r.referencia_key = h.referencia_key
JOIN dw.dim_operario   o ON o.operario_key   = h.operario_key
LEFT JOIN dw.dim_paro  p ON p.paro_key       = h.paro_key
ORDER BY h.maquina_key, h.instante DESC;

COMMENT ON VIEW dw.v_estado_actual_maquina IS
  'Estado mas reciente de cada linea para el panel de estado actual de '
  'Grafana. El semaforo usa los umbrales 65% (meta) y 50% (critico). La '
  'antiguedad del dato se mide contra el instante mas reciente del flujo, no '
  'contra now(), para que el panel funcione tambien con el simulador '
  'acelerado.';

-- ===========================================================================
--  v_kpi_hora   (series de tiempo de Grafana)
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_kpi_hora AS
SELECT
    h.instante,
    m.codigo_maquina,
    m.nombre_maquina,
    t.codigo_turno,
    t.nombre_turno,
    r.nombre_referencia,
    r.linea_comercial,
    h.unidades_producidas,
    h.unidades_rechazadas,
    h.pacas_producidas,
    h.minutos_paro,
    h.minutos_operativos,
    h.unidades_posibles,
    h.disponibilidad,
    h.rendimiento,
    h.calidad,
    h.oee,
    round(h.oee * 100, 2)            AS oee_pct,
    round(h.disponibilidad * 100, 2) AS disponibilidad_pct,
    round(h.rendimiento * 100, 2)    AS rendimiento_pct,
    round(h.calidad * 100, 2)        AS calidad_pct,
    coalesce(p.etiqueta_codigo_paro, 'Sin paro') AS causa_paro,
    coalesce(p.area_impacto, 'N/A')              AS area_impacto,
    -- Media movil de 3 horas: suaviza el ruido hora a hora y es la serie
    -- sobre la que se define la alerta, para evitar falsos positivos.
    round(avg(h.oee) OVER (PARTITION BY h.maquina_key ORDER BY h.instante
                           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 6) AS oee_media_movil_3h
FROM dw.hecho_produccion_hora h
JOIN dw.dim_maquina    m ON m.maquina_key    = h.maquina_key
JOIN dw.dim_turno      t ON t.turno_key      = h.turno_key
JOIN dw.dim_referencia r ON r.referencia_key = h.referencia_key
LEFT JOIN dw.dim_paro  p ON p.paro_key       = h.paro_key;

COMMENT ON VIEW dw.v_kpi_hora IS
  'Serie de tiempo hora a hora por maquina para Grafana. Incluye la media '
  'movil de 3 horas del OEE, que es la serie evaluada por la alerta.';

-- ===========================================================================
--  v_confiabilidad_maquina   -   MTBF y MTTR  (indicador nuevo)
--  La fuente permite derivarlos, pero el Excel actual no los calcula.
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_confiabilidad_maquina AS
WITH fallas AS (   -- codigos 01 y 02: falla electromecanica y espera de soporte
    SELECT
        f.anio, f.mes, f.anio_mes,
        m.codigo_maquina,
        count(*)            AS eventos_falla,
        sum(hp.horas_paro)  AS horas_reparacion
    FROM dw.hecho_paro hp
    JOIN dw.dim_fecha   f ON f.fecha_key   = hp.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = hp.maquina_key
    JOIN dw.dim_paro    p ON p.paro_key    = hp.paro_key
    WHERE p.codigo_paro IN ('01','02')
    GROUP BY f.anio, f.mes, f.anio_mes, m.codigo_maquina
),
operacion AS (
    SELECT
        f.anio, f.mes, f.anio_mes,
        m.codigo_maquina,
        sum(h.horas_operativas)  AS horas_operativas,
        sum(h.horas_programadas) AS horas_programadas
    FROM dw.hecho_produccion_turno h
    JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
    JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
    GROUP BY f.anio, f.mes, f.anio_mes, m.codigo_maquina
)
SELECT
    o.anio, o.mes, o.anio_mes, o.codigo_maquina,
    o.horas_programadas,
    o.horas_operativas,
    coalesce(fa.eventos_falla, 0)      AS eventos_falla,
    coalesce(fa.horas_reparacion, 0)   AS horas_reparacion,
    -- MTBF: tiempo medio entre fallas = horas operativas / numero de fallas
    CASE WHEN coalesce(fa.eventos_falla,0) > 0
         THEN round(o.horas_operativas / fa.eventos_falla, 2) END  AS mtbf_horas,
    -- MTTR: tiempo medio de reparacion = horas de reparacion / numero de fallas
    CASE WHEN coalesce(fa.eventos_falla,0) > 0
         THEN round(fa.horas_reparacion / fa.eventos_falla, 3) END AS mttr_horas,
    -- Disponibilidad inherente = MTBF / (MTBF + MTTR)
    CASE WHEN coalesce(fa.eventos_falla,0) > 0 AND fa.horas_reparacion > 0
         THEN round(o.horas_operativas / (o.horas_operativas + fa.horas_reparacion), 6) END
                                                                   AS disponibilidad_inherente
FROM operacion o
LEFT JOIN fallas fa
       ON fa.anio_mes = o.anio_mes AND fa.codigo_maquina = o.codigo_maquina;

COMMENT ON VIEW dw.v_confiabilidad_maquina IS
  'INDICADOR NUEVO (no existe en el Excel): MTBF, MTTR y disponibilidad '
  'inherente por maquina y mes, usando los codigos 01 y 02 como fallas.';

-- ===========================================================================
--  v_calidad_registro   -   gobierno del dato  (indicador nuevo)
-- ===========================================================================
CREATE OR REPLACE VIEW dw.v_calidad_registro AS
SELECT
    f.anio, f.mes, f.anio_mes, f.etiqueta_anio_mes,
    m.codigo_maquina,
    count(*)                                                        AS turnos,
    count(*) FILTER (WHERE NOT h.operario_no_informado)             AS con_operario,
    count(*) FILTER (WHERE NOT h.referencia_no_informada)           AS con_referencia,
    count(*) FILTER (WHERE NOT h.turno_imputado)                    AS con_turno,
    count(*) FILTER (WHERE h.tiene_estandar)                        AS con_estandar,
    round(100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)   / count(*), 2) AS pct_operario,
    round(100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada) / count(*), 2) AS pct_referencia,
    round(100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)          / count(*), 2) AS pct_turno,
    round(100.0 * count(*) FILTER (WHERE h.tiene_estandar)              / count(*), 2) AS pct_estandar,
    -- Indice compuesto de completitud del registro (promedio de las 4 tasas)
    round((  100.0 * count(*) FILTER (WHERE NOT h.operario_no_informado)
           + 100.0 * count(*) FILTER (WHERE NOT h.referencia_no_informada)
           + 100.0 * count(*) FILTER (WHERE NOT h.turno_imputado)
           + 100.0 * count(*) FILTER (WHERE h.tiene_estandar)
          ) / (4 * count(*)), 2)                                    AS indice_completitud
FROM dw.hecho_produccion_turno h
JOIN dw.dim_fecha   f ON f.fecha_key   = h.fecha_key
JOIN dw.dim_maquina m ON m.maquina_key = h.maquina_key
GROUP BY f.anio, f.mes, f.anio_mes, f.etiqueta_anio_mes, m.codigo_maquina;

COMMENT ON VIEW dw.v_calidad_registro IS
  'INDICADOR NUEVO de gobierno del dato: completitud del diligenciamiento del '
  'formato hora a hora. Permite a la gerencia exigir calidad en la captura, '
  'no solo en el resultado.';

\echo '>> 50: OK'
