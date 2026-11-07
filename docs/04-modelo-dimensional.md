# Modelo dimensional

El diccionario de datos campo por campo está en
[05-diccionario-de-datos.md](05-diccionario-de-datos.md), generado desde el
catálogo de PostgreSQL. Este documento explica **las decisiones de diseño**.

---

## 1. Elección del esquema: constelación de hechos

Se eligió un **esquema en constelación** (*fact constellation*, también
llamado galaxia): **tres tablas de hechos que comparten dimensiones
conformadas**.

### 1.1. Por qué no una sola estrella

La tentación inicial es una única tabla de hechos de producción con los 18
códigos de paro como columnas, replicando la fuente. Se descartó porque:

- **No se puede preguntar por causa.** «Dame los paros de más de 30 minutos»
  exige recorrer 18 columnas. Y añadir un código 19 obligaría a alterar la
  tabla, reescribir las consultas y rehacer los tableros: exactamente la
  fragilidad que se quiere eliminar.
- **Desperdicia espacio y confunde.** De los 18 pares, la mayoría están vacíos
  en cada fila.
- **No admite los atributos del paro.** El subcódigo, el sistema físico, el
  área responsable y la naturaleza planeado/no planeado son atributos *del
  evento de paro*, no del turno. En formato ancho no tienen dónde vivir.

### 1.2. Por qué no un copo de nieve (snowflake)

Normalizar `dim_paro` en tres tablas (área → código → subcódigo) y
`dim_referencia` en dos (línea comercial → referencia) sería más ortodoxo
relacionalmente, pero:

- **Encarece la consulta que más se usa.** El Pareto de causas pasaría de un
  JOIN a tres, y es la consulta del tablero que más se refresca.
- **Complica el drill-down en Power BI.** Una jerarquía de cuatro niveles
  repartida en tres tablas obliga a relaciones encadenadas; en una sola tabla
  desnormalizada la jerarquía se define directamente.
- **No compra nada.** `dim_paro` tiene **65 filas**. El ahorro de espacio al
  normalizar es irrelevante y el costo de claridad es real.

Las dimensiones se dejan **desnormalizadas**, que es la recomendación de
Kimball para un almacén orientado a consulta.

### 1.3. Por qué la constelación y no una estrella con un solo hecho

Porque hay **tres granos distintos** y mezclarlos produciría números falsos:

| Hecho | Grano | Por qué no cabe en los otros |
|---|---|---|
| `hecho_produccion_turno` | Un turno de una máquina en una fecha, para una referencia | Las métricas de producción (horas, pacas) existen una sola vez por turno |
| `hecho_paro` | Un evento de paro de un código concreto dentro de un turno | Hay 0..18 paros por turno. Meterlos en el hecho de turno duplicaría las horas y las pacas en cada evento |
| `hecho_produccion_hora` | Una hora de reloj de una máquina | Es el grano que entregará el PLC. No existe en el Excel |

El riesgo clásico de mezclarlos: si se pusiera un paro por fila junto a las
pacas del turno, un turno con 5 paros reportaría **5 veces** sus pacas. La
separación por grano es lo que lo impide.

### 1.4. Las dimensiones conformadas son la clave

`dim_fecha`, `dim_maquina`, `dim_turno` y `dim_referencia` son **las mismas
tablas** para los tres hechos. Eso permite poner en un mismo informe el OEE del
turno y el Pareto de causas filtrados por el mismo mes y la misma máquina, con
la garantía de que ambos hablan de lo mismo.

**No existe ninguna relación directa entre las tablas de hechos.** Es
deliberado: en una constelación los hechos se relacionan *entre sí*
exclusivamente a través de las dimensiones conformadas. Unirlos crearía caminos
de filtro ambiguos en Power BI y conteos duplicados en SQL.

> `hecho_paro.produccion_turno_id` apunta al turno, pero **no se declara como
> relación en el modelo semántico**: existe solo para trazabilidad y auditoría,
> no como camino de filtro.

---

## 2. Grano declarado de cada tabla de hechos

### `dw.hecho_produccion_turno` — 5.138 filas

> **Un registro por turno de producción de una máquina en una fecha, para una
> referencia concreta.**

Si durante el mismo turno la línea cambia de referencia, la fuente genera un
registro nuevo; `consecutivo_registro` los distingue y **forma parte del
grano**. La clave única es
`(fecha_key, maquina_key, turno_key, referencia_key, consecutivo_registro)`.

De las 8.208 filas del Excel, 5.138 son registros de turno; las otras 3.070 son
3.028 continuaciones del botón «Ingreso subcódigo» y 42 duplicados exactos.
**La suma cuadra exactamente** y ese cuadre es una de las pruebas de
conciliación.

### `dw.hecho_paro` — 16.482 filas

> **Un registro por evento de paro de un código concreto dentro de un turno de
> una máquina.**

Resultado de despivotar los 18 pares `<minutos, horas>`. Solo se crea fila
cuando los minutos son mayores que cero.

### `dw.hecho_produccion_hora`

> **Un registro por hora de reloj y máquina.**

Es el grano que entregaría un historiador de PLC/SCADA. Hoy lo alimenta el
simulador; el ETL del Excel no escribe aquí porque la fuente histórica no tiene
grano horario.

### Aditividad de las métricas

Distinguirla evita el error más común al construir el tablero:

| Tipo | Métricas | Se puede sumar |
|---|---|---|
| **Aditivas** | horas programadas, horas de paro, horas operativas, pacas, unidades, eventos | En todas las dimensiones |
| **Semiaditivas** | `tasa_ideal_unid_min` | En ninguna: es un atributo del estándar que se congela en el hecho |
| **No aditivas (ratios)** | Disponibilidad, Rendimiento, Calidad, OEE | **Nunca.** Hay que recalcularlas desde los numeradores y denominadores agregados |

Por eso las medidas DAX se definen como `DIVIDE(SUM(...), SUM(...))` y **no**
como `AVERAGE(oee_ad)`. Promediar el OEE de 5.138 turnos da un número que no
significa nada, porque un turno de 2 horas pesaría igual que uno de 12. La
columna `oee_ad` existe en el hecho para poder auditar fila a fila contra la
fuente, no para agregarla.

Hay un segundo requisito, menos evidente y más fácil de incumplir: cuando un
indicador es el **producto** de dos ratios, los dos tienen que medirse sobre
las **mismas filas**. La Disponibilidad se puede calcular en cualquier turno
porque solo necesita horas; el Rendimiento exige un estándar de ingeniería, y
la fuente solo lo trae en una parte de los registros. Multiplicar la
Disponibilidad de todos los turnos por el Rendimiento de unos pocos produce un
número que no describe ninguna operación: en Vinilos_1 2023, con un 28 % de
cobertura, daba un OEE del 62,0 % frente al 49,7 % real, e inventaba una caída
de 13 puntos hacia 2024 que nunca existió. De ahí las medidas
`Disponibilidad (OEE)`, `Horas operativas (OEE)` y `Horas programadas (OEE)`,
restringidas al mismo subconjunto que el Rendimiento, y la medida
`Cobertura del OEE`, que se publica al lado del indicador para que el lector
sepa sobre qué fracción del periodo está mirando.

---

## 3. Dimensiones, atributos y jerarquías

| Dimensión | Filas | Jerarquías | Nota |
|---|---|---|---|
| `dim_fecha` | 1.826 | Año → Trimestre → Mes → Día · Año → Semana ISO → Día | **Construida por el equipo** |
| `dim_maquina` | 4 | Planta → Línea | Contiene el factor de producción |
| `dim_turno` | 8 | Tipo de jornada → Turno | |
| `dim_referencia` | 63 | Línea comercial → Referencia → Presentación | |
| `dim_paro` | 65 | **Área → Código → Sistema → Causa raíz** | Jerarquía desbalanceada |
| `dim_estandar` | 137 | — | **SCD Tipo 2** |
| `dim_tipo_paro_cabecera` | 13 | Grupo → Tipo | |
| `dim_area_involucrada` | 7 | — | |
| `dim_operario` | 44 | — | Pseudonimizada |
| `dim_personal_mantenimiento` | 39 | — | Pseudonimizada |

### 3.1. `dim_fecha`: la dimensión construida por el equipo

El enunciado pide al menos una dimensión construida por el equipo. `dim_fecha`
**no existe en la fuente**: el Excel solo tiene una columna de fecha. Se generó
en el ETL con 1.826 días (2022–2026) y 23 atributos. Los que no son obvios:

- **`es_festivo` y `nombre_festivo`** — festivos de Colombia calculados en
  código: los fijos, los derivados del Domingo de Pascua con el **algoritmo de
  Butcher**, y los trasladables al lunes siguiente según la **Ley 51 de 1983
  (Ley Emiliani)**. Permite separar la producción de día hábil de la de
  festivo, que tiene otro costo de mano de obra.
- **`fecha_key_anio_ant` y `anio_mes_anio_ant`** — la llave del mismo día y del
  mismo mes del año anterior, **precalculadas**. Convierte cualquier
  comparativo interanual en SQL en un JOIN en lugar de aritmética de fechas en
  cada consulta.
- **`anio_semana_iso` aparte de `anio`** — porque en la primera y la última
  semana del año difieren, y agregarlas por `anio` partiría semanas.
- **`mes` numérico junto a `nombre_mes`** — para que los meses no salgan en
  orden alfabético en los tableros.
- Los nombres de mes y día se generan **en el ETL y no con `to_char`**, para no
  depender de la configuración regional del servidor.

`fecha_key` es un entero `AAAAMMDD` en lugar de una fecha: los índices y los
JOIN son más compactos y la llave se lee sin consultar la dimensión.

### 3.2. Miembros de relleno en lugar de NULL

Todas las dimensiones reservan la llave **0** para un miembro «Sin informar» o
«No aplica». Las llaves foráneas de los hechos son `NOT NULL`.

Razón: un `NULL` en una llave foránea rompe el `INNER JOIN` y la fila
desaparece del informe sin avisar. Con miembro de relleno, el turno sin
operario sigue sumando sus horas y aparece etiquetado como «Sin informar», que
es la verdad. Es la diferencia entre un informe que miente por omisión y uno
que declara lo que no sabe.

---

## 4. Cómo se modela la jerarquía de los paros

Es la decisión de diseño más delicada del proyecto, por tres razones.

### 4.1. La jerarquía real es desbalanceada (*ragged*)

| Nivel | Atributo | Cardinalidad |
|---|---|---|
| 1 | `area_impacto` | 6 áreas |
| 2 | `etiqueta_codigo_paro` | 18 códigos |
| 3 | `nombre_sistema` | 14 sistemas |
| 4 | `nombre_subcodigo` | Causa raíz |

**Solo los códigos 01, 03 y 05 tienen subcódigos.** Los otros 15 terminan en el
nivel 2. Una jerarquía donde las ramas tienen profundidad distinta es
*ragged*, y hay dos formas de resolverlo:

- Dejar `NULL` en los niveles que no aplican. El drill-down del tablero
  aterriza en una fila en blanco y el usuario no sabe si falta el dato o no
  existe el nivel.
- **Rellenar con miembros explícitos.** Es lo que se hizo: `'N/A'` cuando el
  código no admite subcódigo, y `'SIN-ESP'` cuando sí lo admite pero la fuente
  no lo especificó.

**Son dos cosas distintas y por eso se distinguen.** `'N/A'` significa «este
nivel no existe para esta rama»; `'SIN-ESP'` significa «este nivel existe y
falta el dato». Confundirlas arruinaría el indicador de completitud: medido
sobre los 18 códigos daría un 78 % de registros «incompletos», cuando el valor
real —medido solo donde el subcódigo tiene sentido— es del **2,9 %**
(107 de 3.691 eventos). La columna `admite_subcodigo` es lo que permite hacer
esa distinción, y `nivel_detalle` dice hasta dónde se puede bajar en cada rama.

### 4.2. El nivel 3 es un atributo conformado construido por el equipo

Este es el aporte de diseño más valioso. En la fuente los subcódigos están
organizados por **rama numérica**, que corresponde al *tipo de problema*:

- `1.x` → falla electromecánica (código 01)
- `3.x` → novedad en sistemas de potencia (código 03)
- `5.x` → ajuste operativo (código 05)

Pero `1.4` (sensor del dosificador), `3.2` (aire del dosificador) y `5.2`
(ajuste del dosificador) **se refieren al mismo sistema físico**. En el Excel
viven en columnas distintas, así que nadie puede sumar lo que cuesta el
dosificador.

El ETL deduce el **sistema físico** del prefijo numérico del subcódigo y lo
guarda en `codigo_sistema` / `nombre_sistema`. Así, las tres ramas convergen en
el sistema al que todas apuntan.

Resultado: **el sistema de dosificación de pintura explica el 44,6 % del tiempo
perdido por causas con raíz identificable** (992 h de las 2.222,8 h de los
códigos 01/03/05, es decir el 11,8 % del tiempo perdido total) y cinco sistemas
explican el 81,6 %. Es una pregunta que la fuente contiene pero no puede
responder, y el modelo sí.

### 4.3. Dos taxonomías conviviendo

La fuente tiene una rama `4.x` histórica y una `5.x` vigente para los mismos
conceptos, y 45 variantes de escritura para unos 25 subcódigos del código 01.
La regla que se aplicó: **confiar en el prefijo numérico, no en el texto**. El
número es el dato fiable; el texto es lo que cada persona escribió ese día. Se
mapea `4.1→5.1, 4.2→5.2, 4.3→5.3, 4.4→5.5, 4.5→5.6, 4.6→5.7, 4.7→5.8, 4.8→5.9`
y se corrige la errata del propio catálogo (`1.4.3` debía ser `1.4.C`).

`dim_tipo_paro_cabecera` guarda en `taxonomia_origen` de cuál de las dos
taxonomías viene cada miembro, para poder medir cuánto del histórico usa la
nomenclatura antigua.

### 4.4. Por qué una sola tabla y no tres

Los cuatro niveles están **desnormalizados en `dim_paro`**, con 65 filas.
Normalizarlos en tres tablas convertiría el Pareto —la consulta más frecuente
del tablero— en tres JOIN, y complicaría el drill-down de Power BI, a cambio de
un ahorro de espacio irrelevante.

---

## 5. Matriz de bus

Relaciona los procesos de negocio con las dimensiones conformadas. Las columnas
con ✓ en varias filas son las dimensiones que permiten cruzar procesos.

| Proceso de negocio → | Fecha | Máquina | Turno | Referencia | Estándar | Paro | Tipo paro cab. | Área invol. | Operario | Personal mto. |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **Producción por turno** (`hecho_produccion_turno`) | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ | |
| **Eventos de paro** (`hecho_paro`) | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ | ✓ | ✓ |
| **Telemetría horaria** (`hecho_produccion_hora`) | ✓ | ✓ | ✓ | ✓ | | ✓ | | | ✓ | |
| **Calidad del dato** (`aud.regla_calidad`) | ✓ | | | | | | | | | |
| **Conciliación con la fuente** (`aud.conciliacion`) | ✓ | ✓ | | | | ✓ | | | | |

Cómo se lee:

- **Fecha, Máquina, Turno y Referencia** son las cuatro dimensiones
  verdaderamente conformadas: aparecen en los tres procesos productivos. Son
  las que se usan como segmentaciones globales en los tableros.
- **Paro** solo aplica donde hay eventos de paro. En producción por turno el
  paro está *agregado* (`horas_paro_total`), no detallado: son granos distintos.
- **Estándar** solo aplica a producción por turno, porque es donde se compara
  contra la tasa ideal.
- **Personal de mantenimiento** solo aplica a eventos de paro: la fuente lo
  registra cuando alguien atiende una avería, no por turno.
- Los dos últimos procesos son de **auditoría**, no de negocio, pero se
  incluyen porque comparten `dim_fecha` y permiten responder «¿podemos confiar
  en el dato de este mes?» con la misma segmentación de tiempo que el resto.

---

## 6. Dimensión de cambio lento (SCD)

### 6.1. Qué dimensión lo necesita y por qué

**`dim_estandar`** es la única que lo requiere de verdad, y el razonamiento es
el que decide el tipo:

La tasa ideal de producción de un par máquina–referencia **cambia con el
tiempo**: se reacondiciona la máquina, se cambia el molde del envase,
ingeniería revisa el estándar. Y el Rendimiento del OEE se calcula **dividiendo
por ese estándar**.

Si se sobrescribiera el estándar (Tipo 1), **todo el histórico de Rendimiento
se recalcularía hacia atrás**. Un turno de 2023 que rindió al 95 % contra el
estándar de entonces podría aparecer al 78 % porque en 2025 se subió el
estándar. El indicador del pasado cambiaría sin que nada hubiera pasado en el
pasado, y el informe de este mes dejaría de cuadrar con el del mes anterior.
Eso destruye la credibilidad del tablero más rápido que cualquier error de
cálculo.

### 6.2. Tipo elegido: **SCD Tipo 2**

| Columna | Función |
|---|---|
| `version` | Número de versión, desde 1 |
| `valido_desde` / `valido_hasta` | Vigencia; `NULL` en la versión actual |
| `es_vigente` | Bandera de la versión actual |
| `motivo_cambio` | Por qué se cambió, para auditar |

Un **índice único parcial** garantiza que solo exista una versión vigente por
par máquina–referencia:

```sql
CREATE UNIQUE INDEX uq_dim_estandar_vigente
    ON dw.dim_estandar (maquina_key, referencia_key)
    WHERE es_vigente;
```

Además, `hecho_produccion_turno` **copia la tasa ideal** en
`tasa_ideal_unid_min`. Así, incluso si alguien manipulara la dimensión, el
indicador histórico ya calculado no se altera: el hecho congela el estándar que
regía en ese momento.

`origen_estandar` registra el nivel de confianza: `'Catalogo'` si venía en
`Tablas Desplegables`, `'Inferido'` si se dedujo de otra línea ajustando por el
factor de producción. De los **137 miembros: 132 vienen del catálogo y 5 se
infirieron**. Quedan además **10 pares máquina–referencia sin estándar**, que no
generan miembro: sus turnos se marcan con `tiene_estandar = false` y el
Rendimiento queda en NULL.

### 6.3. Las otras dimensiones y por qué no las necesitan

| Dimensión | Tipo | Razón |
|---|---|---|
| `dim_referencia` | **Tipo 1** (sobrescribir) | Los cambios son correcciones de erratas de digitación. Conservar «Alocdor» como versión histórica sería conservar un error, no un hecho del negocio. `variantes_fuente` guarda las variantes para auditar |
| `dim_maquina` | **Tipo 1** | Un cambio de nombre es cosmético. Si cambiara el `factor_produccion` habría que pasarla a Tipo 2, por el mismo argumento de `dim_estandar`; hoy no ha cambiado |
| `dim_operario` | **Tipo 1** | Un cambio de rol no debe reescribir el histórico, pero analizar por persona está **fuera del alcance declarado** del tratamiento de datos personales, así que no se versiona |
| `dim_paro` | **Tipo 1** | El catálogo del P-MTO-22 es normativo. Si cambiara, interesa el código vigente; `taxonomia_origen` ya deja rastro de la convivencia de taxonomías |
| `dim_fecha` | No aplica | El calendario no cambia |

---

## 7. Restricciones e índices

### 7.1. Restricciones

- **Llaves foráneas en todas las llaves de dimensión**, todas `NOT NULL`
  gracias a los miembros de relleno. La base **impide** cargar un hecho que
  apunte a una dimensión inexistente, de modo que el error de integridad no
  depende de que el ETL esté bien escrito.
- **21 restricciones `CHECK`** que codifican reglas de negocio: que los ratios
  estén entre 0 y 1, que las horas operativas sean coherentes con programadas
  menos paro, que los minutos de paro no sean negativos, que la suma de paro
  planeado y no planeado dé el total. Están listadas en el
  [diccionario de datos](05-diccionario-de-datos.md).
- **Claves únicas de negocio** además de la primaria técnica: la del grano en
  `hecho_produccion_turno`, y `(instante, maquina_key)` en
  `hecho_produccion_hora`, que permite al simulador usar `ON CONFLICT`.

### 7.2. Estrategia de índices, justificada por el tipo de consulta

63 índices en `dw`, con cinco criterios:

1. **Un índice por cada llave foránea.** PostgreSQL **no** los crea
   automáticamente, y sin ellos cada JOIN con una dimensión es un recorrido
   completo de la tabla de hechos.
2. **Índices compuestos con `fecha_key` primero.** Prácticamente toda consulta
   analítica filtra por periodo; poner la fecha al frente permite usar el
   índice tanto para `WHERE anio = 2024` como para los agrupamientos por mes.
3. **Índices parciales** para los subconjuntos que el tablero consulta siempre:
   los turnos con estándar y rendimiento plausible, los paros no planeados, la
   versión vigente del estándar. Un índice parcial es más pequeño y cabe mejor
   en memoria.
4. **Índice BRIN sobre `hecho_produccion_hora(instante)`.** Es una tabla de
   serie de tiempo que crece de forma monótona y se consulta por rangos
   recientes. Un BRIN ocupa una fracción de lo que ocuparía un B-tree y para
   este patrón rinde igual.
5. **Ningún índice sobre las columnas de métricas.** Nadie filtra por
   `WHERE pacas_producidas = 37`; indexarlas solo encarecería la carga.

Se usa `INCLUDE` en algunos índices para habilitar *index-only scans* en las
consultas del Pareto, que leen pocas columnas sobre muchas filas.
