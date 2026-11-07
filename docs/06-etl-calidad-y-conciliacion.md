# ETL, calidad de datos y conciliación

Los informes con las cifras exactas los **genera el propio ETL** en cada
ejecución:

- `etl/salida/informe_calidad_datos.md` — las 21 reglas con conteos antes y
  después.
- `etl/salida/informe_conciliacion.md` — las 62 pruebas de conciliación.
- `etl/salida/resumen_etl.json` — resumen para consumo automático.

Este documento explica **las decisiones**: por qué esta herramienta, qué reglas
se aplicaron y qué significan, y cómo se demuestra que lo cargado concuerda con
la fuente.

---

## 1. Justificación de la herramienta: Python con `openpyxl` y `psycopg`

La herramienta es libre, así que hay que justificarla. Se evaluaron tres
opciones.

### 1.1. Lo que se descartó

**Power Query / Dataflows.** Es la opción natural en un entorno Microsoft y
resuelve bien el despivote. Se descartó porque:

- El código M **no es legible en un diff de git**. Queda embebido en el
  artefacto de Power BI y revisar un cambio exige abrir la herramienta. El
  enunciado pide ETL versionado y reproducible.
- **No puede escribir en PostgreSQL.** Power Query lee y transforma, pero el
  destino es el modelo de Power BI. Se necesitaría un segundo mecanismo para
  materializar el almacén, y entonces el almacén dejaría de ser la única fuente
  de verdad para Grafana.
- **No admite pruebas automáticas.** Las reglas de resolución de subcódigos
  —45 variantes de escritura y dos taxonomías— son lógica de negocio que
  necesita pruebas unitarias.

**SQL puro con `COPY` del Excel a staging.** Tentador por lo directo, pero:

- PostgreSQL no lee `.xlsm`. Haría falta un paso previo de conversión, así que
  no se evita el lenguaje de programación, solo se parte el proceso en dos.
- El cálculo del Domingo de Pascua (algoritmo de Butcher) y los festivos
  trasladables de la Ley 51 de 1983 son procedimentales. En SQL serían
  ilegibles.
- La normalización difusa de 45 variantes de texto con expresiones regulares en
  SQL es frágil y difícil de probar.

### 1.2. Por qué Python

- **`openpyxl` lee `.xlsm` directamente**, incluidas las hojas ocultas, y con
  `data_only=True` toma el **valor calculado** de las fórmulas, que es lo que
  hace falta para conciliar contra las tablas dinámicas. Con `read_only=True`
  recorre 8.208 filas sin cargar el libro entero en memoria.
- **El código es revisable.** Cada regla de limpieza es una función con
  nombre, y el `git diff` de un cambio de criterio se lee en el navegador.
- **`psycopg` 3 con `COPY`** carga por flujo binario, no con `INSERT` fila a
  fila: el ETL completo tarda **4 segundos**.
- **Transacción única con rollback.** Si una regla bloqueante falla, no queda
  nada a medio cargar. El almacén está completo y conciliado, o está como
  estaba.
- **Se prueba.** Las tablas de resolución de turnos, referencias y subcódigos
  tienen pruebas unitarias; son el corazón de la limpieza.
- **Dependencias mínimas**: tres paquetes (`openpyxl`, `psycopg[binary]`,
  `python-dateutil`), con versión fijada. El contenedor se reconstruye igual
  dentro de un año.

### 1.3. Arquitectura del ETL en seis fases

```
1. EXTRACCIÓN     Excel → stg.*  (todo como TEXT, sin rechazar ninguna fila)
2. DIMENSIONES    stg.* → dw.dim_*  (normalización y pseudonimización)
3. HECHOS         stg.* → dw.hecho_*  (despivote y cálculo de OEE)
4. CALIDAD        21 reglas con conteos antes/después → aud.regla_calidad
5. CONCILIACIÓN   62 pruebas contra la fuente → aud.conciliacion
6. CIERRE         informes en Markdown y JSON + registro en aud.ejecucion_etl
```

**La zona de aterrizaje (`stg`) guarda todo como `TEXT`.** Es deliberado: si
staging tuviera tipos, una fila con «32» horas o una fecha mal escrita haría
fallar la extracción y se perdería la evidencia del problema. Cargando texto,
**todo entra** y los problemas se detectan y se cuentan en la fase 4, donde se
pueden documentar.

---

## 2. Reglas de limpieza y su efecto

Las 21 reglas se registran en `aud.regla_calidad` con **conteos antes,
afectadas y después**, severidad y resultado. Las dos marcadas como
`BLOQUEANTE` (DQ-18, coherencia interna del OEE; DQ-19, integridad referencial
de los paros) **abortan la carga** si fallan: en la última ejecución ambas
dieron 0 inconsistencias.

### 2.1. Las reglas que cambian el número de filas

| Regla | Qué hace | Antes | Afectadas | Después |
|---|---|---|---|---|
| **DQ-01** | Descarta 42 duplicados exactos | 8.208 | 42 | 8.166 |
| **DQ-02** | Separa las filas de continuación, que no son registros de producción | 8.208 | 3.028 | 5.138 |
| **DQ-03** | Vincula los paros de continuación a su turno cabecera | 3.028 | 903 sin vincular | 2.125 vinculados |
| **DQ-17** | **No carga** la hoja oculta de subcódigos | 1.252 | 1.252 | 0 |

**DQ-01.** Los 42 duplicados aportan 129 h, 1.019 pacas y 18,116667 h de paro.
Se conserva la primera ocurrencia por `hash_fila`. El efecto sobre el informe
del comité se cuantifica en la conciliación (bloque 3).

**DQ-02.** Es la regla de mayor impacto conceptual: el **37 % de las filas de
la «base de datos» no son registros de producción**. Quien cuente filas para
medir cualquier cosa se equivoca en un tercio.

**DQ-03.** La vinculación es en cascada de tres niveles: por fecha, máquina,
operario, referencia y turno (2.063 filas); luego sin turno (11); luego solo
por fecha y máquina (51), eligiendo el turno con más horas programadas. Quedan
**903 filas sin vincular**, de las cuales solo **5 traen minutos de paro**:
suman **1,9167 h, el 0,0227 % del tiempo de paro**. Esas horas **sí** entran al
total y al Pareto; lo único que no se puede es atribuirlas a un turno concreto.

> La cascada se aplica dos veces: en Python, para repartir el tiempo de paro
> entre los turnos, y en SQL, para resolver la llave foránea
> `hecho_paro → hecho_produccion_turno`. Las dos implementaciones **deben
> cubrir los mismos tres niveles**. Mientras la de SQL cubría solo los dos
> primeros, 53,57 h de paro quedaban en el detalle sin llave foránea aunque sus
> horas ya estuvieran sumadas en el agregado del turno. Hoy el detalle con llave
> (8.429,6183 h) y el agregado de `horas_paro_total` (8.429,6184 h) coinciden, y
> esa igualdad es lo que vigila la prueba de conciliación B2.

**DQ-17.** La hoja oculta `Base de datos de Sub codigos` tiene 1.252 filas, de
las cuales **982 ya están** en `Base De Datos`. Cargarla duplicaría 679,2 h de
paro. Las 270 ausentes no tienen minutos, así que no aportan nada. **No se
carga**, y la decisión queda documentada en lugar de ser una omisión silenciosa.

### 2.2. Las reglas que normalizan sin descartar

| Regla | Qué normaliza | Afectadas |
|---|---|---|
| **DQ-08** | Erratas de digitación en referencias (52 valores → 63 miembros limpios) | 3 confusiones de nombre |
| **DQ-10** | Dos taxonomías de subcódigos (`4.x` histórica → `5.x` vigente) y la errata del catálogo (`1.4.3` → `1.4.C`) | 475 filas de la rama antigua |
| **DQ-16** | Columna «Tipo de paro»: 19 variantes de dos taxonomías → 13 miembros | 2.184 |

La regla de oro en DQ-10: **confiar en el prefijo numérico y no en el texto**.
El número es el dato fiable; el texto es lo que cada persona escribió ese día.

### 2.3. Las reglas que marcan sin modificar

Estas no cambian el dato: le ponen una bandera para que el tablero pueda
excluirlo y el auditor pueda encontrarlo.

| Regla | Qué marca | Afectadas |
|---|---|---|
| **DQ-05** | Turno imputado porque la fuente no lo traía | 2.409 de 5.138 |
| **DQ-06** | Operario no informado | 2.620 |
| **DQ-07** | Referencia no informada | 2.390 |
| **DQ-09** | Causa raíz sin especificar, **solo** en los códigos 01, 03 y 05 | 107 de 3.691 (2,9 %) |
| **DQ-11** | Paro mayor que las horas trabajadas (el peor: 18,17 h en un turno de 10,5) | 9 |
| **DQ-12** | Horas trabajadas fuera del rango plausible de un turno, más de 12 h (una fila declara 16 h) | 1 |
| **DQ-13** | Duración atípica (> 8 h; la mayor de 900 min en el código 10) | 3 |
| **DQ-14** | Sin estándar de ingeniería, luego sin Rendimiento | 2.686 de 5.138 |
| **DQ-21** | **Rendimiento implausible**: el caso extremo declara un 1.561 %, es decir 16× el máximo teórico | 22 de 2.452 |

**DQ-09 merece una nota**, porque medirla mal es fácil. El denominador son
**solo** los eventos de los códigos 01, 03 y 05, los únicos con árbol de
subcódigos. Medida sobre los 18 códigos daría un 78 % de registros
«incompletos», cuando la ausencia de subcódigo en los otros 15 no es un defecto
sino que el nivel no existe.

**DQ-21 es un hallazgo de la carga, no un error del ETL.** 22 turnos declaran
una producción superior al 150 % del máximo que permite el estándar; el peor,
un 1.561 %, es decir 16 veces. No es una línea excepcional: o las pacas se digitaron mal, o las
horas quedaron subregistradas, o el estándar está obsoleto. Se **conserva** el
valor para poder auditarlo y se **excluye** del indicador agregado, del índice
parcial y de las medidas DAX.

### 2.4. Las reglas que solo documentan

| Regla | Qué documenta |
|---|---|
| **DQ-04** | Las tres columnas que deberían convertir pacas a unidades son inservibles: las 7 y 9 están 100 % vacías y la 8 se reutilizó para guardar el turno en 687 filas |
| **DQ-15** | «Horas no trabajadas» **no es tiempo de paro**: 1.263 filas traen un 24 fijo y la suma (41.519,85 h) supera las horas trabajadas |
| **DQ-20** | La fuente **no mide unidades defectuosas**: el componente Calidad del OEE no es medible y se usa un proxy declarado |

**DQ-15 y DQ-20 no modifican nada, y son de las más importantes.** Marcan los
dos errores de interpretación que habrían invalidado el proyecto entero:
sumar las horas no trabajadas como paro, y presentar un componente de Calidad
como si estuviera medido.

---

## 3. Conciliación con la fuente

El enunciado pide «demostrar que los totales cargados concuerdan con la fuente,
o explicar y justificar las diferencias». Hay una tensión real que obliga a
separar dos preguntas:

> El Excel contiene 42 duplicados exactos. Las tablas dinámicas que la empresa
> lleva al comité **los incluyen**, porque una tabla dinámica suma lo que
> encuentra. El modelo dimensional **los descarta**, porque cargar dos veces el
> mismo turno sería un error. Luego los totales **no pueden** coincidir, y eso
> no es un fallo: es la limpieza funcionando.

Por eso la conciliación se hizo en **cuatro bloques**, con **62 pruebas**: 58
OK, 4 informativas y **0 fallidas**.

### Bloque 1 — ¿El modelo entiende el negocio igual que el Excel?

**35 pruebas, todas OK.** Se recalculan los indicadores **desde staging
incluyendo los duplicados**, es decir imitando exactamente lo que hace una
tabla dinámica, y se comparan contra las cifras del Excel con tolerancia de
**1 × 10⁻⁶**.

| Qué se contrasta | Resultado |
|---|---|
| `TD_prodMaq`: % Productividad de Vinilos_2 en 2024, mes a mes y total | 13 de 13 coinciden a 6 decimales (total: 0,624722) |
| `Hoja4`: horas trabajadas por máquina en 2023 | 4 de 4 exactas (V1 3.390,0 · V2 1.220,5 · V3 4.221,3 · V4 4.002,55) |
| `TD_prodCodigo`: participación de los 18 códigos de paro | 18 de 18 coinciden a 6 decimales |

**Esto es lo que demuestra que la interpretación es correcta.** Si la fórmula
del modelo reproduce la del Excel hasta el sexto decimal, cualquier diferencia
posterior viene de la limpieza y no de haber entendido mal el negocio. Es
también la prueba de que el «% Productividad» del Excel **es** la
Disponibilidad del OEE.

### Bloque 2 — ¿Se cargó todo, sin perder ni duplicar nada?

**5 pruebas, todas OK.** Fuente **depurada** (menos el aporte de los 42
duplicados) contra los totales del modelo.

| Prueba | Fuente depurada | Modelo | Diferencia |
|---|---|---|---|
| Horas trabajadas | 37.934,35 | 37.934,35 | 0 |
| Pacas producidas | 377.759 | 377.759 | 0 |
| **Tiempo de paro (despivote)** | 8.431,5350 | 8.431,5350 | 0,000004 h |
| Paro atribuido a turnos | 8.429,6183 | 8.429,6184 | 0,00005 h |
| **Trazabilidad de filas** | 8.208 | 8.208 | 0 |

Dos pruebas merecen comentario:

**El despivote.** La fuente trae el total de paro en una columna calculada por
fila; el modelo lo **reconstruye** sumando los 18 pares desplegados en 16.482
eventos. Coincidir demuestra que no se perdió ni se duplicó un minuto. La
diferencia de 0,000004 h son **14 milisegundos sobre 8.431 horas**, redondeo
acumulado de 16.482 divisiones por 60.

**La trazabilidad de filas.** `8.208 = 5.138 turnos + 3.028 continuaciones +
42 duplicados`. **Ninguna fila de la fuente queda sin explicación**, y es la
prueba que cierra el argumento de que no se perdió nada por el camino.

### Bloque 3 — ¿Cuánto se equivoca hoy el informe del comité?

**4 pruebas informativas.** No hacen fallar el ETL: cuantifican un hallazgo.

| Cifra | Informe actual | Valor correcto | Inflación |
|---|---|---|---|
| Horas trabajadas | 38.063,35 | 37.934,35 | **+129 h** (+0,34 %) |
| Pacas producidas | 378.778 | 377.759 | **+1.019** (+0,27 %) |
| Tiempo de paro | 8.449,65 | 8.431,54 | **+18,12 h** (+0,21 %) |
| % Productividad V2 2024 | 0,624722 | 0,624851 | −1,3 puntos básicos |

El efecto sobre el **ratio** es pequeño, porque los duplicados afectan
numerador y denominador a la vez. Lo relevante no es la magnitud: es que el
indicador que sustenta decisiones de inversión se calcula hoy sobre un conjunto
con duplicados que nadie había detectado, y que **el formulario no tiene ningún
control que lo impida**.

### Bloque 4 — ¿Es exacto el despivote, código por código?

**18 pruebas, todas OK.** Fuente depurada contra `hecho_paro`, código a código.
La mayor diferencia es de **0,0036 h (13 segundos)** en el código 16, que es el
de más eventos (2.971), y es redondeo acumulado.

### Por qué cuatro bloques y no uno

Porque responden preguntas distintas y mezclarlas produce una conciliación que
no significa nada. Si solo se comparara contra el Excel bruto, el ETL fallaría
21 pruebas y la conclusión sería «el modelo está mal». Si solo se comparara
contra la fuente depurada, se perdería la demostración de que la fórmula es
equivalente, **y nadie se enteraría de que el informe del comité está
inflado**. El bloque 1 prueba la lógica, el 2 prueba la carga, el 3 convierte
la diferencia en un hallazgo accionable y el 4 prueba la transformación más
delicada.

---

## 4. Reproducibilidad

El proceso completo se reproduce desde cero con **un solo comando**:

```bash
docker compose up -d --build
```

Verificado: con los volúmenes eliminados, la pila entera —PostgreSQL, DDL, ETL,
Grafana con su provisioning y el simulador— queda operativa en **12 segundos**,
y el ETL termina con código de salida 0 y resultados idénticos a la ejecución
anterior (58 pruebas OK, 0 fallidas). El detalle está en el
[README](../README.md).

Lo que garantiza la reproducibilidad:

- **Versiones fijadas** en las imágenes (`postgres:17-alpine`,
  `grafana/grafana:11.6.0`, `python:3.12-slim`) y en las dependencias de
  Python.
- **SHA-256 del Excel** registrado en `aud.ejecucion_etl`: si la fuente cambia,
  queda constancia de que las cifras se calcularon sobre otro archivo.
- **`ejecucion_id` en cada fila de hechos**, para poder auditar o revertir una
  carga concreta.
- **Transacción única**: no hay estados intermedios.
