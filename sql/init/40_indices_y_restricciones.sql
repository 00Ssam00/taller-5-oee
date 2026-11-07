-- ===========================================================================
--  40_indices_y_restricciones.sql
--
--  JUSTIFICACION DE LA ESTRATEGIA DE INDEXACION
--  --------------------------------------------
--  El patron de consulta de esta solucion NO es OLTP (buscar una fila) sino
--  analitico: agregar millares de filas filtrando por fecha, maquina y codigo
--  de paro. Por eso:
--
--  (1) UN INDICE POR CADA CLAVE FORANEA. En un esquema en estrella el motor
--      ejecuta joins hash o nested-loop dimension -> hecho; sin indice en la FK
--      del hecho, cada drill-down obliga a un Seq Scan completo.
--      PostgreSQL NO crea estos indices automaticamente (a diferencia de la PK).
--
--  (2) INDICES COMPUESTOS CON fecha_key EN PRIMERA POSICION, porque el 100% de
--      las consultas de los tableros filtra por periodo y luego desglosa por
--      maquina o por causa. El orden (fecha, maquina) sirve ademas para los
--      comparativos interanuales y permite un recorrido ordenado que evita el
--      paso de Sort en las funciones de ventana.
--
--  (3) INDICES PARCIALES (clausula WHERE) para los dos filtros mas repetidos
--      del tablero gerencial: paros NO planeados y registros completos. Un
--      indice parcial ocupa una fraccion del total y es el que elige el
--      planificador en esas consultas.
--
--  (4) INDICE BRIN sobre hecho_produccion_hora.instante: esa tabla crece de
--      forma monotona en el tiempo (append-only del simulador/SCADA). BRIN
--      ocupa kilobytes frente a megabytes de un B-tree y es optimo para los
--      filtros de rango $__timeFilter() de Grafana.
--
--  (5) SIN indices sobre las columnas de metricas: nunca se filtra por ellas,
--      solo se agregan. Indexarlas solo encareceria la carga del ETL.
-- ===========================================================================

\echo '>> 40: creando indices'

-- ---------------------------------------------------------------------------
--  dim_fecha
-- ---------------------------------------------------------------------------
CREATE INDEX ix_dim_fecha_anio_mes   ON dw.dim_fecha (anio, mes);
CREATE INDEX ix_dim_fecha_anio_mes_k ON dw.dim_fecha (anio_mes);
CREATE INDEX ix_dim_fecha_fecha      ON dw.dim_fecha (fecha);
-- Solo dias habiles: usado por el KPI de utilizacion del calendario.
CREATE INDEX ix_dim_fecha_habil      ON dw.dim_fecha (fecha_key) WHERE es_dia_habil;

-- ---------------------------------------------------------------------------
--  dim_paro  -  soporta la navegacion de la jerarquia y el Pareto
-- ---------------------------------------------------------------------------
CREATE INDEX ix_dim_paro_codigo    ON dw.dim_paro (codigo_paro);
CREATE INDEX ix_dim_paro_area      ON dw.dim_paro (area_impacto);
CREATE INDEX ix_dim_paro_jerarquia ON dw.dim_paro (area_impacto, codigo_paro, codigo_sistema, codigo_subcodigo);
CREATE INDEX ix_dim_paro_noplan    ON dw.dim_paro (paro_key) WHERE naturaleza_paro = 'No planeado';

-- ---------------------------------------------------------------------------
--  dim_referencia / dim_estandar
-- ---------------------------------------------------------------------------
CREATE INDEX ix_dim_ref_linea   ON dw.dim_referencia (linea_comercial);
-- Indice por expresion: las busquedas de conciliacion son case-insensitive.
CREATE INDEX ix_dim_ref_lower   ON dw.dim_referencia (lower(nombre_referencia));
CREATE INDEX ix_dim_est_par     ON dw.dim_estandar (maquina_key, referencia_key);
-- Resolucion SCD2: "estandar vigente en la fecha del turno".
CREATE INDEX ix_dim_est_vigencia ON dw.dim_estandar (maquina_key, referencia_key, valido_desde, valido_hasta);

-- ---------------------------------------------------------------------------
--  hecho_produccion_turno
-- ---------------------------------------------------------------------------
-- (1) una por FK
CREATE INDEX ix_hpt_fecha      ON dw.hecho_produccion_turno (fecha_key);
CREATE INDEX ix_hpt_maquina    ON dw.hecho_produccion_turno (maquina_key);
CREATE INDEX ix_hpt_turno      ON dw.hecho_produccion_turno (turno_key);
CREATE INDEX ix_hpt_operario   ON dw.hecho_produccion_turno (operario_key);
CREATE INDEX ix_hpt_referencia ON dw.hecho_produccion_turno (referencia_key);
CREATE INDEX ix_hpt_estandar   ON dw.hecho_produccion_turno (estandar_key);
CREATE INDEX ix_hpt_tipoparo   ON dw.hecho_produccion_turno (tipo_paro_key);

-- (2) compuesto para el patron dominante: periodo -> maquina
CREATE INDEX ix_hpt_fecha_maquina ON dw.hecho_produccion_turno (fecha_key, maquina_key)
    INCLUDE (horas_programadas, horas_paro_total, unidades_producidas, pacas_producidas);
--  ^ INCLUDE convierte las consultas de OEE por mes y maquina en index-only
--    scan: el motor no necesita visitar el heap.

-- (3) parcial: el tablero gerencial descarta los registros incompletos
CREATE INDEX ix_hpt_completos ON dw.hecho_produccion_turno (fecha_key, maquina_key)
    WHERE es_registro_completo AND tiene_estandar AND NOT rendimiento_implausible;

-- ---------------------------------------------------------------------------
--  hecho_paro
-- ---------------------------------------------------------------------------
CREATE INDEX ix_hp_fecha      ON dw.hecho_paro (fecha_key);
CREATE INDEX ix_hp_maquina    ON dw.hecho_paro (maquina_key);
CREATE INDEX ix_hp_turno      ON dw.hecho_paro (turno_key);
CREATE INDEX ix_hp_paro       ON dw.hecho_paro (paro_key);
CREATE INDEX ix_hp_operario   ON dw.hecho_paro (operario_key);
CREATE INDEX ix_hp_referencia ON dw.hecho_paro (referencia_key);
CREATE INDEX ix_hp_personal   ON dw.hecho_paro (personal_key);
CREATE INDEX ix_hp_area       ON dw.hecho_paro (area_key);
CREATE INDEX ix_hp_turnofk    ON dw.hecho_paro (produccion_turno_id);

-- Patron del Pareto de causas: periodo -> causa -> maquina
CREATE INDEX ix_hp_fecha_paro_maq ON dw.hecho_paro (fecha_key, paro_key, maquina_key)
    INCLUDE (horas_paro, minutos_paro);

-- Parcial: analisis de confiabilidad (MTBF/MTTR) solo sobre paros no planeados
CREATE INDEX ix_hp_noplaneado ON dw.hecho_paro (maquina_key, fecha_key)
    WHERE NOT es_paro_planeado;

-- ---------------------------------------------------------------------------
--  hecho_produccion_hora  -  tabla de series de tiempo (append-only)
-- ---------------------------------------------------------------------------
-- (4) BRIN para los filtros de rango de Grafana sobre una tabla que crece
--     ordenada en el tiempo.
CREATE INDEX ix_hph_instante_brin ON dw.hecho_produccion_hora
    USING brin (instante) WITH (pages_per_range = 32);
-- B-tree complementario para el panel "estado actual por maquina", que busca
-- el ULTIMO registro de cada linea (ORDER BY instante DESC LIMIT 1).
CREATE INDEX ix_hph_maquina_instante ON dw.hecho_produccion_hora (maquina_key, instante DESC)
    INCLUDE (oee, disponibilidad, rendimiento, calidad, unidades_producidas);
CREATE INDEX ix_hph_fecha   ON dw.hecho_produccion_hora (fecha_key);
CREATE INDEX ix_hph_turno   ON dw.hecho_produccion_hora (turno_key);
CREATE INDEX ix_hph_paro    ON dw.hecho_produccion_hora (paro_key);

-- ---------------------------------------------------------------------------
--  Auditoria
-- ---------------------------------------------------------------------------
CREATE INDEX ix_aud_regla_ejec  ON aud.regla_calidad (ejecucion_id, codigo_regla);
CREATE INDEX ix_aud_conc_ejec   ON aud.conciliacion (ejecucion_id);

-- ---------------------------------------------------------------------------
--  Staging: unico indice util, la deteccion de duplicados exactos.
--  No se indexa mas: staging se trunca y recarga completa en cada ejecucion.
-- ---------------------------------------------------------------------------
CREATE INDEX ix_stg_bd_hash ON stg.base_datos (hash_fila);

\echo '>> 40: OK'
