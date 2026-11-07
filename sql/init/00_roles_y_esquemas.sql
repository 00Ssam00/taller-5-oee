-- ===========================================================================
--  00_roles_y_esquemas.sql
--  Proyecto: BI-OEE lineas de envasado de vinilos y temperas
--  Motor   : PostgreSQL 17
--
--  Crea la separacion de esquemas y el modelo de seguridad de acceso.
--
--  JUSTIFICACION DE POSTGRESQL FRENTE A MYSQL
--  ------------------------------------------
--  1. Funciones de ventana completas y maduras (RANK, LAG/LEAD, SUM OVER con
--     marcos ROWS/RANGE y FILTER), exigidas por las consultas analiticas del
--     proyecto. MySQL 8 las tiene, pero sin clausula FILTER ni agregados
--     ordenados, lo que obligaria a reescribir los Pareto con CASE anidados.
--  2. GENERATED ... STORED, CHECK sobre expresiones y dominios/ENUM nativos:
--     permiten que las reglas de negocio del OEE queden en el DDL y no solo
--     en el ETL.
--  3. Indices parciales y por expresion (WHERE / lower()), usados para las
--     consultas que filtran solo paros no planeados.
--  4. Grafana trae conector nativo PostgreSQL con soporte de macros de tiempo
--     ($__timeFilter, $__timeGroup) y de variables de tablero; con MySQL el
--     soporte de $__timeGroupAlias es mas limitado.
--  5. Seguridad por columna (GRANT ... (columna)) y REVOKE sobre esquema, que
--     es la base del tratamiento de datos personales de este proyecto.
--  6. Licencia PostgreSQL permisiva y imagen oficial alpine de ~80 MB, util
--     para que el despliegue Docker sea liviano y reproducible.
-- ===========================================================================

\echo '>> 00: creando esquemas y roles'

-- ---------------------------------------------------------------------------
--  ESQUEMAS
-- ---------------------------------------------------------------------------
--  stg : staging. Copia fiel y sin transformar de las hojas del Excel. Sirve
--        para auditar el "antes" de la limpieza y para reproducir el ETL sin
--        volver a abrir el archivo fuente.
--  dw  : data warehouse. Modelo dimensional (dimensiones + hechos) que
--        consumen Power BI y Grafana.
--  pii : datos personales identificables (nombres de operarias y de tecnicos
--        de mantenimiento). Aislado en su propio esquema para poder
--        revocarlo en bloque al rol de lectura de los tableros.
--  aud : auditoria del ETL (ejecuciones, reglas de calidad, conciliacion).
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS pii;
CREATE SCHEMA IF NOT EXISTS aud;

COMMENT ON SCHEMA stg IS
  'Staging: copia cruda de las hojas del Excel fuente, sin transformaciones. '
  'Permite auditar los conteos "antes" de la limpieza.';
COMMENT ON SCHEMA dw IS
  'Data warehouse: modelo dimensional en esquema de constelacion. '
  'Es el unico esquema que consumen Power BI y Grafana.';
COMMENT ON SCHEMA pii IS
  'Datos personales identificables. Acceso restringido: el rol de lectura de '
  'los tableros NO tiene privilegios sobre este esquema (Ley 1581 de 2012).';
COMMENT ON SCHEMA aud IS
  'Auditoria del proceso ETL: ejecuciones, resultados de las reglas de '
  'calidad de datos y conciliacion de totales contra la fuente.';

-- ---------------------------------------------------------------------------
--  ROL DE GRUPO PARA LA LECTURA ANALITICA
-- ---------------------------------------------------------------------------
--  Grafana y Power BI se conectan con un rol de LOGIN (bi_lectura) que hereda
--  sus privilegios de este rol de grupo. Asi se puede agregar un segundo
--  consumidor sin repetir los GRANT.
--
--  El rol con LOGIN y su contrasena se crean en 60_permisos.sql, que es el
--  unico script que lee las variables de entorno: aqui no se escribe ninguna
--  credencial.
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE bi_analista NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_analista')
\gexec

COMMENT ON ROLE bi_analista IS
  'Rol de grupo con privilegios de SOLO LECTURA sobre dw y aud. No tiene '
  'ningun privilegio sobre el esquema pii (datos personales) ni sobre stg.';

\echo '>> 00: OK'
