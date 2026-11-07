# Catálogo de medidas DAX

**Este archivo se genera automáticamente** desde los archivos TMDL del
modelo semántico (`herramientas/gen_dax_doc.py`), para que no pueda quedar
desactualizado respecto de lo que Power BI carga de verdad.

El modelo define **36 medidas**, agrupadas en
7 carpetas de visualización.

Sirve para dos cosas: documentar el modelo semántico en el PDF entregable,
y tener las expresiones listas para pegar si hubiera que recrear alguna
medida a mano.

## Índice

- **01 Tiempo** — `% de paro evitable`, `Horas de paro`, `Horas de paro no planeado`, `Horas operativas`, `Horas programadas`
- **02 OEE** — `Brecha vs meta`, `Calidad (proxy)`, `Cobertura del OEE`, `Disponibilidad`, `Disponibilidad (OEE)`, `Horas operativas (OEE)`, `Horas programadas (OEE)`, `Meta de OEE`, `OEE`, `OEE completo`, `Rendimiento`, `Unidades posibles`, `Unidades producidas`
- **03 Inteligencia de tiempo** — `Disponibilidad movil 3 meses`, `Horas de paro del ano anterior`, `OEE acumulado del ano`, `OEE del ano anterior`, `Variacion de OEE interanual`
- **04 Paros** — `Duracion media del paro`, `Horas perdidas`, `Numero de eventos`, `Unidades no producidas`
- **05 Pareto** — `% acumulado de tiempo perdido`, `Clasificacion Pareto`, `Horas perdidas acumuladas`, `Meta Pareto 80%`
- **06 Confiabilidad** — `MTBF`, `MTTR`
- **07 Gobierno del dato** — `Indice de completitud del registro`, `Turnos registrados`, `Turnos sin estandar`

---

## 01 Tiempo

### `% de paro evitable`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Que proporcion del tiempo perdido era evitable.

```dax
% de paro evitable =
DIVIDE([Horas de paro no planeado], [Horas de paro])
```

### `Horas de paro`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Tiempo total perdido por paros.

```dax
Horas de paro =
SUM('Produccion por turno'[horas_paro_total])
```

### `Horas de paro no planeado`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Tiempo perdido EVITABLE. Es la cifra sobre la que se puede actuar.

```dax
Horas de paro no planeado =
SUM('Produccion por turno'[horas_paro_no_planeado])
```

### `Horas operativas`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Horas en que la linea estuvo efectivamente produciendo.

```dax
Horas operativas =
SUM('Produccion por turno'[horas_operativas])
```

### `Horas programadas`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Horas que la planta programo para producir. Es el denominador de la Disponibilidad.

```dax
Horas programadas =
SUM('Produccion por turno'[horas_programadas])
```

---

## 02 OEE

### `Brecha vs meta`

*Tabla:* `Produccion por turno` · *Formato:* `+0.0%;-0.0%;0.0%`

Puntos porcentuales por encima o por debajo de la meta.

```dax
Brecha vs meta =
[OEE] - [Meta de OEE]
```

### `Calidad (proxy)`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Tercer componente del OEE, como PROXY declarado. La fuente no registra unidades defectuosas, asi que la perdida de calidad se estima con el tiempo de reproceso (codigo 11). Es una COTA INFERIOR de la perdida real: el OEE verdadero no puede ser mayor que este.

```dax
Calidad (proxy) =
VAR Reproceso =
    CALCULATE(
        SUM('Eventos de paro'[unidades_no_producidas]),
        'Paro'[codigo_paro] = "11"
    )
VAR Producidas = [Unidades producidas]
RETURN
    IF(
        Producidas > 0,
        1 - DIVIDE(Reproceso, Producidas)
    )
```

### `Cobertura del OEE`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Que porcentaje de los turnos del periodo entra en el calculo del OEE. Hay que declararla junto al OEE: en 2023 solo el 24 % de los turnos tiene estandar de ingenieria, asi que el OEE de ese ano describe una cuarta parte de la operacion.

```dax
Cobertura del OEE =
DIVIDE(
    CALCULATE(
        [Turnos registrados],
        'Produccion por turno'[tiene_estandar] = TRUE(),
        'Produccion por turno'[rendimiento_implausible] = FALSE()
    ),
    [Turnos registrados]
)
```

### `Disponibilidad`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Primer componente del OEE. REPRODUCE EXACTAMENTE el '% Productividad' que el Excel calcula hoy: se verifico a seis decimales contra las tablas dinamicas de la fuente.

```dax
Disponibilidad =
DIVIDE([Horas operativas], [Horas programadas])
```

### `Disponibilidad (OEE)`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Factor de Disponibilidad que entra en el OEE. NO es el mismo que la medida 'Disponibilidad': esa se calcula sobre TODOS los turnos porque solo necesita horas, y es la que reproduce el '% Productividad' del Excel. Esta se limita a los turnos con estandar para no multiplicar dos factores medidos sobre poblaciones distintas.

```dax
Disponibilidad (OEE) =
DIVIDE([Horas operativas (OEE)], [Horas programadas (OEE)])
```

### `Horas operativas (OEE)`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Numerador del factor de Disponibilidad dentro del OEE, sobre los mismos turnos auditables que el Rendimiento.

```dax
Horas operativas (OEE) =
CALCULATE(
    SUM('Produccion por turno'[horas_operativas]),
    'Produccion por turno'[tiene_estandar] = TRUE(),
    'Produccion por turno'[rendimiento_implausible] = FALSE()
)
```

### `Horas programadas (OEE)`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Denominador del factor de Disponibilidad DENTRO del OEE. Se restringe al mismo subconjunto de turnos que el Rendimiento para que el producto de los dos factores sea coherente: ambos miden la misma poblacion.

```dax
Horas programadas (OEE) =
CALCULATE(
    SUM('Produccion por turno'[horas_programadas]),
    'Produccion por turno'[tiene_estandar] = TRUE(),
    'Produccion por turno'[rendimiento_implausible] = FALSE()
)
```

### `Meta de OEE`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Meta del 65%. No es arbitraria: es el nivel que Vinilos_3 y Vinilos_4 ya sostienen con los mismos equipos y el mismo producto, asi que esta demostrado que es alcanzable.

```dax
Meta de OEE =
0.65
```

### `OEE`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

OEE auditable: Disponibilidad por Rendimiento, ambos medidos sobre los MISMOS turnos (los que tienen estandar y rendimiento plausible). Se agrega como razon de sumas, no como promedio de los OEE por turno, para que valga en cualquier nivel de la jerarquia. Declarar siempre la 'Cobertura del OEE' al lado.

```dax
OEE =
[Disponibilidad (OEE)] * [Rendimiento]
```

### `OEE completo`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

OEE con los tres componentes, usando el proxy de Calidad. Se presenta junto al OEE auditable para dejar claro cuanto pesa la parte estimada.

```dax
OEE completo =
[Disponibilidad (OEE)] * [Rendimiento] * [Calidad (proxy)]
```

### `Rendimiento`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Segundo componente del OEE. El Excel NO lo calcula: es uno de los indicadores nuevos que habilita este modelo.

```dax
Rendimiento =
DIVIDE([Unidades producidas], [Unidades posibles])
```

### `Unidades posibles`

*Tabla:* `Produccion por turno` · *Formato:* `#,0`

Unidades que el estandar de ingenieria permitiria producir en el tiempo que la linea estuvo operando.

```dax
Unidades posibles =
CALCULATE(
    SUM('Produccion por turno'[unidades_posibles]),
    'Produccion por turno'[tiene_estandar] = TRUE(),
    'Produccion por turno'[rendimiento_implausible] = FALSE()
)
```

### `Unidades producidas`

*Tabla:* `Produccion por turno` · *Formato:* `#,0`

Unidades producidas, contando solo los turnos con estandar de ingenieria y excluyendo los 22 turnos con rendimiento implausible. El filtro es deliberado: sin estandar no hay con que comparar, y un dato erroneo inflaria el indicador.

```dax
Unidades producidas =
CALCULATE(
    SUM('Produccion por turno'[unidades_producidas]),
    'Produccion por turno'[tiene_estandar] = TRUE(),
    'Produccion por turno'[rendimiento_implausible] = FALSE()
)
```

---

## 03 Inteligencia de tiempo

### `Disponibilidad movil 3 meses`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

Promedio movil de tres meses con DATESINPERIOD. Aisla la tendencia del ruido de un mes suelto.

```dax
Disponibilidad movil 3 meses =
VAR Ultimo = MAX('Fecha'[fecha])
RETURN
    CALCULATE(
        [Disponibilidad],
        DATESINPERIOD('Fecha'[fecha], Ultimo, -3, MONTH)
    )
```

### `Horas de paro del ano anterior`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Tiempo perdido en el mismo periodo del ano anterior.

```dax
Horas de paro del ano anterior =
CALCULATE(
    [Horas de paro],
    SAMEPERIODLASTYEAR('Fecha'[fecha])
)
```

### `OEE acumulado del ano`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

OEE acumulado del ano hasta la fecha, con TOTALYTD. Es la cifra que se presenta en el comite: suaviza el mes malo aislado.

```dax
OEE acumulado del ano =
TOTALYTD([OEE], 'Fecha'[fecha])
```

### `OEE del ano anterior`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

MEDIDA DE INTELIGENCIA DE TIEMPO. El mismo periodo del ano anterior, usando SAMEPERIODLASTYEAR sobre la tabla de fechas marcada. Permite comparar marzo contra marzo sin que la estacionalidad distorsione la lectura.

```dax
OEE del ano anterior =
CALCULATE(
    [OEE],
    SAMEPERIODLASTYEAR('Fecha'[fecha])
)
```

### `Variacion de OEE interanual`

*Tabla:* `Produccion por turno` · *Formato:* `+0.0%;-0.0%;0.0%`

Cuantos puntos porcentuales gano o perdio la linea frente al mismo periodo del ano pasado. Devuelve vacio si falta alguno de los dos periodos, para no mostrar una caida del 100% donde en realidad no hay dato comparable.

```dax
Variacion de OEE interanual =
VAR Actual = [OEE]
VAR Anterior = [OEE del ano anterior]
RETURN
    IF(
        NOT ISBLANK(Actual) && NOT ISBLANK(Anterior),
        Actual - Anterior
    )
```

---

## 04 Paros

### `Duracion media del paro`

*Tabla:* `Eventos de paro` · *Formato:* `0.00`

Horas por evento. Junto con el numero de eventos distingue el problema cronico (muchos paros cortos) del problema grave (pocos pero largos).

```dax
Duracion media del paro =
DIVIDE([Horas perdidas], [Numero de eventos])
```

### `Horas perdidas`

*Tabla:* `Eventos de paro` · *Formato:* `#,0.0`

Tiempo perdido medido sobre la tabla de eventos de paro, que es la que permite abrir la causa hasta el cuarto nivel de la jerarquia.

```dax
Horas perdidas =
SUM('Eventos de paro'[horas_paro])
```

### `Numero de eventos`

*Tabla:* `Eventos de paro` · *Formato:* `#,0`

Numero de eventos de paro registrados.

```dax
Numero de eventos =
COUNTROWS('Eventos de paro')
```

### `Unidades no producidas`

*Tabla:* `Eventos de paro` · *Formato:* `#,0`

Traduce el tiempo perdido al lenguaje del negocio: cuantas unidades se dejaron de envasar.

```dax
Unidades no producidas =
SUM('Eventos de paro'[unidades_no_producidas])
```

---

## 05 Pareto

### `% acumulado de tiempo perdido`

*Tabla:* `Eventos de paro` · *Formato:* `0.0%`

Porcentaje acumulado del tiempo perdido. Es la LINEA del grafico de Pareto: donde cruza el 80% estan las pocas causas que explican casi todo el problema.

```dax
% acumulado de tiempo perdido =
DIVIDE(
    [Horas perdidas acumuladas],
    CALCULATE([Horas perdidas], ALLSELECTED('Paro'))
)
```

### `Clasificacion Pareto`

*Tabla:* `Eventos de paro`

Marca si la causa pertenece al 80% que concentra el tiempo perdido. Sirve para colorear el grafico y para filtrar el plan de mantenimiento.

```dax
Clasificacion Pareto =
IF(
    [% acumulado de tiempo perdido] <= 0.8,
    "Causa vital",
    "Causa trivial"
)
```

### `Horas perdidas acumuladas`

*Tabla:* `Eventos de paro` · *Formato:* `#,0.0`

Suma acumulada de horas perdidas recorriendo las causas de mayor a menor. Es la mitad de la curva de Pareto.

```dax
Horas perdidas acumuladas =
VAR HorasDeLaCausa = [Horas perdidas]
VAR TodasLasCausas =
    ADDCOLUMNS(
        ALLSELECTED('Paro'[etiqueta_codigo_paro]),
        "@horas", [Horas perdidas]
    )
VAR Acumulado =
    SUMX(
        FILTER(TodasLasCausas, [@horas] >= HorasDeLaCausa),
        [@horas]
    )
RETURN
    IF(NOT ISBLANK(HorasDeLaCausa), Acumulado)
```

### `Meta Pareto 80%`

*Tabla:* `Eventos de paro` · *Formato:* `0\ %;-0\ %;0\ %`

```dax
Meta Pareto 80% =
0.8
```

---

## 06 Confiabilidad

### `MTBF`

*Tabla:* `Produccion por turno` · *Formato:* `#,0.0`

Tiempo medio entre fallas, en horas operativas. Sube cuando la confiabilidad mejora.

```dax
MTBF =
VAR Fallas =
    CALCULATE(
        COUNTROWS('Eventos de paro'),
        'Paro'[codigo_paro] IN {"01", "02"}
    )
RETURN
    DIVIDE([Horas operativas], Fallas)
```

### `MTTR`

*Tabla:* `Eventos de paro` · *Formato:* `0.00`

Tiempo medio de reparacion, en horas. Solo cuenta falla electromecanica (01) y espera de soporte (02), que son las averias reales.

```dax
MTTR =
VAR Fallas =
    CALCULATE(
        [Numero de eventos],
        'Paro'[codigo_paro] IN {"01", "02"}
    )
VAR HorasReparacion =
    CALCULATE(
        [Horas perdidas],
        'Paro'[codigo_paro] IN {"01", "02"}
    )
RETURN
    DIVIDE(HorasReparacion, Fallas)
```

---

## 07 Gobierno del dato

### `Indice de completitud del registro`

*Tabla:* `Produccion por turno` · *Formato:* `0.0%`

INDICADOR NUEVO. Mide que tan completo llega el formato hora a hora. Pasa de 0% en 2022 a 100% en 2025, y explica por que el Rendimiento no es calculable antes de 2023. Sin este indicador, cualquier conclusion del tablero es fragil.

```dax
Indice de completitud del registro =
VAR Turnos = [Turnos registrados]
VAR ConOperario =
    CALCULATE([Turnos registrados],
        'Produccion por turno'[operario_no_informado] = FALSE())
VAR ConReferencia =
    CALCULATE([Turnos registrados],
        'Produccion por turno'[referencia_no_informada] = FALSE())
VAR ConTurno =
    CALCULATE([Turnos registrados],
        'Produccion por turno'[turno_imputado] = FALSE())
VAR ConEstandar =
    CALCULATE([Turnos registrados],
        'Produccion por turno'[tiene_estandar] = TRUE())
RETURN
    DIVIDE(ConOperario + ConReferencia + ConTurno + ConEstandar + 0, Turnos * 4)
```

### `Turnos registrados`

*Tabla:* `Produccion por turno` · *Formato:* `#,0`

Numero de turnos cargados.

```dax
Turnos registrados =
COUNTROWS('Produccion por turno')
```

### `Turnos sin estandar`

*Tabla:* `Produccion por turno` · *Formato:* `#,0`

Turnos para los que no existe estandar de ingenieria, asi que no entran al calculo del Rendimiento.

```dax
Turnos sin estandar =
CALCULATE([Turnos registrados],
    'Produccion por turno'[tiene_estandar] = FALSE())
```
