# Catálogo de indicadores

Cada indicador lleva fórmula, unidad, granularidad, meta o umbral, fuente del
dato y el usuario que lo consume (los códigos `U1`–`U5` y `P1.1`–`P5.5`
remiten a [01-usuarios-y-preguntas-de-negocio.md](01-usuarios-y-preguntas-de-negocio.md)).

Los indicadores están separados en dos bloques porque el enunciado pide
distinguirlos: **A)** los que el P-MTO-22 ya reporta hoy, que hay que seguir
entregando para no romper la continuidad del informe mensual; y **B)** los
nuevos, cada uno con su justificación.

---

## A. Indicadores que el P-MTO-22 ya reporta hoy

Estos tres se replican con la **misma fórmula** que usa el Excel. Se verificó
la equivalencia reproduciéndolos desde los datos crudos y comparándolos **a
seis decimales** contra las tres tablas dinámicas del libro: 35 contrastes,
todos coincidentes. Eso permite decirle a la gerencia «es el mismo indicador
que viene viendo», que es condición para que acepte el resto.

### A1 · % Productividad (por máquina, mes y año)

| | |
|---|---|
| **Fórmula** | `1 − (tiempo de paro / horas trabajadas)` |
| **Unidad** | Porcentaje |
| **Granularidad** | Máquina × mes; máquina × año |
| **Meta** | No había meta formal. Se propone **80 %** |
| **Fuente** | `dw.hecho_produccion_turno`: `horas_paro_total`, `horas_programadas` |
| **Consumido por** | U3, U5 (informe mensual del comité) |
| **Equivalencia** | **Es exactamente la Disponibilidad del OEE** (B1). Se mantiene el nombre antiguo como alias para la transición |
| **Verificación** | TD_prodMaq, Vinilos_2 2024: 0,624722 en el Excel y 0,624722 en el modelo |

### A2 · Participación de cada código de paro

| | |
|---|---|
| **Fórmula** | `horas del código / horas trabajadas del periodo` |
| **Unidad** | Porcentaje |
| **Granularidad** | Máquina × código de paro × año |
| **Umbral** | Ninguno; es descriptivo |
| **Fuente** | `dw.hecho_paro` con `dw.dim_paro` |
| **Consumido por** | U3, U4 |
| **Verificación** | TD_prodCodigo, Vinilos_2 2024: coincide a 6 decimales en los 18 códigos |

### A3 · Horas trabajadas y pacas producidas

| | |
|---|---|
| **Fórmula** | `SUM(horas_trabajadas)`, `SUM(pacas_producidas)` |
| **Unidad** | Horas; pacas |
| **Granularidad** | Máquina × mes × año |
| **Fuente** | `dw.hecho_produccion_turno` |
| **Consumido por** | U4, U5 |
| **Verificación** | Hoja4, horas 2023: V1 3.390,0 · V2 1.220,5 · V3 4.221,3 · V4 4.002,55, idénticas |
| **Nota** | El modelo entrega la cifra **depurada**. La del Excel está inflada en 129 h y 1.019 pacas por 42 duplicados exactos |

---

## B. Indicadores nuevos

### B1 · Disponibilidad

| | |
|---|---|
| **Fórmula** | `horas_operativas / horas_programadas` |
| **Unidad** | Porcentaje |
| **Granularidad** | Turno (base); se agrega a máquina × mes × año |
| **Meta** | **80 %** |
| **Fuente** | `dw.hecho_produccion_turno` |
| **Consumido por** | U2 (P2.2), U3, U5 |

**Por qué es nuevo aunque el Excel ya lo calcule:** el número es el mismo que
A1, pero el *nombre* importa. Llamarlo «Disponibilidad» obliga a admitir que
hay otros dos componentes y que hoy no se miden. Mientras se llame
«productividad», la planta cree que ya mide todo.

### B2 · Rendimiento

| | |
|---|---|
| **Fórmula** | `unidades_producidas / (tasa_ideal × 60 × horas_operativas)` |
| **Unidad** | Porcentaje |
| **Granularidad** | Turno; se agrega a máquina × mes × año |
| **Meta** | **95 %** |
| **Fuente** | `hecho_produccion_turno` × `dim_estandar` (tasa ideal de `Tablas Desplegables`) |
| **Consumido por** | U2 (P2.2), U4 (P4.1), U5 |

**Justificación.** Es el componente que falta y el que explica la brecha
oculta. El denominador usa el tiempo **operativo**, no el programado, para no
contar dos veces la pérdida por paro: el tiempo parado ya lo castiga la
Disponibilidad.

Solo se calcula si hay estándar de ingeniería y si el valor es plausible
(≤ 150 % del máximo teórico). Si no, devuelve NULL: **nunca se inventa un
valor**. Esto deja 2.686 de 5.138 turnos sin Rendimiento, casi todos de 2022,
y eso es información, no una carencia.

### B3 · Calidad (proxy declarado)

| | |
|---|---|
| **Fórmula** | `1 − (unidades equivalentes de reproceso / unidades producidas)` |
| **Unidad** | Porcentaje |
| **Granularidad** | Turno |
| **Meta** | **99 %** |
| **Fuente** | Tiempo del código 11 (Reproceso), convertido a unidades con la tasa ideal |
| **Consumido por** | U2, U5 |

**Justificación y advertencia.** La fuente **no registra unidades
defectuosas**, de modo que este componente no es medible. El proxy usa las
9,05 horas de reproceso de todo el histórico, lo que da una calidad cercana al
100 % que con casi total seguridad es optimista. Es una **cota inferior de la
pérdida**: el OEE real no puede ser mejor que este. Se reporta siempre al lado
del OEE auditable (B4) para que se vea cuánto pesa la estimación. Cerrarlo
requiere instrumentación, no analítica.

### B4 · OEE auditable  ·  **indicador principal del proyecto**

| | |
|---|---|
| **Fórmula** | `Disponibilidad × Rendimiento`, con los dos factores medidos sobre los **mismos** turnos |
| **Unidad** | Porcentaje |
| **Granularidad** | Turno; se agrega a máquina × mes × año |
| **Población** | Turnos con estándar de ingeniería y rendimiento plausible. Se declara siempre la **cobertura**: 0 % en 2022, 17–30 % en 2023, 70–91 % en 2024 y 48–100 % en 2025 |
| **Regla de agregación** | **Razón de sumas**, nunca el promedio de los OEE por turno |
| **Meta** | **65 %** · **Umbral crítico 50 %** (dispara la alerta de Grafana) |
| **Fuente** | B1 × B2 |
| **Consumido por** | U2, U3, U5 (P5.1, P5.2) |

**Justificación de la meta del 65 %.** No es un número de manual. Es el nivel
que **Vinilos_3 y Vinilos_4 ya sostienen** (74,4 % y 72,3 % en 2024) con los
mismos equipos y el mismo producto. Una meta que dos de las cuatro líneas ya
superan es demostradamente alcanzable, y eso quita la discusión de si el
objetivo es realista.

**Justificación del umbral crítico del 50 %.** Es la frontera en la que dos
líneas llevan años: **Vinilos_1 está en 49,7 % (2023) y 48,7 % (2024)**, y
**Vinilos_2 en 45,7 % (2023) y 48,3 % en 2025**. Alertar por debajo de ese
valor avisa de un problema real y no de ruido. Además, por debajo del 50 % la línea produce menos de la
mitad de su capacidad mientras consume el 100 % de la mano de obra del turno,
la energía y el aire comprimido: deja de cubrir su costo de operación.

**Por qué los dos factores se miden sobre los mismos turnos.** La
Disponibilidad se puede calcular en cualquier turno, porque solo necesita
horas. El Rendimiento no: exige un estándar de ingeniería, y la fuente solo lo
trae en una parte de los registros. Si se multiplica la Disponibilidad de
*todos* los turnos por el Rendimiento de *unos pocos*, el resultado no describe
ninguna operación real. En Vinilos_1 2023, donde solo el 28 % de los turnos
trae estándar, esa mezcla daba un OEE del **62,0 %** frente al **49,7 %**
correcto, y fabricaba una «caída» de 13 puntos entre 2023 y 2024 que nunca
ocurrió: la línea lleva dos años plana. Por eso el indicador restringe los dos
factores al mismo subconjunto y publica al lado su cobertura.

Hay un hallazgo adicional en esa restricción: en 2023 los turnos **con**
estándar tienen peor disponibilidad que el conjunto (61,4 % contra 76,6 % en
Vinilos_1). El registro del estándar no era aleatorio. En 2024, con la
cobertura por encima del 70 %, ambas cifras ya convergen (66,1 % y 65,7 %).

**Por qué razón de sumas y no promedio de los OEE por turno.** El OEE es un
producto de dos ratios: el promedio de los productos no es el producto de los
promedios. Agregarlo desde los sumandos (horas y unidades) es lo único que da
el mismo valor a cualquier nivel de la jerarquía y lo único que concilia contra
los totales de la fuente. Las dos definiciones se diferencian aquí en menos de
un punto, pero solo una es reproducible desde la tabla de hechos.

**Por qué se reporta `D × R` y no los tres componentes:** porque sus dos
factores se miden con el dato de la fuente, sin estimar nada. El OEE con los
tres (B5) se publica al lado, pero el que sostiene una decisión de inversión es
el auditable.

### B5 · OEE completo

| | |
|---|---|
| **Fórmula** | `Disponibilidad × Rendimiento × Calidad (proxy)` |
| **Unidad** | Porcentaje |
| **Granularidad** | Turno |
| **Meta** | 65 % |
| **Consumido por** | U5 |

**Justificación.** Es la definición canónica de OEE. Se entrega para no
inventar una métrica propia, pero marcada como dependiente de un proxy.

### B6 · Tiempo perdido evitable

| | |
|---|---|
| **Fórmula** | `SUM(horas_paro)` donde la naturaleza del código es «No planeado» |
| **Unidad** | Horas; y `% de paro evitable` sobre el total |
| **Granularidad** | Máquina × código × mes |
| **Meta** | Reducir un 20 % interanual |
| **Fuente** | `dw.hecho_paro` × `dim_paro.naturaleza_paro` |
| **Consumido por** | U3 (P3.5), U5 (P5.4) |

**Justificación.** Sin esta separación el OEE castiga a la planta por hacer
lo correcto: el mantenimiento preventivo, la capacitación y la pausa activa
bajan el indicador igual que una avería. El dato del histórico: **64,9 % del
tiempo perdido (5.468 h) es evitable** y 35,1 % (2.963 h) es programado.

### B7 · Tiempo perdido por sistema físico de la máquina  ·  **el hallazgo**

| | |
|---|---|
| **Fórmula** | `SUM(horas_paro)` agrupado por `dim_paro.nombre_sistema` |
| **Unidad** | Horas; porcentaje del total |
| **Granularidad** | Sistema × máquina × mes |
| **Umbral** | Revisar cualquier sistema que supere el 15 % del tiempo perdido |
| **Fuente** | Atributo conformado `dim_paro.codigo_sistema`, construido por el equipo |
| **Consumido por** | U3 (P3.2) |

**Justificación.** Es el indicador que **el Excel no puede calcular**, y el de
mayor valor práctico. Las ramas de subcódigos 1.x (falla electromecánica), 3.x
(servicios) y 5.x (ajuste operativo) viven en columnas separadas, así que nadie
puede sumar lo que cuesta un sistema concreto. Al unificarlas:

Sobre las **2.222,8 h** de los códigos 01, 03 y 05, que son los únicos con
árbol de causa raíz:

| Sistema | Horas | % de 01/03/05 | % acum. | % del total perdido |
|---|---|---|---|---|
| Sistema de dosificación de pintura | 992,0 | **44,6 %** | 44,6 % | 11,8 % |
| Sistema de tapado (transfer y pisador) | 272,8 | 12,3 % | 56,9 % | 3,2 % |
| Sistema alimentador de tapa y tobogán | 194,4 | 8,7 % | 65,6 % | 2,3 % |
| Sistema Video Jet (codificado) | 188,5 | 8,5 % | 74,1 % | 2,2 % |
| Sistema etiquetadora | 165,9 | 7,5 % | **81,6 %** | 2,0 % |

**Un solo sistema explica el 44,6 % del tiempo perdido con causa raíz
identificable y cinco explican el 81,6 %.** Eso convierte una lista de 18
códigos en una decisión concreta de ingeniería.

> **El denominador importa.** El porcentaje es sobre las 2.222,8 h de los tres
> códigos que tienen subcódigos, no sobre las 8.431,5 h totales: los otros 15
> códigos no registran el sistema afectado, así que atribuirles un sistema sería
> inventarlo. En términos del total perdido, el dosificador pesa el **11,8 %**,
> que sigue siendo el sistema más costoso de la planta con diferencia.

### B8 · MTBF y MTTR

| | |
|---|---|
| **Fórmula** | `MTBF = horas_operativas / nº de fallas` · `MTTR = horas de reparación / nº de fallas` |
| **Unidad** | Horas |
| **Granularidad** | Máquina × año |
| **Meta** | MTBF creciente interanual; MTTR < 1 h |
| **Fuente** | `dw.hecho_paro` restringido a los códigos 01 y 02 |
| **Consumido por** | U3 (P3.3, P3.4) |

**Justificación.** Son el lenguaje estándar de mantenimiento y distinguen dos
problemas distintos que el tiempo total confunde: *fallar mucho* (MTBF bajo) y
*tardar en arreglar* (MTTR alto). El primero se resuelve con rediseño o
preventivo; el segundo, con repuestos y formación. Solo cuentan los códigos 01
y 02 porque son las averías reales.

### B9 · Utilización del calendario y TEEP

| | |
|---|---|
| **Fórmula** | `horas_programadas / (días del año × 24)` |
| **Unidad** | Porcentaje |
| **Granularidad** | Máquina × año |
| **Umbral** | Informativo |
| **Consumido por** | U5 (P5.3) |

**Justificación.** El OEE mide qué tan bien se usa el tiempo **que se
programó**; este indicador mide **cuánto no se programó**, que es una decisión
comercial y no de mantenimiento. Separarlos evita una conversación falsa: en
2024 Vinilos_4 programó el 60,3 % del calendario y Vinilos_2 solo el 22,0 %.
Mejorar el OEE de Vinilos_2 no sirve de nada si el problema es que no hay
órdenes que cargarle.

### B10 · Unidades no producidas por paro

| | |
|---|---|
| **Fórmula** | `tasa_ideal × 60 × horas_paro` |
| **Unidad** | Unidades |
| **Granularidad** | Evento de paro |
| **Consumido por** | U5 (P5.4) |

**Justificación.** Traduce horas técnicas a lenguaje de negocio. «Perdimos
1.069 horas» no mueve a nadie en un comité; «dejamos de envasar X millones de
unidades» sí.

### B11 · Índice de completitud del registro  ·  **gobierno del dato**

| | |
|---|---|
| **Fórmula** | Promedio de cuatro proporciones: con operario, con referencia, con turno informado y con estándar disponible |
| **Unidad** | Porcentaje |
| **Granularidad** | Máquina × año |
| **Meta** | **95 %** |
| **Fuente** | Banderas de calidad de `dw.hecho_produccion_turno` |
| **Consumido por** | U3 (P3.6), U5 (P5.5) |

**Justificación.** Es el indicador que sostiene a todos los demás. Pasa de
**0 % en 2022 a 95 % en 2025** y explica por qué el Rendimiento no es
calculable antes de 2023. Sin él, cualquier conclusión del tablero es frágil, y
con él la conversación sobre disciplina de registro deja de ser una opinión.

### B12 · Costo del cambio de referencia

| | |
|---|---|
| **Fórmula** | `horas del código 07 / horas programadas` y `horas por cambio` |
| **Unidad** | Porcentaje; horas por evento |
| **Granularidad** | Máquina × trimestre |
| **Consumido por** | U4 (P4.2) |

**Justificación.** Cuantifica el costo oculto de una mezcla de producto
fragmentada: 620,8 h en 847 cambios, el 7,4 % de todo el tiempo perdido. Hoy
nadie lo mide, y es una decisión de planeación, no de mantenimiento.

### B13 · Semáforo de estado actual por línea

| | |
|---|---|
| **Fórmula** | Verde ≥ 65 %, amarillo 50–65 %, rojo < 50 % de OEE de la última hora |
| **Unidad** | Categoría |
| **Granularidad** | Máquina, última hora reportada |
| **Consumido por** | U1 (P1.3), U2 (P2.1) |

**Justificación.** Es el único indicador pensado para que se lea en dos
segundos desde una pantalla de piso de planta. Va acompañado del panel de
**líneas sin reportar**, porque un tablero en verde porque no llega
información es peor que un tablero en rojo.

---

## Resumen de metas y umbrales

| Indicador | Meta | Umbral crítico | Cómo se justifica la meta |
|---|---|---|---|
| Disponibilidad | 80 % | 65 % | V3 y V4 ya la superaron (82,7 % y 81,9 % en 2023) |
| Rendimiento | 95 % | 85 % | V3 sostiene 96–98 % y V4 94–96 %, luego es alcanzable |
| Calidad (proxy) | 99 % | 97 % | Provisional: depende de medir defectos de verdad |
| **OEE auditable** | **65 %** | **50 %** | V3 y V4 sostienen 72–74 % (2024); V1 y V2 nunca han pasado del 53 % |
| % de paro evitable | < 50 % | — | Hoy está en 64,9 % |
| MTTR | < 1 h | 2 h | — |
| Índice de completitud | 95 % | 80 % | 2025 ya va en 95,3 % |
