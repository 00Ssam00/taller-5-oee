# Diagnóstico de la fuente

Fuente analizada: `Seguimiento Temperas y Vinilos Actividad.xlsm` (4,2 MB,
habilitado para macros).
SHA-256: `c7d7eabbd55844757c2be07bd61efcee9eb5e0b03aaf9fd76b798737a92d5c55`.
Procedimiento asociado: **P-MTO-22 V1**, vigente desde el 14/05/2025.

Todas las cifras de este documento se obtuvieron leyendo el archivo con
`openpyxl` y son reproducibles ejecutando el ETL.

---

## 1. Estructura del archivo

El libro tiene **21 hojas**, de las cuales 5 están ocultas. La estructura real
no coincide con lo que uno esperaría de una «base de datos»:

| Hoja | Tamaño | Qué es | Oculta |
|---|---|---|---|
| `Base De Datos` | 8.217 × 58 | La tabla de hechos. **Encabezado en la fila 9**, datos desde la fila 10 | |
| `Registro` | — | El formulario de captura hora a hora, con los tres botones de macro | |
| `Tiempos` | 59 × 19 | Parámetros. Contiene la lista de 45 operarios y el factor de producción | |
| `Tablas Desplegables` | 262 × 52 | **Catálogo máquina × referencia con la tasa ideal y las unidades por paca** | |
| `Base de datos de Sub codigos` | 1.260 × 19 | Registros de subcódigos | sí |
| `TABLA CODIGOS` | 41 × 8 | Catálogo de códigos y subcódigos de paro | sí |
| `Hoja4` | — | Tabla auxiliar de horas trabajadas por máquina y año | sí |
| `Calculadora de tiempos` | — | Hoja de cálculo auxiliar | sí |
| `TD_prodMaq`, `TD_prodAño`, `TD_prodCodigo`, `TD_fallaMecanica`, `TD_ajusteOperativo`, `TD_novPotencia` | — | Tablas dinámicas: lo que se lleva al comité | |
| `prodMaquina`, `prodAño`, `prodCodigo`, `fallaMecanica`, `ajusteOperativo`, `novPotencia`, `Hoja1` | — | Hojas de apoyo de los gráficos | |

### 1.1. El dato que hacía falta estaba en una hoja auxiliar

El hallazgo estructural más importante: **la hoja de hechos no contiene lo
necesario para calcular OEE, pero el libro sí**. La hoja
`Tablas Desplegables` tiene un bloque con **135 pares máquina × referencia** y
los encabezados:

```
maquina | Nombre de referencia | # colores | Pacas | Display | Unidades * paca | unidades *minuto
```

`unidades *minuto` es la **tasa ideal de producción**, es decir el estándar de
ingeniería, y `Unidades * paca` es el factor que convierte las pacas que
registra la operaria en unidades comparables. Con esos dos datos el
**Rendimiento** del OEE se vuelve calculable. Nadie los estaba usando para eso:
alimentan las listas desplegables del formulario.

### 1.2. Formato ancho: 18 pares de columnas

Las 58 columnas incluyen **18 pares `<minutos, horas>`**, uno por cada código
de paro, más una columna de subcódigo para los códigos 01, 03 y 05. Un paro de
12 minutos por el código 05 se registra escribiendo 12 en la columna
«cod05_min» y 0,2 en «cod05_hrs».

Esto es un formato de **reporte**, no de datos: funciona para imprimir y para
hacer una tabla dinámica, pero impide preguntar «dame todos los paros de más
de 30 minutos» sin recorrer 18 columnas. El ETL lo **despivota** a 16.482
filas, una por evento.

### 1.3. Volumen y cobertura temporal

| | |
|---|---|
| Filas con datos | **8.208** |
| Rango | 2022-01-01 a **2025-03-28** |
| 2022 | 1.654 filas |
| 2023 | 2.891 filas |
| 2024 | 3.129 filas |
| 2025 | 534 filas (año parcial) |

---

## 2. Problemas de calidad de datos

Se documentaron **21 reglas de calidad** (DQ-01 a DQ-21) con conteos antes y
después; el informe completo con esas cifras lo genera el propio ETL en
`etl/salida/informe_calidad_datos.md`. Aquí van los hallazgos y por qué
importan.

### 2.1. Duplicados exactos — 42 filas

42 filas son copia idéntica de otra. Aportan **129 horas, 1.019 pacas y
18,116667 horas de paro**.

Lo relevante no es la magnitud (0,34 % de las horas) sino que **las tablas
dinámicas que hoy se llevan al comité los incluyen**, porque una tabla
dinámica suma lo que encuentra. Es un error sistemático, no aleatorio: nace de
que el botón «Ingreso total» del formulario no verifica si el registro ya
existe.

### 2.2. Filas de continuación — 3.028 filas

El botón **«Ingreso subcódigo»**, documentado en el apartado 4.1.5 del
P-MTO-22, «permite almacenar un subcódigo y continuar con el mismo registro».
En la práctica genera una fila nueva **sin pacas y sin horas trabajadas**, que
solo lleva el subcódigo y los minutos del paro.

Es decir: **el 37 % de las filas de la «base de datos» no son registros de
producción**, son anexos de la fila anterior. Quien cuente filas para medir
cualquier cosa se equivoca en un tercio.

El ETL las vincula a su cabecera en cascada de tres niveles (por fecha,
máquina, operario, referencia y turno; luego sin turno; luego solo por fecha y
máquina). Quedan **903 filas sin vincular**, porque no existe cabecera para esa
fecha y máquina; de ellas solo **5 traen minutos de paro**, y suman
**1,9167 horas: el 0,02 % del tiempo de paro**. Esas horas sí entran al total de
tiempo perdido y al Pareto; lo único que no se puede es atribuirlas a un turno
concreto.

### 2.3. Las tres columnas que deberían convertir pacas a unidades son inservibles

| Columna | Encabezado | Contenido real |
|---|---|---|
| 7 | «Unidades producidas cada minuto» | **100 % vacía** |
| 8 | «Unidad por display» | **El TURNO**, en 687 filas |
| 9 | «Display por paca» | **100 % vacía** |

Las 687 filas con la columna 8 informada **también** traen el turno en su
columna correcta, así que es una copia redundante, no un respaldo (las 3
aparentes discrepancias son variantes de notación del mismo turno:
`10pm-6am` frente a `10pm-6am (Turno 3)`).

Consecuencia práctica: la conversión de pacas a unidades **no puede salir de
la hoja de hechos** y hay que tomarla del catálogo de `Tablas Desplegables`.

### 2.4. «Horas no trabajadas» no es tiempo de paro

Es el error de interpretación más fácil de cometer con esta fuente, y haberlo
cometido habría invalidado todo el OEE:

- La suma de la columna es **41.519,85 h**, mayor que las 38.063,35 h
  trabajadas.
- **1.263 filas traen un 24 fijo** y 390 traen un 16.
- Una fila trae 32, que no cabe en un día.

No es tiempo perdido: es el **complemento del día de calendario**
(24 − horas trabajadas). Se carga en una columna aparte y **no entra al OEE**.

### 2.5. Dos taxonomías de subcódigos conviviendo

| Problema | Magnitud |
|---|---|
| Rama `4.x` histórica, en mayúsculas | **945 filas** en 8 variantes (p. ej. `4.2 SISTEMA DOSIFICADOR...`) |
| Rama `5.x` vigente | **2.149 filas** en 11 variantes |
| Variantes de escritura del subcódigo del código 01 | **44** distintas, más las filas que lo dejan vacío |
| Errata en el **propio catálogo**: `1.4.3 Sensor` | debía ser `1.4.C` |
| Valor `Sin especificar` | **5.020** apariciones |

La solución fue **confiar en el prefijo numérico y no en el texto**: el número
es el dato fiable, el texto es lo que cada persona escribió ese día. La rama
`4.x` se mapea a la `5.x` (4.1→5.1, 4.2→5.2, 4.3→5.3, 4.4→5.5, 4.5→5.6,
4.6→5.7, 4.7→5.8, 4.8→5.9) y la errata del catálogo se corrige.

### 2.6. Otros problemas documentados

| Problema | Magnitud | Tratamiento |
|---|---|---|
| Referencias con erratas de digitación | 52 valores distintos, 3 confusiones de nombre (`Alocdor`, `Stilo Kids`, `Klips 15cc (12col)`) | Consolidadas en 63 miembros limpios, conservando la lista de variantes |
| Columna «Tipo de paro» | 19 variantes de **dos** taxonomías para ~13 conceptos | Consolidadas en 13 miembros |
| Turnos escritos de varias formas | `6am-2pm`, `6am-2pm (Turno 1)`, `Turno 1` | Resueltos al mismo miembro |
| Operarios | 34 valores, incluidos los marcadores `No` y `No aplica` | Pseudonimizados; marcadores → miembro «Sin informar» |
| Paro mayor que las horas trabajadas | 9 turnos; el peor con **18,17 h de paro en un turno de 10,5 h** | Se marca con bandera; es físicamente imposible, uno de los dos datos está mal |
| Horas trabajadas fuera del rango de un turno (más de 12 h) | 1 turno declara **16 h** | Se marca con bandera; el valor no se corrige, la decisión es del dueño del dato |
| Duraciones atípicas | 3 eventos; el mayor de **900 minutos** en el código 10 | Se marcan con bandera y se conservan |
| Rendimiento implausible | 22 turnos; el extremo declara un rendimiento del **1.561 %**, es decir **16 veces** lo que la máquina puede dar | Se marcan, se conservan para auditoría y se excluyen del indicador agregado |
| Pares máquina–referencia sin estándar | 10 | Resolución en cascada: catálogo → inferido por factor de producción → sin estándar |
| Hoja oculta `Base de datos de Sub codigos` | 1.252 filas, de las cuales **982 ya están** en `Base De Datos` | **No se carga**: duplicaría 679,2 h de paro. Las 270 ausentes no tienen minutos |

### 2.7. La completitud del registro mejoró drásticamente con el tiempo

Este es el hallazgo que condiciona qué se puede medir y desde cuándo:

| Año | Con operario | Con referencia | Con turno | Con estándar | Índice de completitud |
|---|---|---|---|---|---|
| 2022 | 0 % | 0 % | 0 % | 0 % | **0 %** |
| 2023 | 20 % | 22 % | 20 % | 22 % | ~21 % |
| 2024 | 85 % | 93 % | 94 % | 82 % | ~88 % |
| 2025 | 99 % | 100 % | 100 % | 82 % | ~95 % |

**En 2022 ninguna fila tiene operario, referencia ni turno.** Solo fecha,
máquina, horas, pacas y códigos de paro. Por eso:

- La **Disponibilidad** es calculable desde 2022.
- El **Rendimiento** —y con él el OEE— **no es calculable antes de 2023**,
  porque sin referencia no hay estándar contra el que comparar.

Presentar un OEE de 2022 sería inventarlo. El modelo devuelve NULL y el
tablero lo muestra vacío, que es la respuesta honesta.

### 2.8. La fuente no mide defectos

**No existe ninguna columna de unidades defectuosas, rechazadas o
reprocesadas en unidades.** El componente **Calidad** del OEE, por tanto, no
es medible con esta fuente.

Se usa un **proxy declarado**: el tiempo del código 11 (Reproceso) convertido a
unidades equivalentes. Son **9,05 horas en todo el histórico**, lo que da una
calidad cercana al 100 % que con casi total seguridad es optimista. Se publica
como cota inferior de la pérdida y se reporta siempre junto al OEE auditable
(Disponibilidad × Rendimiento), para que se vea cuánto pesa la parte estimada.

Cerrar esta brecha requiere instrumentación, no mejor analítica: es el primer
argumento de la [propuesta de evolución a PLC/SCADA](09-evolucion-plc-scada.md).

---

## 3. Limitaciones del esquema de reporte actual

El apartado 4.1.7 del P-MTO-22 enumera los gráficos que alimenta el Excel:
producción general, producción por máquina (comparativo 2024 vs 2025),
porcentaje de códigos de paro por máquina y análisis detallado de los códigos
01, 03 y 05. Con eso se arma el informe mensual del comité.

### 3.1. El Excel no calcula OEE

Lo que el Excel llama **«% Productividad»** es:

```
% Productividad = 1 − (tiempo de paro / horas trabajadas)
```

que es exactamente la **Disponibilidad** del OEE. Se verificó reproduciéndola
desde los datos crudos y comparándola **a seis decimales** contra las tres
tablas dinámicas del libro (35 contrastes, todos coincidentes).

Es decir: la planta cree medir productividad y mide **solo uno de los tres
componentes**. Una línea parada el 20 % del tiempo pero corriendo al 60 % de su
velocidad nominal aparece con un 80 % de «productividad», cuando su OEE real
es del 48 %.

### 3.2. Las tablas dinámicas no responden la pregunta de mantenimiento

Los subcódigos de las ramas 1.x, 3.x y 5.x están en **columnas distintas** de
la hoja. Una tabla dinámica opera sobre columnas, de modo que puede decir
«cuánto tiempo costó el código 05», pero **no** «cuánto tiempo costó el
sistema dosificador», que es la pregunta que permite decidir una intervención.

### 3.3. Las cifras del comité están infladas

Por los 42 duplicados: **+129 h, +1.019 pacas, +18,12 h de paro**. Una tabla
dinámica no puede deduplicar.

### 3.4. El esquema es frágil por construcción

- **Encabezado en la fila 9**: cualquier inserción de filas arriba rompe las
  referencias.
- **18 pares de columnas**: añadir un código de paro nuevo obliga a insertar
  columnas y rehacer las fórmulas y las tablas dinámicas.
- **Macros con botones**: la trazabilidad depende de que el operador use el
  botón correcto; «Ingreso subcódigo» genera filas que parecen registros y no
  lo son.
- **Un solo archivo de 4,2 MB** en una unidad compartida: no admite dos
  personas digitando a la vez, no tiene historial de cambios y un `Ctrl+Z` mal
  dado destruye datos sin dejar rastro.
- **Sin control de duplicados, ni de rangos, ni de obligatoriedad**: por eso
  hay turnos de 32 horas y paros de 15,63 h en turnos de 8.

### 3.5. Lo que el esquema actual sí hace bien

Conviene decirlo, porque el diseño del modelo lo aprovecha:

- La **codificación de paros está bien pensada**: 18 códigos con una jerarquía
  de subcódigos que llega al sistema de la máquina. Es una taxonomía de
  mantenimiento seria, solo que atrapada en un formato que no la deja explotar.
- Los **estándares de ingeniería existen** y están definidos para 135 pares
  máquina × referencia.
- La **disciplina de registro mejoró** del 0 % al 95,3 % entre 2022 y 2025. Hay
  cultura de dato; lo que falta es la herramienta.
