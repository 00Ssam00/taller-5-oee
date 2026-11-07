# Propuesta de evolución: si el dato llegara desde PLC/SCADA

## 1. El punto de partida

Hoy el dato recorre este camino, descrito en el apartado 4.1 del P-MTO-22:

```
operaria escribe a mano  →  producción recoge el formato  →  mantenimiento
lo remite  →  mantenimiento lo digita en el Excel  →  informe mensual
```

Son **cuatro traspasos manuales** y una latencia de días o semanas. Eso explica
casi todos los problemas documentados en el
[diagnóstico](02-diagnostico-de-la-fuente.md): los 42 duplicados, las 45
variantes de escritura de un mismo subcódigo, los turnos de 32 horas, los paros
de 15,63 h en turnos de 8, y que en 2022 no haya ni un registro con operario.

**La buena noticia:** el modelo dimensional ya está preparado. La tabla
`dw.hecho_produccion_hora` existe, tiene el grano horario que entregaría un
historiador, incluye una columna `unidades_rechazadas` que el Excel no tiene, y
el tablero de Grafana ya consume de ella. Lo que hoy la alimenta es el
simulador; mañana sería el PLC. **El modelo no cambia.**

---

## 2. Qué se instrumenta y qué resuelve cada cosa

| Señal | Sensor | Qué problema resuelve |
|---|---|---|
| **Contador de unidades en la salida** | Fotocélula o encoder ya presente en la mayoría de líneas de envasado | Elimina la digitación de pacas. Acaba con los 22 turnos de rendimiento implausible |
| **Estado de marcha / parada** | Señal del variador o del contactor principal | Elimina la digitación de minutos de paro. Acaba con los paros mayores que el turno |
| **Unidades rechazadas** | Fotocélula en el expulsor, o báscula de control | **Convierte el componente Calidad del OEE en una medición real.** Hoy es un proxy basado en 9,05 h de reproceso en todo el histórico |
| **Causa del paro** | **Pantalla HMI en la línea** con los 18 códigos y sus subcódigos | Es el punto crítico; ver abajo |
| **Referencia en proceso** | Orden de producción desde el ERP, o lectura de código de barras | Elimina las 52 variantes de escritura y las 2.390 filas sin referencia |
| **Presión de aire y energía** | Transductores en la red de aire comprimido | Automatiza el código 03 y permite correlacionar caídas de presión con paros de otros códigos |

### 2.1. La causa del paro sigue necesitando a una persona

Es el punto que conviene no prometer de más. Un PLC sabe **que** la máquina
paró y **cuánto** tiempo, pero no **por qué**. Distinguir «ajuste operativo»
de «falla del sistema dosificador» es un juicio humano.

La propuesta: **el PLC detecta el paro y la HMI pregunta la causa.** En cuanto
la línea se detiene más de un umbral (30 s, por ejemplo), la pantalla muestra
los 18 códigos y, al elegir 01, 03 o 05, despliega el árbol de subcódigos. El
operario toca dos botones y la duración ya está medida por el autómata.

Ventajas sobre el formato en papel:

- **La duración deja de depender de la memoria.** El operario ya no estima «unos
  15 minutos».
- **El subcódigo se elige de una lista**, no se escribe. Desaparecen las 45
  variantes de escritura y las dos taxonomías conviviendo.
- **El dato no se puede duplicar**, porque cada paro tiene su marca de tiempo.
- **Lo registra quien ve el problema**, no quien digita días después.
- **Es obligatorio y bloqueante**: la línea no se reporta como productiva hasta
  que se clasifique el paro. Eso resuelve las 5.020 apariciones de «Sin
  especificar» mejor que cualquier regla de limpieza.

---

## 3. Arquitectura propuesta

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  NIVEL 0-1 · PLANTA                                             │
  │  Sensores (contador, marcha/parada, rechazo, presión)           │
  │  PLC por línea  +  HMI para clasificar el paro                  │
  └───────────────────────────┬─────────────────────────────────────┘
                              │ OPC UA  (estándar industrial)
  ┌───────────────────────────▼─────────────────────────────────────┐
  │  NIVEL 2 · SUPERVISIÓN                                          │
  │  Servidor OPC UA  →  historiador de series de tiempo            │
  │  (TimescaleDB, que es una extensión de PostgreSQL)              │
  └───────────────────────────┬─────────────────────────────────────┘
                              │ ETL incremental, cada 5 min
  ┌───────────────────────────▼─────────────────────────────────────┐
  │  NIVEL 3 · ALMACÉN  (lo que ya existe)                          │
  │  dw.hecho_produccion_hora   ← del historiador                   │
  │  dw.hecho_produccion_turno  ← agregado desde la hora            │
  │  dw.hecho_paro              ← un evento por paro, con su causa   │
  │  Las dimensiones conformadas NO cambian                         │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
  ┌───────────────────────────▼─────────────────────────────────────┐
  │  NIVEL 4 · CONSUMO  (sin cambios)                               │
  │  Grafana (operativo)   ·   Power BI (analítico)                 │
  └─────────────────────────────────────────────────────────────────┘
```

### 3.1. Por qué OPC UA

Es el estándar de interoperabilidad industrial: lo hablan Siemens, Allen
Bradley, Schneider y Omron. Usar el protocolo propietario de un fabricante
ataría el proyecto a esa marca, y en una planta con líneas de distinta
procedencia eso es un problema a los dos años.

### 3.2. Por qué TimescaleDB y no otra base

**Porque es una extensión de PostgreSQL, no otra base de datos.** Convierte
`hecho_produccion_hora` en una *hypertable* particionada por tiempo, con
compresión y agregados continuos, **sin cambiar una sola consulta**: el mismo
SQL, los mismos roles, el mismo datasource de Grafana, el mismo modelo de Power
BI. Introducir InfluxDB o Prometheus obligaría a mantener dos motores, dos
lenguajes de consulta y dos esquemas de permisos.

### 3.3. Qué habría que tocar en el proyecto actual

| Componente | Cambio |
|---|---|
| `dw.hecho_produccion_hora` | Ninguno en la estructura. Pasa a *hypertable* |
| `dw.hecho_produccion_turno` | Deja de cargarse del Excel y pasa a ser un **agregado continuo** de la tabla horaria |
| `dw.hecho_paro` | Igual, pero con marca de tiempo de inicio y fin reales en vez de minutos totales por turno |
| Dimensiones | **Sin cambios.** Son conformadas y ya están |
| ETL | Cambia la extracción (OPC UA en vez de `openpyxl`) y pasa a incremental. **Las reglas de calidad y la conciliación se conservan**: seguirán haciendo falta, porque un sensor sucio también miente |
| Simulador | Se retira. Su función era precisamente ocupar el lugar del PLC |
| Grafana | **Sin cambios.** Ya lee la tabla horaria |
| Power BI | **Sin cambios** en el modelo. Solo gana granularidad |
| `dim_fecha` | Habría que añadir una dimensión de **hora del día** si se quiere analizar patrones intradía |

El diseño del modelo dimensional es, en este sentido, la inversión que sobrevive
al cambio de fuente.

---

## 4. Lo que se gana, por orden de valor

### 4.1. El componente Calidad del OEE deja de ser un proxy

Es la ganancia mayor. Hoy la Calidad se estima con el tiempo de reproceso y da
un valor cercano al 100 % que con casi total seguridad es optimista. Con una
fotocélula en el expulsor el OEE pasa a ser **el OEE de verdad**, y la planta
descubre cuánto le cuesta producir mal, que es un número que hoy **no existe**.

### 4.2. El OEE se vuelve accionable dentro del turno

Un paro de 20 minutos hoy se conoce la semana siguiente. Con dato en línea, la
alerta de OEE crítico —ya construida y probada— llega al supervisor mientras el
turno está corriendo. Un turno de 8 horas tiene 480 minutos: avisar en el minuto
30 en lugar del día siguiente es la diferencia entre corregir y lamentar.

### 4.3. Micro-paros

El formato actual no puede registrar un paro de 40 segundos: nadie lo anota. En
una línea de envasado los micro-paros son una de las pérdidas más grandes y más
invisibles. Un PLC los cuenta todos. Es probable que al instrumentar, el OEE
medido **baje**, y eso sería una buena señal: significaría que se dejó de
contar como productivo un tiempo que no lo era.

### 4.4. Se liberan horas de mantenimiento

Hoy alguien del área digita 8.208 filas en el Excel. Ese trabajo desaparece, y
es tiempo de un técnico que puede dedicarse a mantener máquinas.

### 4.5. El dato queda auditable por construcción

Ni duplicados, ni variantes de escritura, ni turnos de 32 horas. Los problemas
que hoy exigen 21 reglas de limpieza dejan de existir en el origen, que es
donde hay que resolverlos.

---

## 5. Plan por fases

| Fase | Alcance | Qué habilita |
|---|---|---|
| **0 · Ya hecho** | Modelo dimensional, ETL, tableros, alerta | Medir OEE con el dato que existe y cuantificar las brechas |
| **1 · Piloto en una línea** | Contador y marcha/parada en Vinilos_1, la de peor OEE sostenido (49,7 % en 2023 y 48,7 % en 2024). HMI con los 18 códigos | Comparar el dato automático con el manual **sobre la misma línea y el mismo turno**. Es la validación que justifica el resto de la inversión |
| **2 · Extensión** | Las cuatro líneas, más la referencia desde el ERP | OEE horario real en toda la planta |
| **3 · Calidad** | Detección de rechazo en el expulsor | El componente Calidad deja de ser un proxy. **OEE completo y auditable** |
| **4 · Servicios** | Presión de aire y energía | Automatiza el código 03 y permite correlacionar la caída de presión con los paros de otros códigos |
| **5 · Analítica avanzada** | Modelos de predicción de falla sobre el histórico horario | Mantenimiento predictivo. **Requiere las fases anteriores**: sin años de dato horario fiable no hay nada que entrenar |

### Por qué empezar por Vinilos_1

Porque es donde el argumento se defiende solo. Su disponibilidad cayó de
**89,7 % (2022) a 65,7 % (2024)** y su OEE lleva dos años por debajo del umbral
crítico: **49,7 % en 2023 y 48,7 % en 2024**. Al mismo tiempo, Vinilos_3 y
Vinilos_4 sostienen 72–74 % con los mismos equipos y el mismo producto, de modo
que la brecha no se explica por el equipo.

En el primer trimestre de 2025 Vinilos_1 repunta a 66,8 %, pero sobre **95
turnos** frente a los 451 de 2024: es un año parcial y una base demasiado
pequeña para concluir que el problema se resolvió. Precisamente por eso conviene
instrumentarla: hoy no hay forma de saber si mejoró la línea o solo cambió lo
que se le cargó.

Si el piloto demuestra en una línea que el dato automático revela pérdidas que
el formato en papel no veía, la extensión a las otras tres deja de ser una
discusión.

---

## 6. Lo que no resuelve la instrumentación

Conviene ser explícito, porque prometer de más es la forma más rápida de perder
credibilidad en el comité:

- **No mejora el OEE por sí misma.** Medir mejor no produce más. Lo que hace es
  que las decisiones se tomen sobre hechos.
- **No elimina el juicio humano** en la causa del paro, solo lo ordena y lo
  pone en el momento y el lugar correctos.
- **No sirve si nadie mira el tablero.** El circuito se cierra cuando la
  operaria recibe retroalimentación y el supervisor actúa sobre la alerta. Eso
  es un cambio de hábito, no de tecnología.
- **No arregla el histórico.** Los datos de 2022 a 2025 seguirán teniendo las
  limitaciones documentadas. El OEE comparable empieza el día que se
  instrumenta, y conviene decirlo antes de que alguien compare un OEE de 2024
  con uno de 2027 y crea que la planta empeoró.
