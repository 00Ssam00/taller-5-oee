-- ===========================================================================
--  60_permisos.sql
--  Modelo de seguridad de acceso a los tableros y tratamiento de datos
--  personales (Ley 1581 de 2012 y Decreto 1377 de 2013, Colombia).
--
--  ESQUEMA DE ACCESO
--  -----------------
--    bi_admin   (superusuario del contenedor)  -> DDL y ejecucion del ETL
--    bi_analista (rol de grupo, NOLOGIN)       -> permisos de lectura analitica
--    bi_lectura  (rol con LOGIN)               -> lo usan Grafana y Power BI
--
--  PRINCIPIO APLICADO: minimo privilegio.
--    - bi_lectura solo puede SELECT sobre dw y aud.
--    - bi_lectura NO tiene USAGE sobre el esquema pii: aunque alguien robe la
--      cadena de conexion del tablero, no puede leer un solo nombre propio.
--    - bi_lectura no puede crear objetos ni escribir en ninguna tabla.
-- ===========================================================================

\echo '>> 60: aplicando permisos'

-- ---------------------------------------------------------------------------
--  Creacion del rol de LOGIN y asignacion de su contrasena desde el entorno.
--
--  NOTA TECNICA: psql NO interpola sus variables dentro de bloques
--  dollar-quoted ($$ ... $$), por lo que la contrasena se aplica con
--  sentencias planas y `\gexec`, no con un bloque DO. La clave llega por la
--  variable de entorno BI_READONLY_PASSWORD que inyecta docker-compose desde
--  `.env`; NUNCA se escribe en el repositorio.
-- ---------------------------------------------------------------------------
\set ro_user `echo "${BI_READONLY_USER:-bi_lectura}"`
\set ro_pass `echo "${BI_READONLY_PASSWORD:-cambieme}"`

-- Crear el rol solo si no existe (idempotente).
SELECT format('CREATE ROLE %I LOGIN', :'ro_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'ro_user')
\gexec

ALTER ROLE :"ro_user" WITH PASSWORD :'ro_pass';
-- Limite de conexiones: evita que un tablero mal configurado agote el pool.
ALTER ROLE :"ro_user" CONNECTION LIMIT 20;
GRANT bi_analista TO :"ro_user";

-- ---------------------------------------------------------------------------
--  1. Revocar lo que PostgreSQL concede por defecto.
--     Sin esto, cualquier rol puede crear objetos en el esquema public.
--     El nombre de la base se resuelve con current_database(): el entrypoint
--     de la imagen no expone POSTGRES_DB como variable de psql.
-- ---------------------------------------------------------------------------
REVOKE ALL ON SCHEMA public FROM PUBLIC;

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database())
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO bi_analista', current_database())
\gexec

-- ---------------------------------------------------------------------------
--  2. Lectura analitica: esquemas dw y aud.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA dw  TO bi_analista;
GRANT USAGE ON SCHEMA aud TO bi_analista;

GRANT SELECT ON ALL TABLES    IN SCHEMA dw  TO bi_analista;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA dw  TO bi_analista;
GRANT SELECT ON ALL TABLES    IN SCHEMA aud TO bi_analista;

-- Objetos futuros (si el ETL agrega una vista, el permiso ya esta dado).
ALTER DEFAULT PRIVILEGES IN SCHEMA dw  GRANT SELECT ON TABLES TO bi_analista;
ALTER DEFAULT PRIVILEGES IN SCHEMA aud GRANT SELECT ON TABLES TO bi_analista;

-- ---------------------------------------------------------------------------
--  3. DATOS PERSONALES: bloqueo explicito del esquema pii.
--     No basta con "no conceder": se revoca de forma expresa para dejar
--     constancia de la decision en el codigo.
-- ---------------------------------------------------------------------------
REVOKE ALL ON SCHEMA pii                  FROM bi_analista, PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA pii    FROM bi_analista, PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA pii    REVOKE ALL ON TABLES FROM bi_analista;

-- ---------------------------------------------------------------------------
--  4. Staging: tampoco se expone. Contiene la columna `operario` en crudo,
--     es decir el nombre real sin pseudonimizar.
-- ---------------------------------------------------------------------------
REVOKE ALL ON SCHEMA stg               FROM bi_analista, PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA stg FROM bi_analista, PUBLIC;

-- ---------------------------------------------------------------------------
--  5. Rol de finalidad unica para la reidentificacion controlada.
--     Destinado al coordinador de mantenimiento, que SI tiene una finalidad
--     legitima para pasar de un pseudonimo a un nombre en un caso puntual.
--     Se crea NOLOGIN: se otorga de forma deliberada y temporal a una cuenta
--     nominal, y la asignacion debe quedar registrada por el responsable del
--     tratamiento. Debe existir ANTES de las politicas RLS que lo invocan.
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE pii_reidentificacion NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pii_reidentificacion')
\gexec

GRANT USAGE  ON SCHEMA pii               TO pii_reidentificacion;
GRANT SELECT ON ALL TABLES IN SCHEMA pii TO pii_reidentificacion;

COMMENT ON ROLE pii_reidentificacion IS
  'Rol de finalidad unica: reidentificar operarios/tecnicos para un caso de '
  'mantenimiento. Se asigna de forma nominal y temporal; no lo usan los '
  'tableros. Toda asignacion debe quedar registrada por el responsable del '
  'tratamiento de datos personales.';

-- ---------------------------------------------------------------------------
--  6. Seguridad a nivel de fila (RLS) sobre las tablas con datos personales.
--     Defensa en profundidad: si por error se concediera USAGE sobre pii,
--     la politica seguiria negando las filas a quien no sea el propietario.
-- ---------------------------------------------------------------------------
ALTER TABLE pii.operario_identidad  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pii.personal_identidad  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pii.operario_identidad  FORCE ROW LEVEL SECURITY;
ALTER TABLE pii.personal_identidad  FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pol_pii_solo_mantenimiento ON pii.operario_identidad;
CREATE POLICY pol_pii_solo_mantenimiento ON pii.operario_identidad
    FOR SELECT
    -- Solo un rol que pertenezca a `pii_reidentificacion` puede ver las filas.
    USING (pg_has_role(current_user, 'pii_reidentificacion', 'MEMBER'));

DROP POLICY IF EXISTS pol_pii_personal ON pii.personal_identidad;
CREATE POLICY pol_pii_personal ON pii.personal_identidad
    FOR SELECT
    USING (pg_has_role(current_user, 'pii_reidentificacion', 'MEMBER'));

-- ---------------------------------------------------------------------------
--  7. Vista segura de reidentificacion (SECURITY INVOKER por defecto).
--     Expone el minimo necesario: pseudonimo -> nombre, nada mas.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW pii.v_reidentificar_operario AS
SELECT o.codigo_operario, o.alias_operario, i.nombre_fuente
FROM pii.operario_identidad i
JOIN dw.dim_operario o ON o.operario_key = i.operario_key;

CREATE OR REPLACE VIEW pii.v_reidentificar_personal AS
SELECT p.codigo_personal, p.alias_personal, i.nombre_fuente
FROM pii.personal_identidad i
JOIN dw.dim_personal_mantenimiento p ON p.personal_key = i.personal_key;

COMMENT ON VIEW pii.v_reidentificar_operario IS
  'Unico camino previsto para pasar de un pseudonimo a un nombre. Sujeto a la '
  'politica RLS: requiere pertenecer al rol pii_reidentificacion.';
COMMENT ON VIEW pii.v_reidentificar_personal IS
  'Equivalente a v_reidentificar_operario para el personal de mantenimiento.';

-- Las vistas se crean DESPUES del GRANT del paso 5, de modo que aquel no las
-- alcanza: hay que concederlas de forma expresa o el rol autorizado no tendria
-- ningun camino para ejercer su finalidad. Ademas necesita leer el pseudonimo
-- en dw para poder emparejarlo, asi que se concede solo sobre esas dos tablas.
GRANT SELECT ON pii.v_reidentificar_operario,
                pii.v_reidentificar_personal  TO pii_reidentificacion;
GRANT USAGE  ON SCHEMA dw                     TO pii_reidentificacion;
GRANT SELECT ON dw.dim_operario,
                dw.dim_personal_mantenimiento TO pii_reidentificacion;

-- Las vistas son SECURITY INVOKER (comportamiento por defecto), de modo que la
-- politica RLS se evalua con los privilegios de QUIEN CONSULTA y no del
-- propietario. Sin esto, la vista seria una puerta trasera a los datos
-- personales para cualquiera que tuviese SELECT sobre ella.

\echo '>> 60: OK'
