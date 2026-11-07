-- ===========================================================================
--  10_ddl_staging.sql
--  Capa de staging: copia FIEL de las hojas del Excel fuente.
--
--  Principio de diseno: en staging NO se limpia nada. Todas las columnas de
--  texto se tipan como TEXT y los numeros como NUMERIC/TEXT segun lleguen,
--  para que ninguna fila se rechace en la extraccion. Asi se puede medir el
--  "antes" de cada regla de limpieza y demostrar su efecto con conteos.
--
--  La hoja "Base De Datos" viene en formato ANCHO (pivotado): 18 pares de
--  columnas <minutos de paro / horas de paro>, uno por codigo de paro. El ETL
--  los despivota hacia dw.hecho_paro.
-- ===========================================================================

\echo '>> 10: creando staging'

-- ---------------------------------------------------------------------------
--  stg.base_datos  <-  hoja "Base De Datos" (encabezado en fila 9)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.base_datos CASCADE;
CREATE TABLE stg.base_datos (
    stg_id                      bigserial PRIMARY KEY,
    fila_origen                 integer NOT NULL,          -- fila fisica en el Excel (trazabilidad)
    fecha                       text,                      -- col 1
    mes_texto                   text,                      -- col 2  'marzo'
    anio_texto                  text,                      -- col 3  '2025' (viene como TEXTO en la fuente)
    maquina                     text,                      -- col 4
    operario                    text,                      -- col 5  DATO PERSONAL
    referencia                  text,                      -- col 6
    unidades_por_minuto_src     text,                      -- col 7  100% vacia en la fuente
    unidad_por_display_src      text,                      -- col 8  REUTILIZADA: contiene TURNO en 687 filas
    display_por_paca_src        text,                      -- col 9  100% vacia en la fuente
    pacas_producidas            text,                      -- col 10
    horas_trabajadas            text,                      -- col 11
    turno                       text,                      -- col 12
    horas_no_trabajadas         text,                      -- col 13 NO es paro: es tiempo no programado
    tipo_paro                   text,                      -- col 14 taxonomia mezclada (dos sistemas de codigos)
    observaciones_paro          text,                      -- col 15
    -- 18 pares <minutos, horas> por codigo de paro -------------------------
    cod01_min text, cod01_sub text, cod01_hrs text,        -- cols 16,17,18
    cod02_min text,                 cod02_hrs text,        -- cols 19,20
    cod03_min text, cod03_sub text, cod03_hrs text,        -- cols 21,22,23
    cod04_min text,                 cod04_hrs text,        -- cols 24,25
    cod05_min text, cod05_sub text, cod05_hrs text,        -- cols 26,27,28
    cod05_area text, cod05_personal text,                  -- cols 29,30  DATO PERSONAL en 30
    cod06_min text,                 cod06_hrs text,        -- cols 31,32
    cod07_min text,                 cod07_hrs text,        -- cols 33,34
    cod08_min text,                 cod08_hrs text,        -- cols 35,36
    cod09_min text,                 cod09_hrs text,        -- cols 37,38
    cod10_min text,                 cod10_hrs text,        -- cols 39,40
    cod11_min text,                 cod11_hrs text,        -- cols 41,42
    cod12_min text,                 cod12_hrs text,        -- cols 43,44
    cod13_min text,                 cod13_hrs text,        -- cols 45,46
    cod14_min text,                 cod14_hrs text,        -- cols 47,48
    cod15_min text,                 cod15_hrs text,        -- cols 49,50
    cod16_min text,                 cod16_hrs text,        -- cols 51,52
    cod17_min text,                 cod17_hrs text,        -- cols 53,54
    cod18_min text,                 cod18_hrs text,        -- cols 55,56
    tiempo_paro_total           text,                      -- col 57
    observaciones               text,                      -- col 58
    -- metadatos de extraccion ----------------------------------------------
    hash_fila                   text NOT NULL,             -- SHA-256 de la fila: detecta duplicados exactos
    ejecucion_id                bigint NOT NULL,
    extraido_en                 timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  stg.base_datos IS
  'Copia cruda de la hoja "Base De Datos" (8.208 filas de datos, encabezado en '
  'la fila 9). Formato ancho: 18 pares minutos/horas por codigo de paro.';
COMMENT ON COLUMN stg.base_datos.unidad_por_display_src IS
  'PROBLEMA DE CALIDAD DETECTADO (regla DQ-04): columna reutilizada. Su '
  'encabezado dice "Unidad por display" pero contiene valores de TURNO en 687 '
  'filas, redundantes con la columna 12. Junto con las columnas 7 y 9, que '
  'estan 100% vacias, hace que la hoja de hechos NO permita convertir pacas a '
  'unidades: esa conversion se toma del catalogo de Tablas Desplegables.';
COMMENT ON COLUMN stg.base_datos.horas_no_trabajadas IS
  'PROBLEMA DE CALIDAD DETECTADO: no es tiempo de paro. Los valores dominantes '
  'son 24 (1.263 filas) y 16 (390 filas), es decir 24 - horas_trabajadas: '
  'representa tiempo de calendario NO programado. No entra al OEE.';
COMMENT ON COLUMN stg.base_datos.anio_texto IS
  'El anio viene almacenado como TEXTO en la fuente, no como numero.';

-- ---------------------------------------------------------------------------
--  stg.base_subcodigos  <-  hoja oculta "Base de datos de Sub codigos"
--  Se extrae por TRAZABILIDAD, pero NO alimenta el modelo dimensional:
--  982 de sus 1.252 filas ya existen en "Base De Datos" y cargarla duplicaria
--  679,2 horas de paro. Las 270 filas restantes no tienen minutos de paro.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.base_subcodigos CASCADE;
CREATE TABLE stg.base_subcodigos (
    stg_id          bigserial PRIMARY KEY,
    fila_origen     integer NOT NULL,
    fecha           text,
    mes_texto       text,
    anio_texto      text,
    maquina         text,
    operario        text,
    referencia      text,
    pacas_producidas text,
    turno           text,
    cod01_min       text,
    cod01_sub       text,
    cod01_hrs       text,
    cod03_min       text,
    cod03_sub       text,
    cod03_hrs       text,
    cod05_min       text,
    cod05_sub       text,
    cod05_hrs       text,
    cod05_area      text,
    cod05_personal  text,
    hash_fila       text NOT NULL,
    ejecucion_id    bigint NOT NULL,
    extraido_en     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE stg.base_subcodigos IS
  'Hoja oculta "Base de datos de Sub codigos" (1.252 filas, oct-2023 a '
  'may-2024). REDUNDANTE: 982 filas ya estan en "Base De Datos". Se conserva '
  'en staging solo para auditoria; NO se carga al modelo dimensional.';

-- ---------------------------------------------------------------------------
--  stg.catalogo_estandar  <-  hoja "Tablas Desplegables", bloques por maquina
--  Es el catalogo maquina x referencia con la TASA IDEAL (unidades/minuto),
--  insumo indispensable para el componente Rendimiento del OEE.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.catalogo_estandar CASCADE;
CREATE TABLE stg.catalogo_estandar (
    stg_id              bigserial PRIMARY KEY,
    fila_origen         integer NOT NULL,
    maquina             text,
    referencia          text,
    numero_colores      text,
    pacas               text,
    display             text,
    unidades_por_paca   text,
    unidades_por_minuto text,
    ejecucion_id        bigint NOT NULL,
    extraido_en         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE stg.catalogo_estandar IS
  'Catalogo maquina x referencia de la hoja "Tablas Desplegables" (135 pares). '
  'Aporta unidades_por_minuto (tasa ideal) y unidades_por_paca, necesarias '
  'para convertir pacas a unidades y para calcular el Rendimiento del OEE.';

-- ---------------------------------------------------------------------------
--  stg.catalogo_codigo_paro  <-  hoja "Tablas Desplegables" (bloque de codigos)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.catalogo_codigo_paro CASCADE;
CREATE TABLE stg.catalogo_codigo_paro (
    stg_id          bigserial PRIMARY KEY,
    area_impacto    text,
    paro_descripcion text,
    clave           text,
    ejecucion_id    bigint NOT NULL,
    extraido_en     timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
--  stg.catalogo_subcodigo  <-  hoja "Tablas Desplegables" (bloques 1.x / 3.x / 5.x)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.catalogo_subcodigo CASCADE;
CREATE TABLE stg.catalogo_subcodigo (
    stg_id              bigserial PRIMARY KEY,
    codigo_paro_padre   text,          -- '01' | '03' | '05'
    subcodigo           text,          -- '1.2.D'
    subcodigo_nombre    text,          -- '1.2.D Retenedores'
    ejecucion_id        bigint NOT NULL,
    extraido_en         timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
--  stg.catalogo_turno / stg.catalogo_operario  <-  listas desplegables
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.catalogo_turno CASCADE;
CREATE TABLE stg.catalogo_turno (
    stg_id       bigserial PRIMARY KEY,
    turno        text,
    ejecucion_id bigint NOT NULL
);

DROP TABLE IF EXISTS stg.catalogo_operario CASCADE;
CREATE TABLE stg.catalogo_operario (
    stg_id       bigserial PRIMARY KEY,
    operario     text,
    ejecucion_id bigint NOT NULL
);

-- ---------------------------------------------------------------------------
--  stg.pivote_excel  <-  hojas TD_* (tablas dinamicas actuales)
--  Se extraen para usarlas como ANCLA DE CONCILIACION: el ETL compara sus
--  cifras contra las que calcula el modelo dimensional.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS stg.pivote_excel CASCADE;
CREATE TABLE stg.pivote_excel (
    stg_id       bigserial PRIMARY KEY,
    hoja         text NOT NULL,
    etiqueta_fila text,
    etiqueta_col  text,
    valor         numeric,
    ejecucion_id bigint NOT NULL
);
COMMENT ON TABLE stg.pivote_excel IS
  'Valores de las tablas dinamicas del Excel (hojas TD_*, Hoja4). Se usan como '
  'ancla de conciliacion: el ETL debe reproducirlos desde el modelo dimensional.';

\echo '>> 10: OK'
