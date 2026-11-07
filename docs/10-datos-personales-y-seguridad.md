# Tratamiento de datos personales y seguridad de acceso

## 1. Qué datos personales trae la fuente

El Excel contiene datos personales de dos grupos de personas, y conviene decir
exactamente cuáles:

| Dato en la fuente | Columna | Volumen | Naturaleza |
|---|---|---|---|
| Nombre de la operaria o el operario del turno | «Operario» | 34 valores distintos en 5.588 filas | **Dato personal.** En su mayoría nombre de pila, algunos con apellido |
| Nombre del técnico que atendió el paro | «Personal involucrado» (código 05) | 38 valores distintos en 1.767 filas | **Dato personal.** Nombre y apellidos completos |
| Lista nominal de personal | hoja `Tiempos` | 45 nombres | **Dato personal** |

Lo importante no es solo el nombre. Al cruzarlo con el resto de las columnas,
la fuente permite reconstruir **el desempeño individual, el historial de turnos
y la asistencia** de una persona identificada. Esa combinación —no el nombre
aislado— es el riesgo real: convierte una base de producción en una base de
evaluación de personal, sin que nadie lo haya decidido.

### 1.1. Marco legal aplicable

La planta está en Colombia, de modo que rige la **Ley 1581 de 2012** de
protección de datos personales y su **Decreto reglamentario 1377 de 2013**.
Los principios que condicionan el diseño:

- **Finalidad.** Los datos solo pueden tratarse para el fin informado al
  titular. Quien entregó su nombre para un registro de producción no autorizó
  que se use para evaluarlo.
- **Necesidad.** Solo deben tratarse los datos que la finalidad requiera.
- **Acceso restringido.** Los datos no son de acceso libre, ni siquiera dentro
  de la empresa.
- **Seguridad.** El responsable debe adoptar medidas técnicas para impedir
  acceso no autorizado.

---

## 2. La decisión de diseño: medir la línea, no a la persona

**La finalidad declarada del proyecto es medir el desempeño de las máquinas,
no de las personas.** El OEE es un indicador de equipo: se descompone en
disponibilidad, rendimiento y calidad, y ninguno de los tres mejora porque se
señale a un operario.

De esa finalidad se derivan tres consecuencias prácticas:

1. **Ninguna dimensión de persona llega al tablero con nombre.** No porque sea
   difícil, sino porque no hace falta para la finalidad declarada.
2. **El turno sí se analiza; la persona no.** El indicador por turno (consulta
   C07) responde una pregunta legítima de organización del trabajo: si el turno
   de noche rinde distinto, eso es un problema de supervisión, iluminación o
   relevos, no de quién estaba. La consulta lleva una **nota de privacidad
   escrita en el propio SQL** advirtiendo que no debe usarse para identificar
   personas, porque un turno pequeño puede tener un solo operario asignado.
3. **El dato se conserva pseudonimizado, no se destruye.** Si en el futuro la
   empresa quisiera un análisis nominal, tendría que informar a los titulares y
   obtener autorización. El diseño deja esa puerta cerrada, no tapiada, y el
   camino para abrirla es documentado y auditable.

---

## 3. Pseudonimización: cómo se implementa

### 3.1. Lo que llega al almacén

En el momento de construir las dimensiones, cada nombre se sustituye por un
**pseudónimo estable**:

| En la fuente | En `dw.dim_operario` |
|---|---|
| El nombre real | `codigo_operario = 'OPR-003'`, `alias_operario = 'Operario 003'` |

El nombre real se guarda **en una sola tabla de un esquema aparte**,
`pii.operario_identidad`, junto a la huella que lo vincula con el pseudónimo:

```
HMAC-SHA256(nombre_normalizado, semilla_secreta)
```

Decisiones concretas y por qué:

- **HMAC con semilla, no un hash simple.** Un `SHA-256` del nombre es
  trivialmente reversible: hay pocos nombres de pila en uso y cualquiera puede
  precalcular un diccionario. La semilla secreta —que vive en la variable de
  entorno `ETL_SALT_PSEUDONIMO` y **no está en el repositorio**— convierte ese
  ataque en inviable.
- **La huella vive solo en `pii`.** Es la llave de vinculación entre el
  pseudónimo y la persona, luego es un dato personal en sí misma y debe quedar
  tras la política de seguridad a nivel de fila. **En `dw` no existe**: ahí solo
  queda `OPR-003`, que por sí solo no reidentifica a nadie.
- **El pseudónimo es estable entre cargas.** La misma persona recibe siempre el
  mismo código, de modo que el histórico sigue siendo coherente sin necesidad de
  conservar su nombre en el modelo analítico.
- **Los marcadores de ausencia se consolidan.** La fuente usa «No» y «No
  aplica» como marcadores; van al miembro técnico `OPR-000` «Sin informar», y no
  se tratan como si fueran personas.

### 3.2. Separación por esquema

| Esquema | Qué contiene | Quién lo lee |
|---|---|---|
| `dw` | Pseudónimos y alias, sin nombres ni huellas | Grafana y Power BI (`bi_lectura`) |
| `pii` | Los nombres reales y las huellas, con RLS activo | Solo `pii_reidentificacion` |
| `stg` | La zona de aterrizaje, que **sí** tiene el nombre en crudo | Solo `bi_admin` |

`stg` merece la mención explícita: es la copia literal de la fuente y por tanto
contiene los nombres sin pseudonimizar. Por eso se le **revoca el acceso de
forma expresa** al rol de los tableros, igual que a `pii`.

---

## 4. Reidentificación controlada

Negar todo acceso sería cómodo pero irreal: el coordinador de mantenimiento
puede tener una **finalidad legítima** para saber quién atendió una avería
concreta —por ejemplo, preguntarle qué vio—. El diseño no lo prohíbe: lo
canaliza.

- Existe un **rol de finalidad única**, `pii_reidentificacion`, creado
  `NOLOGIN`. No es una cuenta: es una autorización que se concede de forma
  **nominal y temporal** a una cuenta concreta, y cuya asignación debe quedar
  registrada por el responsable del tratamiento.
- El **único camino previsto** son las vistas `pii.v_reidentificar_operario` y
  `pii.v_reidentificar_personal`, que exponen el mínimo necesario: pseudónimo →
  nombre, nada más. No dan acceso al historial de turnos ni al desempeño.
- Las vistas son **`SECURITY INVOKER`** (el comportamiento por defecto), de modo
  que la política de seguridad a nivel de fila se evalúa con los privilegios de
  **quien consulta**, no del propietario. Sin esto, la vista sería una puerta
  trasera para cualquiera con `SELECT` sobre ella.
- **Ningún tablero usa ese rol.** Grafana y Power BI se conectan con
  `bi_lectura`, que no lo tiene.

---

## 5. Seguridad de acceso a los tableros

### 5.1. Mínimo privilegio en la base de datos

| Rol | Para qué | Privilegios |
|---|---|---|
| `bi_admin` | DDL y ejecución del ETL | Superusuario del contenedor. **No lo usa ningún tablero** |
| `bi_analista` | Rol de grupo, `NOLOGIN` | `SELECT` sobre `dw` y `aud`. Concentra los permisos en un sitio |
| `bi_lectura` | **El que usan Grafana y Power BI** | Hereda de `bi_analista`. Nada más |
| `pii_reidentificacion` | Finalidad única, `NOLOGIN` | Las dos vistas de reidentificación |

Medidas concretas:

- **`REVOKE ALL ON SCHEMA public FROM PUBLIC`.** PostgreSQL concede por defecto
  permiso de creación en `public` a cualquier rol; sin esto, el rol del tablero
  podría crear objetos en la base.
- **`REVOKE ALL ON DATABASE ... FROM PUBLIC`**, y `CONNECT` concedido solo al
  rol de grupo.
- **Revocación expresa** de `pii` y `stg`, en lugar de simplemente no
  concederlos: deja constancia de la decisión en el código, que es lo que hace
  auditable un modelo de permisos.
- **`CONNECTION LIMIT 20`** sobre `bi_lectura`: un tablero mal configurado con
  refresco de 10 segundos no puede agotar el conjunto de conexiones.
- **`ALTER DEFAULT PRIVILEGES`**: si mañana el ETL crea una vista nueva en `dw`,
  el permiso ya está dado y nadie tiene que acordarse de concederlo; y si la
  crea en `pii`, sigue revocado por defecto.

### 5.2. Seguridad a nivel de fila como segunda capa

Las dos tablas de `pii` tienen `ENABLE` y **`FORCE ROW LEVEL SECURITY`**, con
una política que solo devuelve filas a quien pertenezca a
`pii_reidentificacion`.

`FORCE` es la parte que importa: sin él, el **propietario de la tabla** se
salta su propia política. Con él, ni el propietario ve las filas si no tiene la
finalidad.

Es defensa en profundidad: si alguien concediera `USAGE` sobre `pii` por error,
la política seguiría negando las filas. **Está demostrado abajo**, no solo
afirmado.

### 5.3. Credenciales fuera del repositorio

Es un requisito explícito del enunciado y se cumple así:

- **Ningún archivo versionado contiene una contraseña ni una cadena de conexión
  con contraseña.** `docker-compose.yml` referencia `${POSTGRES_PASSWORD}` y
  similares.
- Los valores viven en **`.env`, excluido por `.gitignore`**. Se versiona
  **`.env.example`** con los nombres de las variables y comentarios sobre qué
  poner en cada una.
- El **datasource de Grafana** recibe la contraseña por interpolación de la
  variable de entorno en el archivo de provisioning. El YAML versionado no la
  contiene.
- El **proyecto de Power BI** no guarda credenciales: el archivo
  `expressions.tmdl` solo tiene el servidor y el nombre de la base. Power BI
  pide la contraseña al abrir y la guarda en el administrador de credenciales de
  Windows.
- La **semilla de pseudonimización** (`ETL_SALT_PSEUDONIMO`) es también una
  variable de entorno. Es el secreto más sensible del proyecto: quien la tenga
  puede reconstruir el vínculo entre pseudónimo y nombre si además consigue la
  lista de nombres.

### 5.4. Acceso a la interfaz de los tableros

- **Grafana** exige autenticación; el usuario y la contraseña del
  administrador llegan por variables de entorno. En producción habría que
  integrarlo con el directorio de la empresa y usar las carpetas de Grafana
  para que cada perfil vea solo sus tableros.
- **`allowUiUpdates: false`** en el provisioning: nadie puede modificar el
  tablero desde la interfaz. Para cambiarlo hay que editar el JSON y
  versionarlo. Protege la integridad de lo que se publica y evita que el
  repositorio quede desactualizado.
- **El puerto de PostgreSQL se publica en el anfitrión** (55432) para que Power
  BI y DBeaver puedan conectarse desde la máquina virtual. Es una exposición
  deliberada y acotada: el rol que se usa desde fuera es `bi_lectura`, que solo
  puede leer `dw` y `aud`. En producción esa conexión debería ir por la red
  interna o por un túnel, no por la red local.

### 5.5. Advertencia honesta sobre el entorno

Esto es un montaje de desarrollo y conviene no presentarlo como otra cosa:

- Las contraseñas de `.env` son **de desarrollo** y están señaladas como tales.
  En producción deberían venir de un gestor de secretos.
- El tráfico entre Power BI y PostgreSQL **no va cifrado con TLS**. En
  producción habría que exigir `sslmode=require`.
- No hay registro de auditoría de **quién consultó qué**. Si la empresa
  concediera el rol de reidentificación, convendría activar `pgaudit` para
  dejar rastro de cada acceso a `pii`.

---

## 6. Evidencia: lo que está comprobado, no solo afirmado

Ejecutado contra la base recién reconstruida desde cero.

### A · La huella de identidad no existe en el almacén

```
columnas hash_identidad en dw  : 0
columnas hash_identidad en pii : 2
```

### B · Lo que el rol de los tableros sí ve

```sql
SET ROLE bi_lectura;
SELECT codigo_operario, alias_operario, rol, turnos_registrados FROM dw.dim_operario;
```
```
 codigo_operario | alias_operario |         rol          | turnos_registrados
-----------------+----------------+----------------------+--------------------
 OPR-000         | Sin informar   | Sin informar         |               2620
 OPR-003         | Operario 003   | Operario de envasado |                254
```

Sirve para medir —254 turnos registrados— y no identifica a nadie.

### C · Lo que el rol de los tableros no puede hacer

```sql
SELECT * FROM pii.operario_identidad;        -- ERROR: permission denied for schema pii
SELECT * FROM stg.base_datos;                -- ERROR: permission denied for schema stg
SELECT * FROM pii.v_reidentificar_operario;  -- ERROR: permission denied for schema pii
DELETE FROM dw.hecho_paro WHERE false;       -- ERROR: permission denied for table hecho_paro
```

Aunque alguien obtuviera la cadena de conexión del tablero, **no puede leer un
solo nombre propio ni alterar un solo hecho**.

### D · La seguridad a nivel de fila bloquea por sí sola

Se creó un rol con `USAGE` sobre `pii` y `SELECT` sobre la tabla —es decir,
simulando una concesión por error— pero **sin** pertenecer a
`pii_reidentificacion`:

```sql
GRANT USAGE ON SCHEMA pii TO demo_sin_finalidad;
GRANT SELECT ON pii.operario_identidad TO demo_sin_finalidad;
SET ROLE demo_sin_finalidad;
SELECT count(*) FROM pii.operario_identidad;
```
```
 filas_visibles_sin_finalidad
------------------------------
                            0
```

Tiene el permiso y **no ve ninguna de las 43 filas**. Esto es lo que demuestra
que la protección no depende únicamente de haber configurado bien los
privilegios de esquema. (El rol de prueba se eliminó tras la comprobación.)

### E · El rol con finalidad legítima sí puede reidentificar

```sql
SET ROLE pii_reidentificacion;
SELECT count(*) FROM pii.operario_identidad;          -->  43
SELECT codigo_operario, alias_operario, nombre_fuente
  FROM pii.v_reidentificar_operario;
```
```
 codigo_operario | alias_operario | nombre (enmascarado en esta evidencia)
-----------------+----------------+----------------------------------------
 OPR-001         | Operario 001   | A******
 OPR-002         | Operario 002   | A******
```

El mecanismo funciona para quien tiene la finalidad, y solo para quien la tiene.

> Los nombres aparecen enmascarados **en este documento**, no en la base: sería
> incoherente documentar un modelo de protección de datos personales imprimiendo
> los nombres reales en el entregable.

### F · El repositorio no contiene credenciales

`.env` está excluido:

```bash
$ grep -x "\.env" .gitignore
.env
```

Y la búsqueda de valores literales de contraseña en todo lo versionado no
devuelve ninguno:

```bash
$ grep -rEn "(PASSWORD|password)[[:space:]]*[:=][[:space:]]*[\"']?[A-Za-z0-9_]" \
      docker-compose.yml grafana/provisioning/ powerbi/ sql/ etl/ simulador/ \
  | grep -v '\${'
sql/init/60_permisos.sql:38:ALTER ROLE :"ro_user" WITH PASSWORD :'ro_pass';
```

La única coincidencia es `:'ro_pass'`, una **variable de psql** que se resuelve
en tiempo de ejecución desde `BI_READONLY_PASSWORD`, no un valor literal. Todo
lo demás son referencias `${VARIABLE}`.

### G · El repositorio tampoco contiene los nombres reales

Sería incoherente pseudonimizar los nombres en la base de datos y a la vez
publicar en GitHub el archivo que los contiene. El `.xlsm` de origen trae los
**nombres reales de 45 personas**, así que está excluido del control de
versiones:

```bash
$ git check-ignore -v "datos/fuente/Seguimiento Temperas y Vinilos Actividad.xlsm"
.gitignore:92:datos/**/*.xlsm	datos/fuente/Seguimiento Temperas y Vinilos Actividad.xlsm
```

La reproducibilidad no se pierde: `datos/fuente/README.md` **sí** se versiona y
registra el **SHA-256** del libro
(`c7d7eabb…92d5c55`), de modo que quien reponga el archivo puede verificar que
es exactamente el mismo con el que se calcularon las cifras del informe. El ETL
registra además ese hash en `aud.ejecucion_etl` en cada ejecución.

---

## 7. Qué recomendar a la empresa

Más allá de lo implementado, tres cosas que el proyecto no puede resolver por
su cuenta:

1. **Informar a los titulares.** Las operarias y el personal de mantenimiento
   deberían saber que su nombre se registra, para qué y por cuánto tiempo. Es
   una obligación de la Ley 1581 y hoy no consta que se cumpla.
2. **Decidir si el nombre hace falta en el formato.** Si la finalidad es medir
   la máquina, quizá baste con el turno. Recoger menos dato es la medida de
   protección más eficaz que existe, y la más barata.
3. **Fijar una política de retención.** El histórico llega a 2022. Conservar
   nombres indefinidamente sin una finalidad vigente contradice el principio de
   necesidad. Los pseudónimos pueden conservarse sin límite; los nombres, no.
