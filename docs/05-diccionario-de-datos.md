# Diccionario de datos

> **Este documento se genera automaticamente** leyendo el catalogo de
> PostgreSQL (`herramientas/gen_diccionario.py`). Los tipos, las llaves y
> las restricciones son los que la base tiene de verdad, no una
> transcripcion; y las descripciones salen de los `COMMENT` del script
> `sql/init/70_diccionario.sql`, de modo que el diccionario y la base no
> pueden divergir.

Cada descripcion de columna tiene tres partes:

- **La descripcion** de que representa el campo.
- **`ORIGEN:`** de donde sale el dato. `construida` significa que el ETL la
  genera y no existe en la fuente; si viene del Excel, se nombra la columna
  y la hoja exactas.
- **`REGLA:`** la transformacion que se le aplico.

El esquema `dw` tiene **13 tablas** y **187 columnas**, todas documentadas.

## Indice

- [`dw.hecho_produccion_turno`](#dwhechoproduccionturno) — Hecho, 38 columnas
- [`dw.hecho_paro`](#dwhechoparo) — Hecho, 21 columnas
- [`dw.hecho_produccion_hora`](#dwhechoproduccionhora) — Hecho, 22 columnas
- [`dw.dim_fecha`](#dwdimfecha) — Dimension, 23 columnas
- [`dw.dim_maquina`](#dwdimmaquina) — Dimension, 9 columnas
- [`dw.dim_turno`](#dwdimturno) — Dimension, 11 columnas
- [`dw.dim_referencia`](#dwdimreferencia) — Dimension, 12 columnas
- [`dw.dim_estandar`](#dwdimestandar) — Dimension, 12 columnas
- [`dw.dim_paro`](#dwdimparo) — Dimension, 16 columnas
- [`dw.dim_tipo_paro_cabecera`](#dwdimtipoparocabecera) — Dimension, 6 columnas
- [`dw.dim_area_involucrada`](#dwdimareainvolucrada) — Dimension, 4 columnas
- [`dw.dim_operario`](#dwdimoperario) — Dimension, 8 columnas
- [`dw.dim_personal_mantenimiento`](#dwdimpersonalmantenimiento) — Dimension, 5 columnas

---

## `dw.hecho_produccion_turno`

Tabla de hechos de produccion por turno.

**Grano declarado.** **Un registro por turno de produccion de una maquina en una fecha, para una referencia concreta.** Si en el mismo turno la linea cambia de referencia, la fuente genera un registro nuevo, y el consecutivo lo distingue. 5.138 filas.

*Filas cargadas: aproximadamente 5.138.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `produccion_turno_id` | `bigint NOT NULL` | PK | Llave primaria tecnica de la fila. ORIGEN: construida. |
| `fecha_key` | `integer NOT NULL` | FK → `dim_fecha` UQ | Llave a dim_fecha. ORIGEN: columna 'Dia' de la hoja Base De Datos. REGLA: se convierte a entero AAAAMMDD. |
| `maquina_key` | `smallint NOT NULL` | FK → `dim_maquina` UQ | Llave a dim_maquina. ORIGEN: columna 'Maquina'. |
| `turno_key` | `smallint NOT NULL` | FK → `dim_turno` UQ | Llave a dim_turno. ORIGEN: columna 'Turno', con respaldo en la columna 8 ('Unidad por display'), que el formulario reutilizo para guardar el turno. REGLA: si la fuente no trae turno se asigna el miembro de relleno y se marca turno_imputado; ocurre en 2.409 de 5.138 turnos. |
| `operario_key` | `integer NOT NULL` | FK → `dim_operario` UQ | Llave a dim_operario. ORIGEN: columna 'Operario'. REGLA: pseudonimizado. |
| `referencia_key` | `integer NOT NULL` | FK → `dim_referencia` UQ | Llave a dim_referencia. ORIGEN: columna 'Referencia'. |
| `estandar_key` | `integer` | FK → `dim_estandar` | Llave a la version VIGENTE del estandar en dim_estandar. ORIGEN: construida. REGLA: resolucion en cascada de tres niveles: catalogo exacto del par maquina-referencia; si no existe, estandar de otra linea ajustado por el factor de produccion; si tampoco, 'sin estandar'. |
| `tipo_paro_key` | `smallint NOT NULL` | FK → `dim_tipo_paro_cabecera` | Llave a dim_tipo_paro_cabecera. ORIGEN: columna 'Tipo de paro'. |
| `consecutivo_registro` | `integer NOT NULL` | UQ | Numero de registro del turno cuando hay varios para la misma fecha, maquina y turno. ORIGEN: construida. REGLA: forma parte del grano; la fuente permite varios registros por turno si cambia la referencia. |
| `fila_origen_excel` | `integer NOT NULL` |  | Numero de fila en la hoja 'Base De Datos' del Excel (la fila 10 es la primera con datos). ORIGEN: construida. REGLA: trazabilidad: permite volver a la celda exacta del Excel ante cualquier duda. |
| `horas_programadas` | `numeric(10,6) NOT NULL` |  | Horas que la planta programo para producir en el turno. ORIGEN: columna 'Horas trabajadas'. REGLA: se carga tal cual; es el denominador de la Disponibilidad y la base de toda la conciliacion contra el Excel. *(Valor por defecto: `0`.)* |
| `horas_no_programadas` | `numeric(10,6)` |  | Horas de calendario sin produccion declaradas por la fuente. ORIGEN: columna 'Horas no trabajadas'. REGLA: ATENCION, NO ES TIEMPO DE PARO. Su suma (41.519,85 h) supera las horas trabajadas y 1.263 filas traen un 24 fijo: es el complemento del dia, no una perdida. Se carga aparte y NO entra al OEE; incluirla seria el error de interpretacion mas facil de cometer con esta fuente. |
| `horas_paro_total` | `numeric(10,6) NOT NULL` |  | Horas totales de paro del turno. ORIGEN: reconstruida sumando los 18 pares de columnas de paro. REGLA: NO se copia la columna 'Tiempo de paro' del Excel; se recalcula desde el detalle y despues se CONCILIA contra ella. Coincidir demuestra que el despivote no perdio ni duplico un minuto. *(Valor por defecto: `0`.)* |
| `horas_paro_planeado` | `numeric(10,6) NOT NULL` |  | Horas de paro de naturaleza planeada. ORIGEN: derivada. REGLA: suma de los paros cuyos codigos son 04, 08, 15, 16, 17 o 18. *(Valor por defecto: `0`.)* |
| `horas_paro_no_planeado` | `numeric(10,6) NOT NULL` |  | Horas de paro EVITABLE. ORIGEN: derivada. REGLA: horas_paro_total menos horas_paro_planeado. Es la cifra sobre la que la gerencia puede actuar. *(Valor por defecto: `0`.)* |
| `horas_operativas` | `numeric(10,6) NOT NULL` |  | Horas en que la linea estuvo efectivamente produciendo. ORIGEN: derivada. REGLA: horas_programadas menos horas_paro_total, acotada en cero. *(Valor por defecto: `0`.)* |
| `eventos_paro` | `smallint NOT NULL` |  | Numero de eventos de paro del turno. ORIGEN: derivada. REGLA: conteo de pares de columnas con minutos mayores que cero. *(Valor por defecto: `0`.)* |
| `pacas_producidas` | `integer NOT NULL` |  | Pacas producidas en el turno. ORIGEN: columna 'Pacas producidas'. REGLA: se carga tal cual; es la unidad en que registra el operario. *(Valor por defecto: `0`.)* |
| `unidades_producidas` | `bigint NOT NULL` |  | Produccion convertida a unidades comparables. ORIGEN: derivada. REGLA: pacas_producidas por unidades_por_paca de la referencia. Sin esta conversion no se pueden comparar referencias de 6 y de 12 colores, ni calcular Rendimiento. *(Valor por defecto: `0`.)* |
| `tasa_ideal_unid_min` | `numeric(8,3)` |  | Tasa ideal del estandar vigente aplicado. ORIGEN: dim_estandar. REGLA: se copia al hecho para congelar el estandar que regia en ese momento; si el estandar cambia luego, el indicador historico no se altera. |
| `unidades_teoricas` | `bigint` |  | Unidades que el estandar permitiria en el tiempo PROGRAMADO. ORIGEN: derivada. REGLA: tasa por 60 por horas_programadas. Es la capacidad nominal del turno. |
| `unidades_posibles` | `bigint` |  | Unidades que el estandar permitiria en el tiempo OPERATIVO. ORIGEN: derivada. REGLA: tasa por 60 por horas_operativas. Es el denominador del Rendimiento: compara contra lo que se pudo hacer con la maquina andando, no con la capacidad nominal, para no contar dos veces la perdida por paro. |
| `unidades_perdidas_paro` | `bigint` |  | Unidades que se dejaron de producir por los paros. ORIGEN: derivada. REGLA: tasa por 60 por horas_paro_total. Traduce el tiempo perdido al lenguaje del negocio. |
| `disponibilidad` | `numeric(7,6)` |  | Primer componente del OEE. ORIGEN: derivada. REGLA: horas_operativas / horas_programadas. REPRODUCE EXACTAMENTE el '% Productividad' que el Excel calcula hoy, verificado a seis decimales contra las tablas dinamicas. Al agregarla se usan TODOS los turnos, porque solo necesita horas; el factor de disponibilidad que entra en el OEE se restringe en cambio a los turnos con estandar, para medir la misma poblacion que el Rendimiento (ver la vista v_oee_mes_maquina, columna disponibilidad_oee). |
| `rendimiento` | `numeric(12,6)` |  | Segundo componente del OEE. ORIGEN: derivada. REGLA: unidades_producidas / unidades_posibles. NULL si no hay estandar: nunca se inventa un valor. El Excel no lo calcula. |
| `calidad_proxy` | `numeric(7,6)` |  | Tercer componente del OEE, como PROXY declarado. ORIGEN: derivada. REGLA: la fuente NO registra unidades defectuosas, asi que la perdida se estima con el tiempo de reproceso (codigo 11) convertido a unidades. Es una COTA INFERIOR: el OEE real no puede ser mejor que este. Es la principal limitacion del modelo y esta declarada, no disimulada. |
| `oee_ad` | `numeric(12,6)` |  | OEE auditable del turno: disponibilidad * rendimiento. ORIGEN: derivada. REGLA: es la version que se reporta, porque sus dos componentes se miden con el dato de la fuente sin estimar nada. NO AGREGAR ESTA COLUMNA: es un ratio no aditivo y existe solo para auditar fila a fila. El OEE de un periodo se recalcula como razon de sumas sobre los turnos con tiene_estandar y sin rendimiento_implausible; promediarla, aunque sea ponderando por horas, da otro numero. |
| `oee_completo` | `numeric(12,6)` |  | OEE con los tres componentes, usando el proxy de Calidad. ORIGEN: derivada. REGLA: se publica junto al auditable para que se vea cuanto pesa la parte estimada. |
| `es_registro_completo` | `boolean NOT NULL` |  | Verdadero si el formato se diligencio completo. ORIGEN: derivada. REGLA: exige operario, referencia y turno informados y estandar disponible. *(Valor por defecto: `true`.)* |
| `tiene_estandar` | `boolean NOT NULL` |  | Verdadero si existe estandar para el par maquina-referencia. ORIGEN: derivada. REGLA: si es falso, el Rendimiento y el OEE quedan en NULL. *(Valor por defecto: `false`.)* |
| `paro_excede_programado` | `boolean NOT NULL` |  | Verdadero si el paro declarado supera las horas trabajadas. ORIGEN: derivada. REGLA: bandera de calidad; 9 turnos lo cumplen, el peor con 15,63 h de paro en un turno de 8 h. Es imposible fisicamente, de modo que uno de los dos datos esta mal. *(Valor por defecto: `false`.)* |
| `horas_fuera_de_rango` | `boolean NOT NULL` |  | Verdadero si las horas trabajadas no son plausibles. ORIGEN: derivada. REGLA: bandera de calidad; una fila declara 32 h en un dia. *(Valor por defecto: `false`.)* |
| `turno_imputado` | `boolean NOT NULL` |  | Verdadero si el turno se asigno porque la fuente no lo traia. ORIGEN: derivada. REGLA: hace visible el dato imputado para que nadie lo confunda con dato real. *(Valor por defecto: `false`.)* |
| `operario_no_informado` | `boolean NOT NULL` |  | Verdadero si la fuente no registro el operario. ORIGEN: derivada. *(Valor por defecto: `false`.)* |
| `referencia_no_informada` | `boolean NOT NULL` |  | Verdadero si la fuente no registro la referencia. ORIGEN: derivada. *(Valor por defecto: `false`.)* |
| `rendimiento_implausible` | `boolean NOT NULL` |  | Verdadero si el rendimiento supera el 150% del maximo teorico. ORIGEN: derivada. REGLA: hallazgo real de la carga: el caso extremo declara un rendimiento del 1.561%, es decir 16 veces el maximo del estandar. No es una linea excepcional, es un dato erroneo. Se CONSERVA el valor para poder auditarlo, pero se excluye del indicador agregado y del indice parcial. *(Valor por defecto: `false`.)* |
| `ejecucion_id` | `bigint NOT NULL` |  | Identificador de la ejecucion del ETL que cargo la fila. ORIGEN: construida. REGLA: permite auditar y revertir una carga concreta. |
| `cargado_en` | `timestamp with time zone NOT NULL` |  | Marca de tiempo de la carga. ORIGEN: construida. REGLA: default now(). *(Valor por defecto: `now()`.)* |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_hpt_horas_prog`: `CHECK (((horas_programadas >= (0)::numeric) AND (horas_programadas <= (24)::numeric)))`
- `ck_hpt_pacas`: `CHECK ((pacas_producidas >= 0))`
- `ck_hpt_paro_partes`: `CHECK ((abs((horas_paro_total - (horas_paro_planeado + horas_paro_no_planeado))) < 0.0005))`
- `ck_hpt_paro_pos`: `CHECK ((horas_paro_total >= (0)::numeric))`
- `ck_hpt_ratios`: `CHECK ((((disponibilidad IS NULL) OR ((disponibilidad >= (0)::numeric) AND (disponibilidad <= (1)::numeric))) AND ((rendimiento IS NULL) OR (rendimiento >= (0)::numeric)) AND ((calidad_proxy IS NULL) OR ((calidad_proxy >= (0)::numeric) AND (calidad_proxy <= (1)::numeric)))))`

---

## `dw.hecho_paro`

Tabla de hechos de eventos de paro.

**Grano declarado.** **Un registro por evento de paro de un codigo concreto dentro de un turno de una maquina.** Es el resultado de despivotar los 18 pares de columnas `<minutos, horas>` que el Excel tiene en horizontal. 16.482 filas.

*Filas cargadas: aproximadamente 16.482.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `paro_id` | `bigint NOT NULL` | PK | Llave primaria tecnica de la fila. ORIGEN: construida. |
| `fecha_key` | `integer NOT NULL` | FK → `dim_fecha` | Llave a dim_fecha. ORIGEN: columna 'Dia'. |
| `maquina_key` | `smallint NOT NULL` | FK → `dim_maquina` | Llave a dim_maquina. ORIGEN: columna 'Maquina'. |
| `turno_key` | `smallint NOT NULL` | FK → `dim_turno` | Llave a dim_turno. ORIGEN: columna 'Turno'. |
| `operario_key` | `integer NOT NULL` | FK → `dim_operario` | Llave a dim_operario. ORIGEN: columna 'Operario'. REGLA: pseudonimizado. |
| `referencia_key` | `integer NOT NULL` | FK → `dim_referencia` | Llave a dim_referencia. ORIGEN: columna 'Referencia'. |
| `paro_key` | `integer NOT NULL` | FK → `dim_paro` | Llave a dim_paro, es decir la causa del paro con sus cuatro niveles. ORIGEN: posicion del par de columnas mas la columna de subcodigo correspondiente. REGLA: si el subcodigo no viene especificado se asigna el miembro de relleno y se marca subcodigo_imputado. |
| `area_key` | `smallint` | FK → `dim_area_involucrada` | Llave a dim_area_involucrada. ORIGEN: columna 'Area involucrada'. |
| `personal_key` | `integer` | FK → `dim_personal_mantenimiento` | Llave a dim_personal_mantenimiento. ORIGEN: columna 'Personal de mantenimiento'. REGLA: pseudonimizado. |
| `produccion_turno_id` | `bigint` | FK → `hecho_produccion_turno` | Llave al turno de produccion al que pertenece el paro; NULL si no se pudo vincular. ORIGEN: construida. REGLA: 3.028 filas de la fuente son CONTINUACIONES generadas por el boton 'Ingreso subcodigo' y no traen pacas ni horas. Se vinculan a su cabecera en cascada de tres niveles: por fecha, maquina, operario, referencia y turno; luego sin turno; luego solo por fecha y maquina. Quedan 903 filas sin vincular, que suman 1,917 h, el 0,02% del tiempo de paro. |
| `fila_origen_excel` | `integer NOT NULL` |  | Numero de fila en la hoja 'Base De Datos' del Excel (la fila 10 es la primera con datos). ORIGEN: construida. REGLA: trazabilidad: permite volver a la celda exacta del Excel ante cualquier duda. |
| `observacion_paro` | `text` |  | Observacion libre escrita por mantenimiento. ORIGEN: columna 'Observacion del paro'. REGLA: se carga sin modificar; es texto libre y no se usa para clasificar, solo para consultar el caso concreto. |
| `minutos_paro` | `numeric(10,3) NOT NULL` |  | Duracion del paro en minutos, tal como la registra la fuente. ORIGEN: columna de minutos del par correspondiente al codigo. REGLA: se conserva el valor original, incluidos los decimales raros (219,6 y 160,5), para no perder trazabilidad. |
| `horas_paro` | `numeric(12,8) NOT NULL` |  | Duracion del paro en horas. ORIGEN: derivada. REGLA: minutos / 60, con ocho decimales para que la suma de 16.482 eventos no acumule error de redondeo frente al total que calcula el Excel. |
| `unidades_no_producidas` | `bigint` |  | Unidades que se dejaron de producir por este paro. ORIGEN: derivada. REGLA: tasa ideal por los minutos del paro. |
| `es_paro_planeado` | `boolean NOT NULL` |  | Verdadero si el codigo es de naturaleza planeada. ORIGEN: derivada de dim_paro. REGLA: se copia al hecho para que los filtros del tablero no tengan que pasar por la dimension. *(Valor por defecto: `false`.)* |
| `proviene_de_continuacion` | `boolean NOT NULL` |  | Verdadero si la fila venia de una continuacion del boton 'Ingreso subcodigo'. ORIGEN: derivada. REGLA: hace visible el artefacto del formulario de captura. *(Valor por defecto: `false`.)* |
| `subcodigo_imputado` | `boolean NOT NULL` |  | Verdadero si la causa raiz no venia especificada. ORIGEN: derivada. REGLA: solo se evalua en los codigos 01, 03 y 05, los unicos con subcodigos; 107 de 3.691 eventos (2,9%) carecen de causa raiz utilizable. *(Valor por defecto: `false`.)* |
| `minutos_atipicos` | `boolean NOT NULL` |  | Verdadero si la duracion supera las 8 horas. ORIGEN: derivada. REGLA: bandera de calidad; 3 eventos, el mayor de 900 minutos en el codigo 10. *(Valor por defecto: `false`.)* |
| `ejecucion_id` | `bigint NOT NULL` |  | Identificador de la ejecucion del ETL que cargo la fila. ORIGEN: construida. REGLA: permite auditar y revertir una carga concreta. |
| `cargado_en` | `timestamp with time zone NOT NULL` |  | Marca de tiempo de la carga. ORIGEN: construida. REGLA: default now(). *(Valor por defecto: `now()`.)* |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_hp_coher`: `CHECK ((abs((horas_paro - (minutos_paro / 60.0))) < 0.0005))`
- `ck_hp_min`: `CHECK ((minutos_paro > (0)::numeric))`

---

## `dw.hecho_produccion_hora`

Tabla de hechos de telemetria horaria.

**Grano declarado.** **Un registro por hora de reloj y maquina.** Es el grano que entregaria un historiador de PLC/SCADA. Hoy lo alimenta el simulador; el ETL del Excel no escribe aqui porque la fuente historica no tiene grano horario.

*Filas cargadas: aproximadamente 1.056.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `produccion_hora_id` | `bigint NOT NULL` | PK | Llave primaria tecnica. ORIGEN: construida. |
| `instante` | `timestamp with time zone NOT NULL` | UQ | Marca de tiempo del inicio de la hora. ORIGEN: construida por el simulador. REGLA: timestamptz nativo, para que funcionen las macros $__timeFilter y $__timeGroup de Grafana. |
| `fecha_key` | `integer NOT NULL` | FK → `dim_fecha` | Llave a dim_fecha. ORIGEN: derivada de instante. |
| `hora_del_dia` | `smallint NOT NULL` |  | Hora del dia, 0 a 23. ORIGEN: derivada de instante. |
| `maquina_key` | `smallint NOT NULL` | FK → `dim_maquina` UQ | Llave a dim_maquina. ORIGEN: construida. |
| `turno_key` | `smallint NOT NULL` | FK → `dim_turno` | Llave a dim_turno. ORIGEN: derivada de la hora del dia. |
| `referencia_key` | `integer NOT NULL` | FK → `dim_referencia` | Llave a dim_referencia. ORIGEN: construida. REGLA: el simulador usa la referencia que cada linea corre con mas frecuencia en el historico. |
| `operario_key` | `integer NOT NULL` | FK → `dim_operario` | Llave a dim_operario. ORIGEN: construida. REGLA: el simulador usa el miembro 'Sin informar': no inventa personas reales. |
| `paro_key` | `integer` | FK → `dim_paro` | Llave a dim_paro; NULL si la hora no tuvo paro. ORIGEN: construida. REGLA: la causa se muestrea de la distribucion REAL de dw.hecho_paro ponderada por horas perdidas, de modo que el Pareto del tablero operativo se parece al historico. |
| `minutos_programados` | `numeric(6,2) NOT NULL` |  | Minutos programados de la hora, normalmente 60. ORIGEN: construida. *(Valor por defecto: `60`.)* |
| `minutos_paro` | `numeric(6,2) NOT NULL` |  | Minutos de paro de la hora. ORIGEN: construida. REGLA: proceso de Poisson calibrado para que la disponibilidad promedio converja a la que la maquina mostro en 2024. *(Valor por defecto: `0`.)* |
| `minutos_operativos` | `numeric(6,2) NOT NULL` |  | Minutos efectivos de produccion. ORIGEN: derivada. *(Valor por defecto: `60`.)* |
| `pacas_producidas` | `integer NOT NULL` |  | Pacas producidas en la hora. ORIGEN: derivada. *(Valor por defecto: `0`.)* |
| `unidades_producidas` | `integer NOT NULL` |  | Unidades producidas en la hora. ORIGEN: construida. *(Valor por defecto: `0`.)* |
| `unidades_rechazadas` | `integer NOT NULL` |  | Unidades rechazadas en la hora. ORIGEN: construida. REGLA: esta columna NO tiene equivalente en el Excel, porque la fuente no mide defectos. Existe aqui porque un historiador de PLC SI puede medirlo, y con ella el componente Calidad del OEE deja de ser un proxy. *(Valor por defecto: `0`.)* |
| `tasa_ideal_unid_min` | `numeric(8,3) NOT NULL` |  | Tasa ideal aplicada. ORIGEN: dim_estandar. |
| `unidades_posibles` | `integer NOT NULL` |  | Unidades posibles en el tiempo operativo. ORIGEN: derivada. *(Valor por defecto: `0`.)* |
| `disponibilidad` | `numeric(7,6) NOT NULL` |  | Disponibilidad de la hora. ORIGEN: derivada. |
| `rendimiento` | `numeric(7,6) NOT NULL` |  | Rendimiento de la hora. ORIGEN: derivada. |
| `calidad` | `numeric(7,6) NOT NULL` |  | Calidad de la hora. ORIGEN: derivada. REGLA: aqui si es Calidad MEDIDA, no proxy, porque existen unidades rechazadas. |
| `oee` | `numeric(7,6) NOT NULL` |  | OEE de la hora, con los tres componentes. ORIGEN: derivada. |
| `registrado_en` | `timestamp with time zone NOT NULL` |  | Marca de tiempo de la insercion. ORIGEN: construida. REGLA: distinta de instante; permite medir la latencia entre el momento productivo y su registro. *(Valor por defecto: `now()`.)* |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_hph_hora`: `CHECK (((hora_del_dia >= 0) AND (hora_del_dia <= 23)))`
- `ck_hph_min`: `CHECK (((minutos_paro >= (0)::numeric) AND (minutos_paro <= minutos_programados)))`
- `ck_hph_oper`: `CHECK ((abs((minutos_operativos - (minutos_programados - minutos_paro))) < 0.01))`

---

## `dw.dim_fecha`

Dimension de calendario CONSTRUIDA POR EL EQUIPO. No existe en la fuente.

*Filas cargadas: aproximadamente 1.826.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `fecha_key` | `integer NOT NULL` | PK | Llave surrogada con formato AAAAMMDD, legible a simple vista. ORIGEN: construida. REGLA: entero en lugar de fecha para que los indices y los JOIN sean mas compactos, y para poder leer la llave sin consultar la dimension. |
| `fecha` | `date NOT NULL` | UQ | Fecha del calendario. ORIGEN: construida. REGLA: columna marcada como fecha del modelo en Power BI; es la que usan las funciones de inteligencia de tiempo de DAX. |
| `anio` | `smallint NOT NULL` |  | Ano del calendario. ORIGEN: construida. |
| `trimestre` | `smallint NOT NULL` |  | Numero de trimestre, 1 a 4. ORIGEN: construida. |
| `nombre_trimestre` | `character varying(8) NOT NULL` |  | Trimestre como texto, por ejemplo 'T1'. ORIGEN: construida. |
| `mes` | `smallint NOT NULL` |  | Numero de mes, 1 a 12. ORIGEN: construida. REGLA: ordena a nombre_mes, para que los meses no salgan en orden alfabetico. |
| `nombre_mes` | `character varying(12) NOT NULL` |  | Nombre del mes en espanol. ORIGEN: construida. REGLA: generado en el ETL y no con to_char, para no depender de la configuracion regional del servidor. |
| `nombre_mes_corto` | `character varying(4) NOT NULL` |  | Abreviatura del mes, por ejemplo 'ene'. ORIGEN: construida. |
| `anio_mes` | `integer NOT NULL` |  | Periodo como entero AAAAMM. ORIGEN: construida. REGLA: sirve para ordenar y para las funciones de ventana que comparan periodos. |
| `etiqueta_anio_mes` | `character varying(9) NOT NULL` |  | Periodo legible, por ejemplo '2024-03'. ORIGEN: construida. |
| `dia` | `smallint NOT NULL` |  | Dia del mes. ORIGEN: construida. |
| `dia_del_anio` | `smallint NOT NULL` |  | Dia del ano, 1 a 366. ORIGEN: construida. |
| `dia_semana_iso` | `smallint NOT NULL` |  | Dia de la semana ISO: 1 lunes a 7 domingo. ORIGEN: construida. REGLA: se usa el estandar ISO y no el de PostgreSQL (0 domingo) para que la semana empiece en lunes, como en la planta. |
| `nombre_dia` | `character varying(12) NOT NULL` |  | Nombre del dia de la semana en espanol. ORIGEN: construida. |
| `nombre_dia_corto` | `character varying(4) NOT NULL` |  | Abreviatura del dia. ORIGEN: construida. |
| `semana_iso` | `smallint NOT NULL` |  | Numero de semana ISO. ORIGEN: construida. |
| `anio_semana_iso` | `integer NOT NULL` |  | Ano de la semana ISO. ORIGEN: construida. REGLA: puede diferir de anio en la primera y la ultima semana del ano; se guarda aparte para no partir semanas al agregar. |
| `es_fin_semana` | `boolean NOT NULL` |  | Verdadero en sabado y domingo. ORIGEN: construida. |
| `es_festivo` | `boolean NOT NULL` |  | Verdadero si es festivo en Colombia. ORIGEN: construida. REGLA: festivos fijos, mas los calculados desde el Domingo de Pascua con el algoritmo de Butcher, mas los trasladables al lunes siguiente segun la Ley 51 de 1983 (Ley Emiliani). |
| `nombre_festivo` | `character varying(60)` |  | Nombre del festivo; NULL si no es festivo. ORIGEN: construida. |
| `es_dia_habil` | `boolean NOT NULL` |  | Verdadero si no es fin de semana ni festivo. ORIGEN: construida. REGLA: permite separar la produccion de dia habil de la de festivo, que tiene costo de mano de obra distinto. |
| `fecha_key_anio_ant` | `integer` |  | fecha_key del mismo dia del ano anterior. ORIGEN: construida. REGLA: precalculada para que los comparativos interanuales en SQL sean un JOIN y no un calculo de fechas en cada consulta. |
| `anio_mes_anio_ant` | `integer` |  | anio_mes del mismo mes del ano anterior. ORIGEN: construida. REGLA: igual que la anterior, para comparativos mensuales. |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_fecha_key`: `CHECK ((fecha_key = (to_char((fecha)::timestamp with time zone, 'YYYYMMDD'::text))::integer))`
- `ck_dim_fecha_mes`: `CHECK (((mes >= 1) AND (mes <= 12)))`
- `ck_dim_fecha_trimestre`: `CHECK (((trimestre >= 1) AND (trimestre <= 4)))`

---

## `dw.dim_maquina`

Dimension de las cuatro lineas de envasado.

*Filas cargadas: aproximadamente 4.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `maquina_key` | `smallint NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_maquina` | `character varying(20) NOT NULL` | UQ | Codigo de la linea tal como lo escribe la fuente: Vinilos_1 a Vinilos_4. ORIGEN: columna 'Maquina' de la hoja Base De Datos. REGLA: se conserva el codigo original para poder conciliar contra el Excel. |
| `nombre_maquina` | `character varying(40) NOT NULL` |  | Nombre legible de la linea. ORIGEN: construida. |
| `numero_linea` | `smallint NOT NULL` |  | Numero de linea, 1 a 4. ORIGEN: construida. REGLA: extraido del codigo; ordena la presentacion. |
| `planta` | `character varying(30) NOT NULL` |  | Planta donde esta la linea. ORIGEN: construida. REGLA: valor unico por ahora; la columna existe para que el modelo admita una segunda planta sin rediseno. *(Valor por defecto: `'Planta Vinilos y Temperas'::character varying`.)* |
| `familia_producto` | `character varying(30) NOT NULL` |  | Familia de producto que envasa la linea. ORIGEN: construida. *(Valor por defecto: `'Vinilos y temperas'::character varying`.)* |
| `factor_produccion` | `numeric(5,3) NOT NULL` |  | Multiplicador de capacidad de la linea respecto de la de referencia: V1 1,100, V2 1,160, V3 y V4 1,000. ORIGEN: estaba ESCONDIDO dentro de una formula de texto de la hoja 'Tiempos', no en ninguna celda de datos. REGLA: se extrajo leyendo la formula; permite inferir el estandar de una linea a partir del de otra cuando el catalogo no trae el par maquina-referencia. *(Valor por defecto: `1.000`.)* |
| `grupo_capacidad` | `character varying(20) NOT NULL` |  | Agrupacion por capacidad relativa. ORIGEN: construida. REGLA: derivada del factor de produccion; agrupa lineas comparables entre si. |
| `es_activa` | `boolean NOT NULL` |  | Verdadero si la linea esta en operacion. ORIGEN: construida. *(Valor por defecto: `true`.)* |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_maquina_factor`: `CHECK (((factor_produccion > (0)::numeric) AND (factor_produccion <= (3)::numeric)))`

---

## `dw.dim_turno`

Dimension de turnos de trabajo.

*Filas cargadas: aproximadamente 8.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `turno_key` | `smallint NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_turno` | `character varying(30) NOT NULL` | UQ | Codigo corto del turno: T1, T2, T3, TE1, TE2, TE3, NA, DESC. ORIGEN: construida. |
| `nombre_turno` | `character varying(40) NOT NULL` |  | Nombre del turno con su horario. ORIGEN: columna 'Turno' de la hoja Base De Datos. REGLA: la fuente escribe el turno de varias formas ('6am-2pm', '6am-2pm (Turno 1)', 'Turno 1'); se resuelven todas al mismo miembro. |
| `etiqueta_fuente` | `character varying(40) NOT NULL` |  | Forma en que la fuente escribe el turno. ORIGEN: idem. REGLA: se conserva para auditar la resolucion de variantes. |
| `hora_inicio` | `time without time zone` |  | Hora de inicio del turno. ORIGEN: derivada del nombre. |
| `hora_fin` | `time without time zone` |  | Hora de fin del turno. ORIGEN: derivada del nombre. |
| `duracion_horas` | `numeric(4,2)` |  | Duracion nominal del turno en horas. ORIGEN: derivada. REGLA: sirve para detectar registros cuyas horas trabajadas exceden la duracion del turno. |
| `tipo_jornada` | `character varying(20) NOT NULL` |  | 'Ordinario', 'Extendido' o 'No aplica'. ORIGEN: construida. REGLA: separa los turnos de 8 horas de las jornadas extendidas, que tienen un patron de paros distinto. |
| `es_nocturno` | `boolean NOT NULL` |  | Verdadero en el turno de noche. ORIGEN: construida. REGLA: permite comprobar si el turno nocturno rinde distinto, que es una pregunta recurrente de produccion. *(Valor por defecto: `false`.)* |
| `orden_presentacion` | `smallint NOT NULL` |  | Orden cronologico de presentacion. ORIGEN: construida. |
| `es_valido` | `boolean NOT NULL` |  | Falso en los miembros de relleno 'No aplica' y 'Descanso'. ORIGEN: construida. *(Valor por defecto: `true`.)* |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_turno_dur`: `CHECK (((duracion_horas IS NULL) OR ((duracion_horas >= (0)::numeric) AND (duracion_horas <= (24)::numeric))))`

---

## `dw.dim_referencia`

Dimension de productos envasados, depurada de erratas de digitacion.

*Filas cargadas: aproximadamente 63.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `referencia_key` | `integer NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_referencia` | `character varying(60) NOT NULL` | UQ | Codigo normalizado de la referencia. ORIGEN: construida. REGLA: nombre sin tildes, en mayusculas y sin espacios; es la clave con que se consolidan las variantes de escritura. |
| `nombre_referencia` | `character varying(60) NOT NULL` |  | Nombre de la referencia, depurado. ORIGEN: columna 'Referencia' de la hoja Base De Datos. REGLA: la fuente trae 52 valores distintos con erratas de digitacion; se corrigieron tres confusiones de nombre ('Alocdor' por 'Alocolor', 'Stilo Kids' por 'Estilo Kids', 'Klips 15cc (12col)' por su forma con espacio) y se consolidaron en 63 miembros limpios. |
| `linea_comercial` | `character varying(30) NOT NULL` |  | Linea comercial del producto. ORIGEN: derivada del nombre. REGLA: se extrae con expresion regular el patron '<Linea> <volumen>cc (<n> col)'. |
| `volumen_cc` | `numeric(6,1)` |  | Volumen del envase en centimetros cubicos. ORIGEN: derivada del nombre de la referencia. REGLA: idem. |
| `etiqueta_presentacion` | `character varying(20)` |  | Presentacion legible, por ejemplo '22 cc, 6 colores'. ORIGEN: construida. |
| `numero_colores` | `smallint` |  | Numero de colores de la presentacion. ORIGEN: derivada del nombre, y confirmada con la columna '# colores' de la hoja Tablas Desplegables. REGLA: determina cuantas unidades caben en una paca, asi que es imprescindible para comparar produccion entre referencias. |
| `display_por_paca` | `integer` |  | Displays que contiene una paca. ORIGEN: columna 'Display' de la hoja Tablas Desplegables. |
| `unidades_por_paca` | `integer` |  | Unidades que contiene una paca. ORIGEN: columna 'Unidades * paca' de la hoja Tablas Desplegables. REGLA: es el factor que convierte las pacas del registro en unidades comparables. En la hoja de hechos este dato era inservible: las columnas 7 y 9 estan 100% vacias y la 8 se reutilizo para guardar el turno. |
| `es_no_aplica` | `boolean NOT NULL` |  | Verdadero en el miembro de relleno. ORIGEN: construida. *(Valor por defecto: `false`.)* |
| `tiene_estandar` | `boolean NOT NULL` |  | Verdadero si existe estandar de ingenieria para la referencia. ORIGEN: construida. *(Valor por defecto: `false`.)* |
| `variantes_fuente` | `text` |  | Lista de las variantes de escritura que la fuente usaba para esta referencia. ORIGEN: construida. REGLA: se conserva para poder auditar la consolidacion y demostrar que no se perdio ningun valor. |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_ref_colores`: `CHECK (((numero_colores IS NULL) OR ((numero_colores >= 1) AND (numero_colores <= 24))))`

---

## `dw.dim_estandar`

Dimension de estandares de ingenieria por par maquina-referencia, con historia SCD Tipo 2.

*Filas cargadas: aproximadamente 137.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `estandar_key` | `integer NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `maquina_key` | `smallint NOT NULL` | FK → `dim_maquina` UQ | Llave a dim_maquina. ORIGEN: construida. REGLA: el estandar es especifico del par maquina-referencia, porque la misma referencia corre a distinta velocidad en cada linea. |
| `referencia_key` | `integer NOT NULL` | FK → `dim_referencia` UQ | Llave a dim_referencia. ORIGEN: construida. |
| `unidades_por_minuto` | `numeric(8,3) NOT NULL` |  | Tasa ideal de produccion: unidades que la linea debe envasar por minuto. ORIGEN: columna 'unidades *minuto' del bloque maquina x referencia de la hoja 'Tablas Desplegables'. REGLA: es el estandar de ingenieria y el denominador del Rendimiento del OEE. Es el dato que hacia falta para poder calcular OEE y que estaba en una hoja auxiliar, no en la hoja de hechos. |
| `unidades_por_paca` | `integer NOT NULL` |  | Unidades que contiene una paca de esta referencia. ORIGEN: columna 'Unidades * paca' de la hoja 'Tablas Desplegables'. REGLA: convierte las pacas que registra el operario en unidades comparables entre referencias de 6 y de 12 colores. |
| `pacas_meta_hora` | `numeric(8,3) NOT NULL` |  | Meta de pacas por hora derivada del estandar. ORIGEN: construida. REGLA: unidades_por_minuto * 60 / unidades_por_paca. Se expresa en pacas porque es la unidad en que piensa el operario. |
| `version` | `smallint NOT NULL` |  | Numero de version del estandar para el par maquina-referencia. ORIGEN: construida. REGLA: SCD Tipo 2; empieza en 1 y se incrementa en cada cambio del estandar. *(Valor por defecto: `1`.)* |
| `valido_desde` | `date NOT NULL` | UQ | Fecha desde la que rige esta version del estandar. ORIGEN: construida. REGLA: SCD Tipo 2. |
| `valido_hasta` | `date NOT NULL` |  | Fecha hasta la que rigio esta version; NULL si es la vigente. ORIGEN: construida. REGLA: SCD Tipo 2. *(Valor por defecto: `'9999-12-31'::date`.)* |
| `es_vigente` | `boolean NOT NULL` |  | Verdadero en la version actual del estandar. ORIGEN: construida. REGLA: SCD Tipo 2; un indice unico parcial garantiza que solo exista una version vigente por par maquina-referencia. *(Valor por defecto: `true`.)* |
| `origen_estandar` | `character varying(40) NOT NULL` |  | Como se obtuvo el estandar: 'Catalogo' si venia en Tablas Desplegables, 'Inferido' si se dedujo de otra linea ajustando por el factor de produccion, 'Sin estandar' si no fue posible. ORIGEN: construida. REGLA: hace explicito el nivel de confianza del dato; los turnos con 'Sin estandar' quedan fuera del calculo del Rendimiento. |
| `motivo_cambio` | `character varying(80)` |  | Razon del cambio de version del estandar. ORIGEN: construida. REGLA: texto libre para auditar el historial del SCD2. |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_estandar_tasa`: `CHECK ((unidades_por_minuto >= (0)::numeric))`
- `ck_dim_estandar_vig`: `CHECK ((valido_hasta >= valido_desde))`

---

## `dw.dim_paro`

Dimension de causas de paro con jerarquia desbalanceada de cuatro niveles.

*Filas cargadas: aproximadamente 65.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `paro_key` | `integer NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `area_impacto` | `character varying(40) NOT NULL` |  | NIVEL 1 de la jerarquia de paros: area responsable de la causa. ORIGEN: construida. REGLA: clasificacion de los 18 codigos de paro segun quien debe actuar (Mantenimiento, Produccion, Calidad, Logistica, Servicios generales). |
| `codigo_paro` | `character(2) NOT NULL` | UQ | Codigo de paro de dos digitos, '01' a '18'. ORIGEN: cabecera de los 18 pares de columnas de la hoja Base De Datos. REGLA: el codigo se deduce de la POSICION de la columna, no de su texto, porque los encabezados tienen variantes de escritura. |
| `codigo_paro_numero` | `smallint NOT NULL` |  | El codigo como entero, para ordenar. ORIGEN: construida. |
| `nombre_codigo_paro` | `character varying(90) NOT NULL` |  | Descripcion del codigo segun el procedimiento P-MTO-22. ORIGEN: documento P-MTO-22 V1, vigente desde el 14/05/2025. REGLA: se toma la descripcion oficial del procedimiento, no la del encabezado del Excel, que esta abreviada. |
| `etiqueta_codigo_paro` | `character varying(95) NOT NULL` |  | NIVEL 2 de la jerarquia: codigo y descripcion juntos, por ejemplo '[05] Ajuste operativo'. ORIGEN: construida. REGLA: es la etiqueta que se muestra en los tableros; incluir el numero permite cruzarla con el formato en papel que usa la planta. |
| `naturaleza_paro` | `character varying(20) NOT NULL` |  | 'Planeado' o 'No planeado'. ORIGEN: construida. REGLA: se clasifican como planeados los codigos 04, 08, 15, 16, 17 y 18 (mantenimiento preventivo, capacitacion, cambio de insumos, aseo, pausa activa y afines). Es la separacion que distingue el tiempo perdido EVITABLE del que es parte normal de la operacion, y sin ella el OEE castiga a la planta por hacer lo correcto. |
| `es_imputable_mantenimiento` | `boolean NOT NULL` |  | Verdadero si el paro es responsabilidad del area de mantenimiento. ORIGEN: construida. REGLA: permite medir el desempeno de mantenimiento sin cargarle los paros de produccion o de logistica. *(Valor por defecto: `false`.)* |
| `codigo_sistema` | `character varying(20) NOT NULL` |  | Codigo del sistema fisico de la maquina. ORIGEN: construida. REGLA: ATRIBUTO CONFORMADO, lo mas importante de esta dimension. Se deduce del prefijo numerico del subcodigo y unifica las ramas 1.x (falla electromecanica), 3.x (servicios) y 5.x (ajuste operativo) en el sistema al que todas se refieren. |
| `nombre_sistema` | `character varying(70) NOT NULL` |  | NIVEL 3 de la jerarquia: nombre del sistema fisico, por ejemplo 'Sistema de dosificacion de pintura'. ORIGEN: construida. REGLA: el Excel NO puede responder 'que sistema me cuesta mas tiempo' porque las tres ramas viven en columnas separadas. Al unificarlas se descubrio que el sistema dosificador explica el 44,6% del tiempo perdido de los codigos 01/03/05 (992 de 2.222,8 h), el 11,8% del tiempo perdido total. |
| `codigo_subcodigo` | `character varying(12) NOT NULL` | UQ | Codigo del subcodigo de causa raiz. ORIGEN: columnas 'Subcodigo N' de la hoja Base De Datos y hoja oculta 'Base de datos de Sub codigos'. REGLA: la fuente tiene DOS taxonomias conviviendo; la rama 4.x historica se mapea a la 5.x vigente (4.1 a 5.1, 4.2 a 5.2, 4.3 a 5.3, 4.4 a 5.5, 4.5 a 5.6, 4.6 a 5.7, 4.7 a 5.8, 4.8 a 5.9) y se corrige la errata del propio catalogo (1.4.3 debia ser 1.4.C). |
| `nombre_subcodigo` | `character varying(90) NOT NULL` |  | NIVEL 4 de la jerarquia: causa raiz concreta. ORIGEN: idem. REGLA: la fuente trae 45 variantes de escritura para unos 25 subcodigos del codigo 01; se resuelven confiando en el PREFIJO NUMERICO y no en el texto, que es el dato fiable. |
| `nivel_detalle` | `smallint NOT NULL` |  | Profundidad real del miembro en la jerarquia, 2 a 4. ORIGEN: construida. REGLA: la jerarquia es DESBALANCEADA (ragged): solo los codigos 01, 03 y 05 tienen subcodigos. Esta columna dice hasta donde se puede bajar en cada rama. |
| `admite_subcodigo` | `boolean NOT NULL` |  | Verdadero en los codigos 01, 03 y 05. ORIGEN: construida. REGLA: evita medir como 'dato incompleto' la ausencia de subcodigo en los 15 codigos que no lo tienen; sin esta distincion el indicador de completitud daria un 78% de falsos positivos. *(Valor por defecto: `false`.)* |
| `es_subcodigo_especificado` | `boolean NOT NULL` |  | Falso en los miembros de relleno 'N/A' y 'SIN-ESP'. ORIGEN: construida. REGLA: la jerarquia desbalanceada se resuelve con miembros de relleno EXPLICITOS en lugar de NULL, de modo que el drill-down del tablero nunca aterriza en un hueco. *(Valor por defecto: `false`.)* |
| `orden_presentacion` | `integer NOT NULL` |  | Orden de presentacion del miembro. ORIGEN: construida. |

**Restricciones de validacion (CHECK).** Son las reglas de negocio que la base impide violar, de modo que un dato incoherente no puede entrar ni por error de programacion:

- `ck_dim_paro_nat`: `CHECK (((naturaleza_paro)::text = ANY ((ARRAY['No planeado'::character varying, 'Planeado'::character varying])::text[])))`
- `ck_dim_paro_nivel`: `CHECK ((nivel_detalle = ANY (ARRAY[2, 4])))`
- `ck_dim_paro_num`: `CHECK (((codigo_paro_numero >= 1) AND (codigo_paro_numero <= 18)))`

---

## `dw.dim_tipo_paro_cabecera`

Dimension del tipo de paro declarado en la cabecera del registro.

*Filas cargadas: aproximadamente 13.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `tipo_paro_key` | `smallint NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_tipo` | `character varying(20) NOT NULL` | UQ | Codigo corto del tipo de paro de cabecera. ORIGEN: construida. |
| `nombre_tipo` | `character varying(80) NOT NULL` |  | Tipo de paro declarado en la cabecera del registro. ORIGEN: columna 'Tipo de paro' de la hoja Base De Datos. REGLA: la fuente trae 19 variantes de escritura de DOS taxonomias distintas para unos 13 conceptos; se consolidaron en 13 miembros. |
| `grupo_tipo` | `character varying(40) NOT NULL` |  | Agrupacion de alto nivel del tipo de paro. ORIGEN: construida. |
| `taxonomia_origen` | `character varying(20) NOT NULL` |  | De cual de las dos taxonomias de la fuente proviene el miembro. ORIGEN: construida. REGLA: documenta la convivencia de taxonomias; permite medir cuanto del historico usa la nomenclatura antigua. |
| `variantes_fuente` | `text` |  | Variantes de escritura consolidadas en este miembro. ORIGEN: construida. REGLA: trazabilidad de la consolidacion. |

---

## `dw.dim_area_involucrada`

Dimension de areas de la empresa que intervienen en un paro.

*Filas cargadas: aproximadamente 7.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `area_key` | `smallint NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_area` | `character varying(40) NOT NULL` | UQ | Codigo corto del area. ORIGEN: construida. REGLA: derivado del nombre, sin tildes ni espacios. |
| `nombre_area` | `character varying(60) NOT NULL` |  | Area de la empresa que atendio el paro. ORIGEN: columna 'Area involucrada' de la hoja Base De Datos. REGLA: se normalizo capitalizacion y se consolidaron variantes de escritura en 7 miembros. |
| `es_area_soporte` | `boolean NOT NULL` |  | Verdadero si el area es de soporte (mantenimiento, calidad, laboratorio) y no de produccion. ORIGEN: construida. REGLA: clasificacion manual del equipo, usada para separar la responsabilidad del paro. *(Valor por defecto: `false`.)* |

---

## `dw.dim_operario`

Dimension de personal de envasado, PSEUDONIMIZADA.

*Filas cargadas: aproximadamente 44.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `operario_key` | `integer NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_operario` | `character varying(16) NOT NULL` | UQ | Codigo pseudonimo estable, formato OPER-NNN. ORIGEN: construida. REGLA: se asigna por orden de aparicion; es estable entre ejecuciones del ETL. |
| `alias_operario` | `character varying(30) NOT NULL` |  | Alias que se muestra en los tableros, formato 'Operario NNN'. ORIGEN: construida. REGLA: PSEUDONIMIZACION. Es el unico identificador que sale del esquema dw; el nombre real nunca llega a los tableros. |
| `rol` | `character varying(30) NOT NULL` |  | Rol del trabajador. ORIGEN: construida. *(Valor por defecto: `'Operario de envasado'::character varying`.)* |
| `es_identificado` | `boolean NOT NULL` |  | Falso en el miembro 'Sin informar'. ORIGEN: construida. REGLA: la fuente trae 'No' y 'No aplica' como marcadores de ausencia; se consolidan en un unico miembro de relleno con llave 0. *(Valor por defecto: `true`.)* |
| `primera_aparicion` | `date` |  | Primera fecha en que aparece el operario. ORIGEN: derivada de la hoja Base De Datos. REGLA: min(fecha) de sus registros. |
| `ultima_aparicion` | `date` |  | Ultima fecha en que aparece. ORIGEN: derivada. REGLA: max(fecha) de sus registros. |
| `turnos_registrados` | `integer NOT NULL` |  | Numero de turnos en que aparece. ORIGEN: derivada. REGLA: conteo de registros; sirve para distinguir al personal de planta del eventual. *(Valor por defecto: `0`.)* |

---

## `dw.dim_personal_mantenimiento`

Dimension de personal de mantenimiento, PSEUDONIMIZADA.

*Filas cargadas: aproximadamente 39.*

| Columna | Tipo | Clave | Descripcion, origen y regla |
|---|---|---|---|
| `personal_key` | `integer NOT NULL` | PK | Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos. |
| `codigo_personal` | `character varying(16) NOT NULL` | UQ | Codigo pseudonimo estable, formato TEC-NNN. ORIGEN: construida. |
| `alias_personal` | `character varying(30) NOT NULL` |  | Alias mostrado en los tableros, formato 'Tecnico NNN'. ORIGEN: construida. REGLA: PSEUDONIMIZACION, igual que en dim_operario. |
| `area` | `character varying(40) NOT NULL` |  | Area del tecnico. ORIGEN: derivada de la fuente. REGLA: normalizada. *(Valor por defecto: `'Mantenimiento'::character varying`.)* |
| `es_identificado` | `boolean NOT NULL` |  | Falso en el miembro 'Sin informar'. ORIGEN: construida. *(Valor por defecto: `true`.)* |

