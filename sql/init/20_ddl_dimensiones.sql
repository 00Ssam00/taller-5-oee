-- ===========================================================================
--  20_ddl_dimensiones.sql
--  Dimensiones del modelo dimensional.
--
--  ELECCION DEL ESQUEMA: CONSTELACION (fact constellation / galaxy schema)
--  ----------------------------------------------------------------------
--  Se descarta el copo de nieve (snowflake) porque normalizar las jerarquias
--  de paro y de referencia obligaria a 3-4 joins extra en cada consulta y
--  degradaria la navegacion drill-down en Power BI, sin ganancia de espacio
--  relevante (las dimensiones son de decenas a centenas de filas).
--
--  Se descarta la estrella UNICA porque el negocio tiene procesos con granos
--  distintos e irreconciliables en una sola tabla de hechos:
--     (a) la produccion y el tiempo programado se declaran POR TURNO,
--     (b) los paros ocurren VARIOS POR TURNO y con jerarquia propia,
--     (c) el monitoreo operativo necesita grano HORA.
--  Forzarlos a una sola tabla provocaria duplicacion de las horas trabajadas
--  por cada paro (el error clasico que ya comete el Excel al repetir la
--  cabecera del turno en cada fila de subcodigo).
--
--  Resultado: CONSTELACION con tres tablas de hechos que COMPARTEN las mismas
--  dimensiones conformadas (dim_fecha, dim_maquina, dim_turno, dim_referencia),
--  lo que permite consultas drill-across entre procesos.
-- ===========================================================================

\echo '>> 20: creando dimensiones'

-- ===========================================================================
--  dim_fecha   -   DIMENSION CONSTRUIDA POR NOSOTROS
--  La fuente solo trae fecha, mes en texto espanol y anio en texto. Esta
--  dimension aporta todo lo que el Excel no puede: trimestre, semana ISO,
--  festivos de Colombia (Ley 51 de 1983), dias habiles y claves de periodo
--  para los comparativos interanuales.
--  Grano: un dia calendario.  Rango: 2022-01-01 .. 2026-12-31.
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_fecha CASCADE;
CREATE TABLE dw.dim_fecha (
    fecha_key           integer     PRIMARY KEY,             -- AAAAMMDD (clave inteligente)
    fecha               date        NOT NULL UNIQUE,
    anio                smallint    NOT NULL,
    trimestre           smallint    NOT NULL,
    nombre_trimestre    varchar(8)  NOT NULL,                -- 'T1'
    mes                 smallint    NOT NULL,
    nombre_mes          varchar(12) NOT NULL,                -- 'marzo'
    nombre_mes_corto    varchar(4)  NOT NULL,                -- 'mar'
    anio_mes            integer     NOT NULL,                -- 202503  (ordenable)
    etiqueta_anio_mes   varchar(9)  NOT NULL,                -- '2025-03'
    dia                 smallint    NOT NULL,
    dia_del_anio        smallint    NOT NULL,
    dia_semana_iso      smallint    NOT NULL,                -- 1=lunes .. 7=domingo
    nombre_dia          varchar(12) NOT NULL,
    nombre_dia_corto    varchar(4)  NOT NULL,
    semana_iso          smallint    NOT NULL,
    anio_semana_iso     integer     NOT NULL,                -- 202513
    es_fin_semana       boolean     NOT NULL,
    es_festivo          boolean     NOT NULL,
    nombre_festivo      varchar(60),
    es_dia_habil        boolean     NOT NULL,                -- ni fin de semana ni festivo
    -- Claves de apoyo para inteligencia de tiempo ---------------------------
    fecha_key_anio_ant  integer,                             -- mismo dia del anio anterior
    anio_mes_anio_ant   integer,                             -- mismo mes del anio anterior
    CONSTRAINT ck_dim_fecha_trimestre CHECK (trimestre BETWEEN 1 AND 4),
    CONSTRAINT ck_dim_fecha_mes       CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT ck_dim_fecha_key       CHECK (fecha_key = to_char(fecha,'YYYYMMDD')::integer)
);
COMMENT ON TABLE dw.dim_fecha IS
  'DIMENSION CONSTRUIDA POR EL EQUIPO (requisito del proyecto). Calendario '
  'diario 2022-2026 con jerarquia Anio > Trimestre > Mes > Dia, semana ISO y '
  'festivos colombianos. La fuente Excel no tiene ninguna de estas columnas.';
COMMENT ON COLUMN dw.dim_fecha.fecha_key IS
  'Clave subrogada inteligente AAAAMMDD: legible en depuracion y ordenable, '
  'y evita un join adicional para filtrar por rango de fechas.';
COMMENT ON COLUMN dw.dim_fecha.anio_mes_anio_ant IS
  'Soporta los comparativos 2024 vs 2025 que hoy el Excel arma a mano.';

-- ===========================================================================
--  dim_maquina
--  Grano: una maquina de envasado.  4 filas (Vinilos_1 .. Vinilos_4).
--  factor_produccion proviene de la hoja "Tiempos" del Excel, donde esta
--  escondido en una formula de texto:
--      SI(maquina="Vinilos_1";1,1; SI(maquina="Vinilos_2";1,16; ... 1))
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_maquina CASCADE;
CREATE TABLE dw.dim_maquina (
    maquina_key         smallint    PRIMARY KEY,
    codigo_maquina      varchar(20) NOT NULL UNIQUE,         -- 'Vinilos_1'  (clave de negocio)
    nombre_maquina      varchar(40) NOT NULL,                -- 'Linea Vinilos 1'
    numero_linea        smallint    NOT NULL,
    planta              varchar(30) NOT NULL DEFAULT 'Planta Vinilos y Temperas',
    familia_producto    varchar(30) NOT NULL DEFAULT 'Vinilos y temperas',
    factor_produccion   numeric(5,3) NOT NULL DEFAULT 1.000, -- correccion de capacidad relativa
    grupo_capacidad     varchar(20) NOT NULL,                -- 'Alta' | 'Media' | 'Estandar'
    es_activa           boolean     NOT NULL DEFAULT true,
    CONSTRAINT ck_dim_maquina_factor CHECK (factor_produccion > 0 AND factor_produccion <= 3)
);
COMMENT ON TABLE dw.dim_maquina IS 'Las cuatro lineas de envasado. Grano: una maquina.';
COMMENT ON COLUMN dw.dim_maquina.factor_produccion IS
  'Factor de capacidad relativa recuperado de la formula de la hoja "Tiempos": '
  'V1=1,10  V2=1,16  V3=1,00  V4=1,00. Se usa como respaldo de la tasa ideal '
  'cuando el par maquina-referencia no existe en el catalogo de estandares.';

-- ===========================================================================
--  dim_turno
--  Grano: un turno de trabajo declarado en la fuente.
--  La fuente mezcla 7 etiquetas de turno con y sin sufijo "(Turno N)".
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_turno CASCADE;
CREATE TABLE dw.dim_turno (
    turno_key           smallint    PRIMARY KEY,
    codigo_turno        varchar(30) NOT NULL UNIQUE,         -- 'T1' | 'T2' | 'T3' | 'TE1' ...
    nombre_turno        varchar(40) NOT NULL,                -- 'Turno 1 (06:00-14:00)'
    etiqueta_fuente     varchar(40) NOT NULL,                -- '6am-2pm (Turno 1)'  valor crudo normalizado
    hora_inicio         time,
    hora_fin            time,
    duracion_horas      numeric(4,2),
    tipo_jornada        varchar(20) NOT NULL,                -- 'Ordinario' | 'Extendido' | 'No aplica'
    es_nocturno         boolean     NOT NULL DEFAULT false,
    orden_presentacion  smallint    NOT NULL,
    es_valido           boolean     NOT NULL DEFAULT true,   -- false para 'No aplica' / 'Desconocido'
    CONSTRAINT ck_dim_turno_dur CHECK (duracion_horas IS NULL OR duracion_horas BETWEEN 0 AND 24)
);
COMMENT ON TABLE dw.dim_turno IS
  'Turnos de trabajo. Incluye miembros tecnicos "No aplica" y "Desconocido" '
  'para no perder hechos cuyo turno no fue diligenciado (3.912 filas en la fuente).';

-- ===========================================================================
--  dim_operario   -   PSEUDONIMIZADA
--  Grano: una persona que opera una maquina.
--  TRATAMIENTO DE DATOS PERSONALES (Ley 1581 de 2012, Colombia):
--  esta tabla NO contiene el nombre real. Guarda un codigo derivado por
--  HMAC-SHA256 con una semilla secreta (variable de entorno) y un alias
--  generico. El nombre de la fuente vive unicamente en pii.operario_identidad,
--  esquema sobre el cual el rol de los tableros no tiene privilegios.
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_operario CASCADE;
CREATE TABLE dw.dim_operario (
    operario_key        integer     PRIMARY KEY,
    codigo_operario     varchar(16) NOT NULL UNIQUE,         -- 'OPR-07'  (pseudonimo estable)
    alias_operario      varchar(30) NOT NULL,                -- 'Operario 07'
    rol                 varchar(30) NOT NULL DEFAULT 'Operario de envasado',
    es_identificado     boolean     NOT NULL DEFAULT true,   -- false en 'No aplica' / 'No'
    primera_aparicion   date,
    ultima_aparicion    date,
    turnos_registrados  integer     NOT NULL DEFAULT 0
);
COMMENT ON TABLE dw.dim_operario IS
  'Dimension de operarios PSEUDONIMIZADA. No contiene nombres. El vinculo con '
  'la identidad real esta en pii.operario_identidad, inaccesible para el rol '
  'de lectura de Power BI y Grafana (Ley 1581 de 2012, principio de finalidad).';
-- NOTA: la huella HMAC-SHA256 que vincula el pseudonimo con el nombre real NO
-- vive aqui, sino en pii.operario_identidad. Es la llave de vinculacion y
-- por tanto dato personal: debe quedar tras la politica RLS del esquema pii.
-- En dw solo queda el pseudonimo, que no permite reidentificar por si solo.

-- ===========================================================================
--  dim_personal_mantenimiento   -   PSEUDONIMIZADA
--  Tecnicos que atendieron los paros del codigo 05 (columna "Personal
--  involucrado" de la fuente, 1.767 filas con nombre y apellido completos).
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_personal_mantenimiento CASCADE;
CREATE TABLE dw.dim_personal_mantenimiento (
    personal_key        integer     PRIMARY KEY,
    codigo_personal     varchar(16) NOT NULL UNIQUE,         -- 'TEC-03'
    alias_personal      varchar(30) NOT NULL,                -- 'Tecnico 03'
    area                varchar(40) NOT NULL DEFAULT 'Mantenimiento',
    es_identificado     boolean     NOT NULL DEFAULT true
);
COMMENT ON TABLE dw.dim_personal_mantenimiento IS
  'Tecnicos de mantenimiento, PSEUDONIMIZADOS. La fuente los registra con '
  'nombre y apellidos completos, dato personal que no debe llegar al tablero.';

-- ===========================================================================
--  dim_area_involucrada
--  Area que atendio el paro de ajuste operativo (codigo 05).
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_area_involucrada CASCADE;
CREATE TABLE dw.dim_area_involucrada (
    area_key        smallint    PRIMARY KEY,
    codigo_area     varchar(40) NOT NULL UNIQUE,
    nombre_area     varchar(60) NOT NULL,
    es_area_soporte boolean     NOT NULL DEFAULT false
);

-- ===========================================================================
--  dim_referencia
--  Grano: una referencia comercial de producto envasado.
--  Atributos derivados por el ETL a partir del nombre (la fuente solo trae la
--  cadena de texto, con variantes y erratas):
--     'Parchesitos 22cc (6 col)'  ->  linea='Parchesitos', volumen=22 cc, colores=6
--  JERARQUIA:  Familia > Linea comercial > Referencia
--  JERARQUIA:  Presentacion (volumen) > Referencia
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_referencia CASCADE;
CREATE TABLE dw.dim_referencia (
    referencia_key      integer     PRIMARY KEY,
    codigo_referencia   varchar(60) NOT NULL UNIQUE,         -- nombre normalizado (clave de negocio)
    nombre_referencia   varchar(60) NOT NULL,
    linea_comercial     varchar(30) NOT NULL,                -- 'Parchesitos', 'Kids', 'Klips' ...
    volumen_cc          numeric(6,1),                        -- 15 | 22 | 30 | 70 | 125
    etiqueta_presentacion varchar(20),                       -- '22 cc'
    numero_colores      smallint,                            -- 6 | 7 | 12
    display_por_paca    integer,
    unidades_por_paca   integer,                             -- numero_colores * display_por_paca
    es_no_aplica        boolean     NOT NULL DEFAULT false,
    tiene_estandar      boolean     NOT NULL DEFAULT false,  -- existe en el catalogo de la fuente
    variantes_fuente    text,                                -- erratas unificadas, para auditoria
    CONSTRAINT ck_dim_ref_colores CHECK (numero_colores IS NULL OR numero_colores BETWEEN 1 AND 24)
);
COMMENT ON TABLE dw.dim_referencia IS
  'Referencias de producto. 52 valores distintos en la fuente se consolidan '
  'resolviendo erratas (p. ej. "Alocdor 22cc (6col)" -> "Alocolor 22cc (6 col)", '
  '"Stilo Kids" -> "Estilo Kids"). La columna variantes_fuente deja la pista.';
COMMENT ON COLUMN dw.dim_referencia.unidades_por_paca IS
  'Factor de conversion pacas -> unidades. Indispensable: la fuente mide la '
  'produccion en PACAS, pero el OEE exige unidades comparables entre '
  'referencias de 6 y de 12 colores.';

-- ===========================================================================
--  dim_paro   -   JERARQUIA DE PAROS, DESNORMALIZADA AL GRANO DE SUBCODIGO
--
--  JUSTIFICACION DEL MODELADO DE LA JERARQUIA DE PAROS
--  ---------------------------------------------------
--  La fuente expresa los paros en CUATRO niveles:
--     N1  Area de impacto          'Mantenimiento', 'Produccion', 'Calidad',
--                                  'Almacen de materias primas', 'Paro programado'
--     N2  Codigo de paro (01..18)  'FALLA DEL SISTEMA ELECTROMECANICO...'
--     N3  Sistema de la maquina    '1.2 SISTEMA DE DOSIFICACION'
--     N4  Subcodigo (causa raiz)   '1.2.D Retenedores'
--
--  Solo los codigos 01, 03 y 05 tienen niveles N3/N4: la jerarquia es RAGGED
--  (desbalanceada). Se resuelve con MIEMBROS DE RELLENO explicitos
--  ("Sin subcodigo" / "Sin especificar") en lugar de NULL, porque:
--     (a) Power BI colapsa las ramas con NULL y rompe el drill-down;
--     (b) permite declarar NOT NULL en las claves del hecho y mantener
--         integridad referencial estricta;
--     (c) deja medible la COMPLETITUD del registro: el 61% de los paros de
--         codigo 05 llega como "Sin especificar", hallazgo que se reporta a
--         la gerencia.
--
--  Se elige UNA SOLA dimension desnormalizada al grano mas fino (subcodigo)
--  en vez de copo de nieve (dim_area -> dim_codigo -> dim_sistema ->
--  dim_subcodigo) porque la jerarquia es estrictamente de contencion y la
--  tabla tiene solo decenas de filas: desnormalizar da drill-down nativo en
--  Power BI y Grafana con cero joins adicionales.
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_paro CASCADE;
CREATE TABLE dw.dim_paro (
    paro_key                integer     PRIMARY KEY,
    -- Nivel 1 ---------------------------------------------------------------
    area_impacto            varchar(40) NOT NULL,
    -- Nivel 2 ---------------------------------------------------------------
    codigo_paro             char(2)     NOT NULL,            -- '01' .. '18'
    codigo_paro_numero      smallint    NOT NULL,
    nombre_codigo_paro      varchar(90) NOT NULL,
    etiqueta_codigo_paro    varchar(95) NOT NULL,            -- '[01] Falla del sistema...'
    naturaleza_paro         varchar(20) NOT NULL,            -- 'No planeado' | 'Planeado'
    es_imputable_mantenimiento boolean  NOT NULL DEFAULT false,
    -- Nivel 3 ---------------------------------------------------------------
    --  ATRIBUTO CONFORMADO CONSTRUIDO POR EL EQUIPO: agrupa los subcodigos de
    --  los codigos 01 (falla), 03 (servicios) y 05 (ajuste operativo) en el
    --  SISTEMA FISICO de la maquina al que pertenecen. Es la pieza que permite
    --  preguntar "que sistema de la linea pierde mas tiempo, sin importar si
    --  fue por falla o por ajuste", algo que el Excel no puede responder
    --  porque alli las ramas 1.x y 5.x viven en columnas separadas.
    codigo_sistema          varchar(20) NOT NULL,            -- 'SYS-DOSIF' | 'SYS-NA'
    nombre_sistema          varchar(70) NOT NULL,            -- 'Sistema de dosificacion'
    -- Nivel 4 ---------------------------------------------------------------
    codigo_subcodigo        varchar(12) NOT NULL,            -- '1.2.D' | 'SIN-ESP' | 'N/A'
    nombre_subcodigo        varchar(90) NOT NULL,            -- '1.2.D Retenedores'
    -- Control ---------------------------------------------------------------
    nivel_detalle           smallint    NOT NULL,            -- 2 = solo codigo, 4 = con subcodigo
    admite_subcodigo        boolean     NOT NULL DEFAULT false,
    es_subcodigo_especificado boolean   NOT NULL DEFAULT false,
    orden_presentacion      integer     NOT NULL,
    CONSTRAINT uq_dim_paro UNIQUE (codigo_paro, codigo_subcodigo),
    CONSTRAINT ck_dim_paro_num   CHECK (codigo_paro_numero BETWEEN 1 AND 18),
    CONSTRAINT ck_dim_paro_nivel CHECK (nivel_detalle IN (2,4)),
    CONSTRAINT ck_dim_paro_nat   CHECK (naturaleza_paro IN ('No planeado','Planeado'))
);
COMMENT ON TABLE dw.dim_paro IS
  'Jerarquia de paros desnormalizada al grano de subcodigo: '
  'Area de impacto > Codigo de paro > Sistema de la maquina > Subcodigo. '
  'Jerarquia ragged resuelta con miembros de relleno explicitos.';
COMMENT ON COLUMN dw.dim_paro.naturaleza_paro IS
  'Planeado = codigos 04, 15, 16, 17 (mantenimiento preventivo, cambio de '
  'insumos, aseo, pausa activa) mas el area "Paro programado". Permite calcular '
  'la Disponibilidad en dos variantes, algo que el Excel actual no distingue.';
COMMENT ON COLUMN dw.dim_paro.es_subcodigo_especificado IS
  'false cuando la operaria no diligencio el subcodigo. Alimenta el indicador '
  'de completitud del registro.';

-- ===========================================================================
--  dim_estandar   -   SCD TIPO 2  (bonificacion del proyecto)
--
--  IDENTIFICACION DE LA DIMENSION QUE REQUIERE SCD Y TIPO APLICADO
--  ---------------------------------------------------------------
--  La tasa ideal (unidades/minuto) de cada par maquina x referencia es el
--  denominador del componente Rendimiento del OEE. Esa tasa CAMBIA en el
--  tiempo: cuando mantenimiento interviene una linea, cuando se cambia el
--  roscador o cuando ingenieria reestandariza la referencia.
--
--  Si se sobrescribiera (SCD Tipo 1), el OEE historico de 2022 se recalcularia
--  con el estandar de 2026 y los comparativos interanuales -que son el
--  objetivo principal de la gerencia- quedarian falseados.
--
--  => Se aplica SCD TIPO 2 (versionado con vigencias). Cada cambio de
--     estandar crea una nueva fila con valido_desde/valido_hasta, y el hecho
--     apunta a la version vigente EN LA FECHA DEL TURNO.
--
--  Las otras dimensiones y su tipo:
--     dim_maquina     Tipo 1  (el factor de produccion es una constante tecnica)
--     dim_operario    Tipo 1  (solo cambia el alias; versionar personas
--                              ampliaria el tratamiento de datos personales
--                              sin aportar valor analitico)
--     dim_referencia  Tipo 1 para erratas de nombre + Tipo 2 delegado a
--                             dim_estandar para los atributos que si cambian
--     dim_paro        Tipo 2 conceptual: la fuente evidencia DOS versiones de
--                             la taxonomia (ramas "4.x" antiguas y "5.x"
--                             vigentes). Se mapean a la version vigente y se
--                             deja constancia en docs/02_modelo_dimensional.md.
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_estandar CASCADE;
CREATE TABLE dw.dim_estandar (
    estandar_key        integer     PRIMARY KEY,
    -- Claves de negocio -----------------------------------------------------
    maquina_key         smallint    NOT NULL REFERENCES dw.dim_maquina(maquina_key),
    referencia_key      integer     NOT NULL REFERENCES dw.dim_referencia(referencia_key),
    -- Atributos versionados -------------------------------------------------
    unidades_por_minuto numeric(8,3) NOT NULL,               -- TASA IDEAL
    unidades_por_paca   integer     NOT NULL,
    pacas_meta_hora     numeric(8,3) NOT NULL,               -- (unid/min * 60) / unid_por_paca
    -- Control SCD Tipo 2 ----------------------------------------------------
    version             smallint    NOT NULL DEFAULT 1,
    valido_desde        date        NOT NULL,
    valido_hasta        date        NOT NULL DEFAULT DATE '9999-12-31',
    es_vigente          boolean     NOT NULL DEFAULT true,
    origen_estandar     varchar(40) NOT NULL,                -- 'Catalogo fuente' | 'Inferido' ...
    motivo_cambio       varchar(80),
    CONSTRAINT uq_dim_estandar_version UNIQUE (maquina_key, referencia_key, valido_desde),
    CONSTRAINT ck_dim_estandar_tasa    CHECK (unidades_por_minuto >= 0),
    CONSTRAINT ck_dim_estandar_vig     CHECK (valido_hasta >= valido_desde)
);
COMMENT ON TABLE dw.dim_estandar IS
  'SCD TIPO 2. Estandar de produccion por par maquina x referencia con '
  'vigencias (valido_desde / valido_hasta / es_vigente). Preserva la tasa '
  'ideal historica para que los comparativos interanuales de OEE sean validos.';
COMMENT ON COLUMN dw.dim_estandar.origen_estandar IS
  'Trazabilidad del dato: "Catalogo fuente" cuando el par existe en la hoja '
  '"Tablas Desplegables"; "Inferido por referencia" cuando se tomo la tasa de '
  'la misma referencia en otra maquina ajustada por factor_produccion; '
  '"Sin estandar" cuando no fue posible determinarla (129 turnos).';

-- Solo puede haber UNA version vigente por par maquina x referencia.
CREATE UNIQUE INDEX uq_dim_estandar_vigente
    ON dw.dim_estandar (maquina_key, referencia_key)
    WHERE es_vigente;

-- ===========================================================================
--  dim_tipo_paro_cabecera
--  Columna "Tipo de paro" del registro de turno. La fuente mezcla DOS
--  taxonomias historicas (una con prefijo "[NN]" y otra con "N." en
--  mayusculas), con 19 variantes para ~13 conceptos.
-- ===========================================================================
DROP TABLE IF EXISTS dw.dim_tipo_paro_cabecera CASCADE;
CREATE TABLE dw.dim_tipo_paro_cabecera (
    tipo_paro_key       smallint    PRIMARY KEY,
    codigo_tipo         varchar(20) NOT NULL UNIQUE,
    nombre_tipo         varchar(80) NOT NULL,
    grupo_tipo          varchar(40) NOT NULL,
    taxonomia_origen    varchar(20) NOT NULL,                -- 'Vigente' | 'Historica' | 'N/A'
    variantes_fuente    text
);
COMMENT ON TABLE dw.dim_tipo_paro_cabecera IS
  'Tipo de paro declarado en la cabecera del turno. Consolida 19 variantes de '
  'DOS taxonomias historicas distintas presentes en la misma columna.';

-- ===========================================================================
--  pii.*   -   DATOS PERSONALES, ACCESO RESTRINGIDO
-- ===========================================================================
DROP TABLE IF EXISTS pii.operario_identidad CASCADE;
CREATE TABLE pii.operario_identidad (
    operario_key    integer     PRIMARY KEY REFERENCES dw.dim_operario(operario_key),
    nombre_fuente   varchar(60) NOT NULL,
    hash_identidad  char(64)    NOT NULL,
    registrado_en   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE pii.operario_identidad IS
  'TABLA CON DATOS PERSONALES. Unico lugar donde se almacena el nombre de la '
  'operaria. Finalidad: permitir que Mantenimiento reidentifique un caso '
  'puntual. El rol de lectura de los tableros NO tiene USAGE sobre pii.';

DROP TABLE IF EXISTS pii.personal_identidad CASCADE;
CREATE TABLE pii.personal_identidad (
    personal_key    integer     PRIMARY KEY REFERENCES dw.dim_personal_mantenimiento(personal_key),
    nombre_fuente   varchar(80) NOT NULL,
    hash_identidad  char(64)    NOT NULL,
    registrado_en   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE pii.personal_identidad IS
  'TABLA CON DATOS PERSONALES: nombres completos de los tecnicos de '
  'mantenimiento. Mismo tratamiento restringido que pii.operario_identidad.';

\echo '>> 20: OK'
