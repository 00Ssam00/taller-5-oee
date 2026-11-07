-- ===========================================================================
--  30_ddl_hechos.sql
--  Tablas de hechos del modelo en constelacion.
--
--  TRES PROCESOS DE NEGOCIO, TRES GRANOS:
--    1. hecho_produccion_turno   grano = un registro de turno
--    2. hecho_paro               grano = un evento de paro dentro de un turno
--    3. hecho_produccion_hora    grano = una maquina en una hora calendario
-- ===========================================================================

\echo '>> 30: creando hechos'

-- ===========================================================================
--  1. dw.hecho_produccion_turno
--
--  ####  DECLARACION EXPLICITA DEL GRANO  ####
--  "UNA FILA POR CADA REGISTRO DE PRODUCCION DE UN TURNO: la combinacion de
--   fecha, maquina, turno, operario y referencia que el area de mantenimiento
--   transcribe desde un formato 'hora a hora' diligenciado por la operaria."
--
--  Es un hecho TRANSACCIONAL de grano turno. NO es un snapshot periodico:
--  cada fila existe solo si hubo un formato diligenciado.
--
--  DECISION CRITICA SOBRE LA FUENTE
--  --------------------------------
--  La hoja "Base De Datos" tiene 8.208 filas, pero NO todas son registros de
--  turno. El boton "Ingreso subcodigo" del Excel crea FILAS DE CONTINUACION
--  que repiten la cabecera y solo aportan un paro adicional: 3.048 filas
--  llegan sin pacas y sin horas trabajadas.
--  Cargarlas aqui duplicaria los turnos y hundiria artificialmente el OEE.
--  => Solo las 5.160 filas con cabecera completa producen un hecho de turno.
--     Los paros de las filas de continuacion SI se cargan, pero en hecho_paro,
--     asociados al turno al que pertenecen.
--
--  ADITIVIDAD DE LAS METRICAS
--    Aditivas               : horas_programadas, pacas/unidades producidas,
--                             horas_paro_*, unidades_*
--    Semi-aditivas          : ninguna
--    NO aditivas (ratios)   : disponibilidad, rendimiento, calidad, oee.
--                             Se almacenan a nivel de fila SOLO para auditoria
--                             y para Grafana; en Power BI se recalculan como
--                             medidas DAX sobre los sumandos, nunca con
--                             AVERAGE de la columna.
-- ===========================================================================
DROP TABLE IF EXISTS dw.hecho_produccion_turno CASCADE;
CREATE TABLE dw.hecho_produccion_turno (
    produccion_turno_id     bigserial   PRIMARY KEY,

    -- ---- Claves foraneas a las dimensiones (todas NOT NULL) --------------
    fecha_key               integer     NOT NULL REFERENCES dw.dim_fecha(fecha_key),
    maquina_key             smallint    NOT NULL REFERENCES dw.dim_maquina(maquina_key),
    turno_key               smallint    NOT NULL REFERENCES dw.dim_turno(turno_key),
    operario_key            integer     NOT NULL REFERENCES dw.dim_operario(operario_key),
    referencia_key          integer     NOT NULL REFERENCES dw.dim_referencia(referencia_key),
    estandar_key            integer         NULL REFERENCES dw.dim_estandar(estandar_key),
    tipo_paro_key           smallint    NOT NULL REFERENCES dw.dim_tipo_paro_cabecera(tipo_paro_key),

    -- ---- Dimension degenerada --------------------------------------------
    consecutivo_registro    integer     NOT NULL,   -- distingue dos turnos identicos el mismo dia
    fila_origen_excel       integer     NOT NULL,   -- trazabilidad al archivo fuente

    -- ---- Metricas de tiempo (horas) --------------------------------------
    horas_programadas       numeric(10,6) NOT NULL DEFAULT 0, -- "Horas trabajadas" de la fuente
    horas_no_programadas    numeric(10,6)     NULL,           -- tiempo de calendario sin produccion
    horas_paro_total        numeric(10,6) NOT NULL DEFAULT 0,
    horas_paro_planeado     numeric(10,6) NOT NULL DEFAULT 0,
    horas_paro_no_planeado  numeric(10,6) NOT NULL DEFAULT 0,
    horas_operativas        numeric(10,6) NOT NULL DEFAULT 0, -- programadas - paro total
    eventos_paro            smallint     NOT NULL DEFAULT 0,

    -- ---- Metricas de produccion ------------------------------------------
    pacas_producidas        integer      NOT NULL DEFAULT 0,
    unidades_producidas     bigint       NOT NULL DEFAULT 0,  -- pacas * unidades_por_paca
    tasa_ideal_unid_min     numeric(8,3)     NULL,            -- snapshot del estandar vigente
    unidades_teoricas       bigint           NULL,            -- tasa * 60 * horas_programadas
    unidades_posibles       bigint           NULL,            -- tasa * 60 * horas_operativas
    unidades_perdidas_paro  bigint           NULL,            -- tasa * 60 * horas_paro_total

    -- ---- Componentes OEE a nivel de fila (auditoria / Grafana) -----------
    disponibilidad          numeric(7,6)     NULL,   -- acotada a [0,1] por construccion
    -- El rendimiento NO se acota: la fuente contiene turnos que declaran
    -- producir hasta 16 veces el maximo teorico (ver bandera
    -- rendimiento_implausible y la regla de calidad DQ-21). Guardar el valor
    -- real, por absurdo que sea, es lo que permite auditar el problema en vez
    -- de esconderlo; las vistas analiticas son las que lo excluyen.
    rendimiento             numeric(12,6)    NULL,
    calidad_proxy           numeric(7,6)     NULL,
    oee_ad                  numeric(12,6)    NULL,  -- Disponibilidad x Rendimiento
    oee_completo            numeric(12,6)    NULL,  -- x Calidad_proxy

    -- ---- Banderas de calidad de datos ------------------------------------
    es_registro_completo    boolean      NOT NULL DEFAULT true,
    tiene_estandar          boolean      NOT NULL DEFAULT false,
    paro_excede_programado  boolean      NOT NULL DEFAULT false,
    horas_fuera_de_rango    boolean      NOT NULL DEFAULT false,
    turno_imputado          boolean      NOT NULL DEFAULT false,
    operario_no_informado   boolean      NOT NULL DEFAULT false,
    referencia_no_informada boolean      NOT NULL DEFAULT false,
    -- true cuando la produccion declarada supera en mas de 50% el maximo
    -- teorico del estandar: o las pacas estan mal digitadas o el estandar de
    -- ingenieria esta desactualizado. Se excluye del Rendimiento agregado.
    rendimiento_implausible boolean      NOT NULL DEFAULT false,

    -- ---- Linaje -----------------------------------------------------------
    ejecucion_id            bigint       NOT NULL,
    cargado_en              timestamptz  NOT NULL DEFAULT now(),

    -- ---- Reglas de negocio en el DDL -------------------------------------
    CONSTRAINT ck_hpt_horas_prog   CHECK (horas_programadas >= 0 AND horas_programadas <= 24),
    CONSTRAINT ck_hpt_paro_pos     CHECK (horas_paro_total >= 0),
    CONSTRAINT ck_hpt_paro_partes  CHECK (
        abs(horas_paro_total - (horas_paro_planeado + horas_paro_no_planeado)) < 0.0005),
    CONSTRAINT ck_hpt_pacas        CHECK (pacas_producidas >= 0),
    CONSTRAINT ck_hpt_ratios       CHECK (
        (disponibilidad IS NULL OR disponibilidad BETWEEN 0 AND 1) AND
        (rendimiento    IS NULL OR rendimiento    >= 0) AND
        (calidad_proxy  IS NULL OR calidad_proxy  BETWEEN 0 AND 1)),
    CONSTRAINT uq_hpt_registro UNIQUE (fecha_key, maquina_key, turno_key, operario_key,
                                       referencia_key, consecutivo_registro)
);

COMMENT ON TABLE dw.hecho_produccion_turno IS
  'GRANO: una fila por registro de produccion de un turno (fecha x maquina x '
  'turno x operario x referencia x consecutivo). Hecho transaccional. '
  'Excluye las 3.048 filas de continuacion generadas por el boton '
  '"Ingreso subcodigo" del Excel, que no son turnos reales.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_programadas IS
  'Horas que la maquina estuvo asignada al turno ("Horas trabajadas" en la '
  'fuente). Es el DENOMINADOR de la Disponibilidad.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_operativas IS
  'horas_programadas - horas_paro_total. Es el tiempo en que la maquina '
  'realmente pudo producir y el denominador del Rendimiento.';
COMMENT ON COLUMN dw.hecho_produccion_turno.calidad_proxy IS
  'PROXY, NO MEDICION DIRECTA. La fuente no registra unidades defectuosas ni '
  'rechazos, por lo que el componente Calidad del OEE no es medible con el '
  'dato actual. Se estima con el tiempo de reproceso (codigo 11) y de materia '
  'prima defectuosa (codigo 12) convertido a unidades equivalentes. Toda '
  'lectura de oee_completo debe acompanarse de esta advertencia.';
COMMENT ON COLUMN dw.hecho_produccion_turno.consecutivo_registro IS
  'Dimension degenerada. Resuelve el caso real de dos registros con identica '
  'combinacion de fecha, maquina, turno, operario y referencia.';

-- ===========================================================================
--  2. dw.hecho_paro
--
--  ####  DECLARACION EXPLICITA DEL GRANO  ####
--  "UNA FILA POR CADA EVENTO DE PARO REPORTADO: la combinacion de un registro
--   de turno con un codigo de paro y el subcodigo (causa raiz) informado."
--
--  Hecho transaccional. Resultado de DESPIVOTAR los 18 pares de columnas
--  <minutos, horas> de la hoja fuente: 8.208 filas x 18 codigos = 147.744
--  celdas, de las cuales solo se materializan los eventos con minutos > 0.
--
--  Esto es lo que habilita el analisis de causas y el drill-down por
--  jerarquia de paros que el formato ancho del Excel hace imposible.
-- ===========================================================================
DROP TABLE IF EXISTS dw.hecho_paro CASCADE;
CREATE TABLE dw.hecho_paro (
    paro_id                 bigserial   PRIMARY KEY,

    -- ---- Dimensiones conformadas (compartidas con hecho_produccion_turno)
    fecha_key               integer     NOT NULL REFERENCES dw.dim_fecha(fecha_key),
    maquina_key             smallint    NOT NULL REFERENCES dw.dim_maquina(maquina_key),
    turno_key               smallint    NOT NULL REFERENCES dw.dim_turno(turno_key),
    operario_key            integer     NOT NULL REFERENCES dw.dim_operario(operario_key),
    referencia_key          integer     NOT NULL REFERENCES dw.dim_referencia(referencia_key),
    -- ---- Dimensiones propias de este proceso -----------------------------
    paro_key                integer     NOT NULL REFERENCES dw.dim_paro(paro_key),
    area_key                smallint        NULL REFERENCES dw.dim_area_involucrada(area_key),
    personal_key            integer         NULL REFERENCES dw.dim_personal_mantenimiento(personal_key),
    -- ---- Enlace al hecho de turno (drill-across) -------------------------
    produccion_turno_id     bigint          NULL REFERENCES dw.hecho_produccion_turno(produccion_turno_id),

    -- ---- Dimension degenerada --------------------------------------------
    fila_origen_excel       integer     NOT NULL,
    observacion_paro        text,                    -- texto libre de la operaria

    -- ---- Metricas (aditivas) ---------------------------------------------
    minutos_paro            numeric(10,3) NOT NULL,
    -- Escala de 8 decimales para que la suma de 16.482 eventos no acumule
    -- error de redondeo frente al total que calcula el Excel por fila.
    horas_paro              numeric(12,8) NOT NULL,
    unidades_no_producidas  bigint          NULL,    -- horas_paro * tasa_ideal * 60

    -- ---- Banderas ---------------------------------------------------------
    es_paro_planeado        boolean     NOT NULL DEFAULT false,
    proviene_de_continuacion boolean    NOT NULL DEFAULT false,
    subcodigo_imputado      boolean     NOT NULL DEFAULT false,
    minutos_atipicos        boolean     NOT NULL DEFAULT false,

    -- ---- Linaje -----------------------------------------------------------
    ejecucion_id            bigint      NOT NULL,
    cargado_en              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT ck_hp_min    CHECK (minutos_paro > 0),
    CONSTRAINT ck_hp_coher  CHECK (abs(horas_paro - minutos_paro/60.0) < 0.0005)
);

COMMENT ON TABLE dw.hecho_paro IS
  'GRANO: una fila por evento de paro reportado (registro de turno x codigo de '
  'paro x subcodigo). Se obtiene despivotando los 18 pares minutos/horas de la '
  'hoja fuente. Habilita el Pareto de causas y el drill-down de la jerarquia.';
COMMENT ON COLUMN dw.hecho_paro.proviene_de_continuacion IS
  'true cuando el paro venia en una fila de continuacion del boton "Ingreso '
  'subcodigo". El paro es real y se conserva; lo que se descarta de esas filas '
  'es la cabecera duplicada de produccion.';
COMMENT ON COLUMN dw.hecho_paro.unidades_no_producidas IS
  'Traduce el tiempo de paro a producto no envasado usando la tasa ideal del '
  'estandar vigente. Convierte el indicador tecnico en lenguaje de gerencia.';

-- ===========================================================================
--  3. dw.hecho_produccion_hora
--
--  ####  DECLARACION EXPLICITA DEL GRANO  ####
--  "UNA FILA POR MAQUINA Y POR HORA CALENDARIO."
--
--  Es el proceso de MONITOREO near real-time que alimenta Grafana. Reproduce
--  el formato "hora a hora" que las operarias ya diligencian a mano y que hoy
--  se pierde al agregarse por turno antes de llegar al Excel.
--
--  Lo alimenta el servicio `simulador` del docker-compose; cuando la planta
--  conecte PLC/SCADA, este es el punto de entrada natural (ver
--  docs/06_evolucion_plc_scada.md).
-- ===========================================================================
DROP TABLE IF EXISTS dw.hecho_produccion_hora CASCADE;
CREATE TABLE dw.hecho_produccion_hora (
    produccion_hora_id      bigserial   PRIMARY KEY,

    -- ---- Marca de tiempo nativa para las macros de Grafana ---------------
    instante                timestamptz NOT NULL,     -- inicio de la hora
    fecha_key               integer     NOT NULL REFERENCES dw.dim_fecha(fecha_key),
    hora_del_dia            smallint    NOT NULL,

    -- ---- Dimensiones conformadas -----------------------------------------
    maquina_key             smallint    NOT NULL REFERENCES dw.dim_maquina(maquina_key),
    turno_key               smallint    NOT NULL REFERENCES dw.dim_turno(turno_key),
    referencia_key          integer     NOT NULL REFERENCES dw.dim_referencia(referencia_key),
    operario_key            integer     NOT NULL REFERENCES dw.dim_operario(operario_key),
    paro_key                integer         NULL REFERENCES dw.dim_paro(paro_key),

    -- ---- Metricas aditivas de la hora ------------------------------------
    minutos_programados     numeric(6,2) NOT NULL DEFAULT 60,
    minutos_paro            numeric(6,2) NOT NULL DEFAULT 0,
    minutos_operativos      numeric(6,2) NOT NULL DEFAULT 60,
    pacas_producidas        integer      NOT NULL DEFAULT 0,
    unidades_producidas     integer      NOT NULL DEFAULT 0,
    unidades_rechazadas     integer      NOT NULL DEFAULT 0,   -- el SCADA SI podra medirlo
    tasa_ideal_unid_min     numeric(8,3) NOT NULL,
    unidades_posibles       integer      NOT NULL DEFAULT 0,

    -- ---- Componentes OEE de la hora --------------------------------------
    disponibilidad          numeric(7,6) NOT NULL,
    rendimiento             numeric(7,6) NOT NULL,
    calidad                 numeric(7,6) NOT NULL,
    oee                     numeric(7,6) NOT NULL,

    registrado_en           timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT ck_hph_min   CHECK (minutos_paro >= 0 AND minutos_paro <= minutos_programados),
    CONSTRAINT ck_hph_oper  CHECK (abs(minutos_operativos - (minutos_programados - minutos_paro)) < 0.01),
    CONSTRAINT ck_hph_hora  CHECK (hora_del_dia BETWEEN 0 AND 23),
    CONSTRAINT uq_hph       UNIQUE (instante, maquina_key)
);

COMMENT ON TABLE dw.hecho_produccion_hora IS
  'GRANO: una maquina en una hora calendario. Proceso de monitoreo near '
  'real-time que consume Grafana. Lo alimenta el simulador hora a hora y, a '
  'futuro, el PLC/SCADA de las lineas.';
COMMENT ON COLUMN dw.hecho_produccion_hora.instante IS
  'timestamptz del inicio de la hora. Columna de tiempo que usan las macros '
  '$__timeFilter() y $__timeGroup() de Grafana.';
COMMENT ON COLUMN dw.hecho_produccion_hora.unidades_rechazadas IS
  'Este hecho SI contempla el rechazo, que la fuente historica no mide. '
  'Demuestra que el componente Calidad del OEE es medible cuando el dato se '
  'captura en origen.';

-- ===========================================================================
--  aud.*   -   AUDITORIA DEL ETL
-- ===========================================================================
DROP TABLE IF EXISTS aud.ejecucion_etl CASCADE;
CREATE TABLE aud.ejecucion_etl (
    ejecucion_id        bigserial   PRIMARY KEY,
    iniciado_en         timestamptz NOT NULL DEFAULT now(),
    finalizado_en       timestamptz,
    modo                varchar(20) NOT NULL,
    estado              varchar(20) NOT NULL DEFAULT 'EN_CURSO',  -- EN_CURSO|EXITOSO|FALLIDO
    archivo_fuente      text        NOT NULL,
    hash_archivo        char(64)    NOT NULL,
    filas_extraidas     integer,
    filas_cargadas_turno integer,
    filas_cargadas_paro integer,
    duracion_segundos   numeric(10,2),
    version_etl         varchar(20) NOT NULL,
    mensaje             text
);
COMMENT ON TABLE aud.ejecucion_etl IS
  'Una fila por ejecucion del ETL. El hash SHA-256 del archivo fuente permite '
  'demostrar que la carga corresponde exactamente al Excel entregado.';

DROP TABLE IF EXISTS aud.regla_calidad CASCADE;
CREATE TABLE aud.regla_calidad (
    regla_id            bigserial   PRIMARY KEY,
    ejecucion_id        bigint      NOT NULL REFERENCES aud.ejecucion_etl(ejecucion_id) ON DELETE CASCADE,
    codigo_regla        varchar(20) NOT NULL,     -- 'DQ-01'
    dimension_calidad   varchar(20) NOT NULL,     -- Completitud|Exactitud|Consistencia|Unicidad|Validez
    objeto              varchar(60) NOT NULL,
    descripcion         text        NOT NULL,
    accion_aplicada     text        NOT NULL,
    filas_antes         integer,
    filas_afectadas     integer,
    filas_despues       integer,
    severidad           varchar(15) NOT NULL,     -- BLOQUEANTE|ALTA|MEDIA|INFORMATIVA
    resultado           varchar(15) NOT NULL,     -- OK|ADVERTENCIA|FALLO
    evaluado_en         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE aud.regla_calidad IS
  'Bitacora de las reglas de calidad de datos: conteos ANTES y DESPUES de cada '
  'limpieza, con la accion aplicada. Es la evidencia del requisito "documentar '
  'las reglas de limpieza y su efecto".';

DROP TABLE IF EXISTS aud.conciliacion CASCADE;
CREATE TABLE aud.conciliacion (
    conciliacion_id     bigserial   PRIMARY KEY,
    ejecucion_id        bigint      NOT NULL REFERENCES aud.ejecucion_etl(ejecucion_id) ON DELETE CASCADE,
    prueba              varchar(80) NOT NULL,
    alcance             varchar(80) NOT NULL,
    metrica             varchar(40) NOT NULL,
    valor_fuente        numeric(18,6),
    valor_modelo        numeric(18,6),
    diferencia          numeric(18,6) GENERATED ALWAYS AS (valor_modelo - valor_fuente) STORED,
    tolerancia          numeric(18,6) NOT NULL DEFAULT 0.000001,
    resultado           varchar(15) NOT NULL,     -- OK|FALLO
    explicacion         text,
    evaluado_en         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE aud.conciliacion IS
  'Conciliacion exigida por el proyecto: compara los totales del modelo '
  'dimensional contra la fuente Excel (hojas TD_* y Hoja4). Toda diferencia '
  'queda explicada en la columna explicacion.';

\echo '>> 30: OK'
