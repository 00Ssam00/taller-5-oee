# Power BI y Grafana: por qué hacen falta los dos

La pregunta que hay que responder no es «cuál es mejor», sino **por qué no se
intercambian**. Las dos herramientas leen la misma base de datos, así que la
diferencia no está en el dato: está en el tipo de pregunta.

---

## 1. La distinción de fondo

> **Grafana responde «¿qué está pasando?». Power BI responde «¿qué está
> cambiando?».**

Son dos problemas técnicos distintos:

- **«Qué está pasando»** necesita el **último** dato y lo necesita ya. El
  horizonte es de minutos y la consulta toca pocas filas recientes. La
  pregunta no admite espera.
- **«Qué está cambiando»** necesita **todo el histórico** y compararlo contra
  un periodo anterior. El horizonte es de meses y la consulta recorre años de
  datos. La pregunta no admite imprecisión.

Casi todo lo demás se deduce de ahí.

---

## 2. Comparación

| | **Grafana** | **Power BI** |
|---|---|---|
| **Pregunta que resuelve** | ¿Qué línea está en rojo **ahora** y qué la está frenando? | ¿Cómo evolucionó el OEE y por qué, comparado con el año pasado? |
| **Usuario** | U1 operaria, U2 supervisor de turno, U3 coordinador de mantenimiento (uso diario) | U3 (informe mensual), U4 jefe de producción, U5 gerencia |
| **Horizonte** | Las últimas 24 horas | 2022–2025, con comparativos interanuales |
| **Frecuencia de actualización** | **10 segundos** (consulta directa a PostgreSQL) | **Importación**, refresco diario o a demanda |
| **Grano que consume** | `hecho_produccion_hora` (hora × máquina) | `hecho_produccion_turno` y `hecho_paro` (turno y evento) |
| **Dónde se mira** | Pantalla fija en el piso de planta | Portátil, en una reunión |
| **Interacción** | Mirar. Como mucho, cambiar una variable | Explorar: segmentar, hacer drill-down, cruzar |
| **Modelo de datos** | Ninguno: SQL directo sobre vistas | Modelo semántico con 10 relaciones, 2 jerarquías y 36 medidas DAX |
| **Alertas** | **Sí**, nativas y con estado (Normal → Pending → Firing) y notificación saliente | No en el escritorio; requiere el servicio en la nube |
| **Cálculos complejos** | Lo que quepa en SQL | DAX: inteligencia de tiempo, contexto de filtro, Pareto acumulado |
| **Versionado** | JSON del tablero + YAML de provisioning | PBIP/TMDL (texto) |
| **Costo** | Libre, en el contenedor | Licencia; Desktop gratis, publicar requiere Pro |

---

## 3. Por qué Grafana no puede hacer el trabajo de Power BI

### 3.1. No tiene modelo semántico

Grafana ejecuta SQL y dibuja el resultado. **No hay capa semántica**: cada panel
lleva su propia consulta. Consecuencias concretas:

- La definición del OEE queda **repetida en cada panel**. Si mañana se decide
  excluir los paros planeados del denominador, hay que editar los paneles uno
  por uno. En Power BI se cambia **una** medida DAX y se propaga a todo el
  informe.
- **No hay contexto de filtro.** El `% acumulado de tiempo perdido` del Pareto
  en DAX se recalcula solo cuando el usuario filtra por máquina o por mes,
  porque la medida se evalúa en el contexto vigente. En Grafana hay que escribir
  la función de ventana en el SQL del panel, y solo funciona para las
  variables que ese panel contemple.

### 3.2. La inteligencia de tiempo es manual

`SAMEPERIODLASTYEAR` y `TOTALYTD` resuelven en una línea el problema de
comparar contra el año anterior respetando años bisiestos, meses incompletos y
el filtro vigente. En Grafana hay que escribirlo en SQL —por eso `dim_fecha`
trae `fecha_key_anio_ant` precalculada— y no responde a los filtros del
usuario.

### 3.3. No se explora, se mira

Un tablero de Grafana está pensado para leerse de un vistazo. No tiene
drill-down por jerarquías, ni tablas cruzadas, ni la capacidad de que un
gerente pregunte «¿y si miro solo el turno de noche de Vinilos_2 en el segundo
semestre?» sin que alguien le reprograme un panel.

### 3.4. Importar frente a consultar

Grafana consulta **en vivo**, que es su virtud y su límite. Un panel que
recorriera 5.138 turnos × 16.482 paros con funciones de ventana sobre tres años
tardaría segundos en cada refresco, y con refresco de 10 s castigaría a la base
sin motivo: **el histórico de 2023 no cambia**. Power BI importa el modelo a
memoria y lo recorre al instante.

---

## 4. Por qué Power BI no puede hacer el trabajo de Grafana

### 4.1. No tiene alertas en el escritorio

Es la razón decisiva. Un supervisor no mira una pantalla todo el turno: hay que
**avisarle**. El proyecto lo demuestra de punta a punta: la alerta de OEE
crítico pasa por `Normal → Pending → Firing`, y la notificación llega a su
destinatario con la línea afectada, el valor y el umbral.

Power BI Desktop no alerta. Las alertas de Power BI requieren publicar en el
servicio en la nube, con licencia Pro, y se evalúan **cada 15 minutos como
máximo** sobre un modelo que puede llevar horas sin refrescar. Para un paro de
12 minutos eso no sirve.

### 4.2. La latencia es estructural, no un ajuste

Power BI **importa**. Entre el momento productivo y la cifra en pantalla hay un
refresco de por medio: en Desktop, cuando alguien lo pulsa; publicado, hasta 8
refrescos programados al día con licencia Pro. El modo DirectQuery reduce la
latencia pero inutiliza buena parte de DAX y vuelve lenta la exploración.

Grafana consulta con `$__timeFilter(instante)` cada 10 segundos. La diferencia
entre 10 segundos y 3 horas no es de grado: decide si el dato sirve para actuar
durante el turno.

### 4.3. No corre en el piso de planta

El tablero operativo tiene que vivir en una pantalla fija, encendida todo el
turno, sin que nadie inicie sesión. Grafana es una página web: se abre y se
deja. Power BI Desktop es una aplicación de Windows que exige una licencia por
usuario y una sesión abierta.

### 4.4. No es contenerizable

Power BI Desktop solo existe para Windows y no se contenedoriza, de ahí que en
esta arquitectura corra en el anfitrión. Grafana es parte de la pila y se
levanta con el mismo comando, con su tablero y su alerta ya cargados por
provisioning.

---

## 5. Cómo se reparten el trabajo sin duplicarlo

El riesgo de tener dos herramientas es que den números distintos. Se evita con
tres reglas:

1. **Una sola fuente de verdad.** Las dos leen `dw` con el rol `bi_lectura`.
   Ninguna lee el Excel y ninguna guarda su propia copia transformada.
2. **Las definiciones viven en la base de datos.** `naturaleza_paro`,
   `tiene_estandar`, `rendimiento_implausible` y los componentes del OEE se
   calculan en el ETL y se almacenan. Grafana y Power BI **consumen** la
   definición, no la reimplementan. Si mañana cambia el criterio de qué paro es
   planeado, se cambia en un sitio.
3. **Cada tablero tiene su grano.** Grafana lee `hecho_produccion_hora`
   (telemetría); Power BI lee `hecho_produccion_turno` y `hecho_paro`
   (histórico auditado). No compiten por el mismo dato.

### Reparto por indicador

| Indicador | Grafana | Power BI |
|---|---|---|
| Semáforo de estado actual por línea | ✓ | |
| Líneas sin reportar | ✓ | |
| OEE y componentes de la última hora | ✓ | |
| Minutos de paro por hora y causa | ✓ | |
| Pareto del turno en curso | ✓ | |
| Alerta de OEE crítico | ✓ | |
| OEE mensual y anual por línea | | ✓ |
| Comparativo interanual | | ✓ |
| OEE acumulado del año | | ✓ |
| Drill-down de la jerarquía de paros | | ✓ |
| Pareto del histórico | | ✓ |
| MTBF y MTTR | | ✓ |
| Rendimiento por referencia | | ✓ |
| Utilización del calendario | | ✓ |
| Índice de completitud del registro | | ✓ |

El **Pareto aparece en las dos**, y no es una duplicación: en Grafana es el
Pareto del rango seleccionado, para decidir a qué atender ahora; en Power BI es
el del histórico, con el porcentaje acumulado recalculándose según los filtros,
para decidir el plan de mantenimiento del trimestre. Misma forma de gráfico,
decisiones distintas.

---

## 6. Qué pasaría si se eligiera solo una

**Solo Grafana.** Se mantiene la operación diaria, pero el comité mensual
vuelve al Excel, porque Grafana no compara periodos con soltura ni permite
explorar. Y se perdería el drill-down de la jerarquía de paros, que es donde
está el hallazgo del sistema dosificador.

**Solo Power BI.** Se tiene un informe gerencial excelente y **la planta sigue
sin saber que una línea está parada**. El circuito de retroalimentación con la
operaria —hoy inexistente: entrega el formato en papel y nunca ve el
resultado— seguiría sin cerrarse. Y sin alertas, el valor del dato near real
time se pierde por completo.

Dicho de otro modo: Power BI mejora **las decisiones del mes**; Grafana mejora
**las decisiones del turno**. La planta pierde dinero en los dos horizontes.
