# Usuarios y preguntas de negocio

El punto de partida no es el dato sino quién decide. Cada usuario tiene una
frecuencia de consulta y un tipo de decisión distintos, y eso determina en qué
herramienta vive su respuesta.

La fuente de esta identificación es el propio procedimiento **P-MTO-22 V1**
(vigente desde el 14/05/2025), que describe la cadena de personas por las que
pasa el dato: las operarias diligencian el formato hora a hora, producción lo
remite a mantenimiento, mantenimiento lo digita en el Excel, y el coordinador
de mantenimiento socializa un informe mensual «ante los jefes de las demás
áreas y la alta dirección».

---

## U1 · Operaria de la línea de envasado

**Qué decide:** si avisa o no. Es quien ve la máquina.
**Frecuencia:** cada hora, durante el turno.
**Dónde se le responde:** Grafana, en una pantalla de piso de planta.

| # | Pregunta |
|---|---|
| P1.1 | ¿Voy al ritmo que debería, o me estoy quedando atrás? |
| P1.2 | ¿Cuánto tiempo llevo parada en este turno y por qué? |
| P1.3 | ¿Mi línea está peor que las otras tres ahora mismo? |

> **Nota.** Hoy esta usuaria no recibe ninguna información de vuelta: entrega
> el formato en papel y nunca ve el resultado. Es el circuito de
> retroalimentación más corto y más barato de cerrar de todo el proyecto.

## U2 · Supervisor de producción del turno

**Qué decide:** dónde pone al mejor técnico en las próximas dos horas, si para
una línea para limpiarla, si cambia el orden de las órdenes.
**Frecuencia:** varias veces por turno.
**Dónde se le responde:** Grafana.

| # | Pregunta |
|---|---|
| P2.1 | ¿Qué línea está en rojo en este momento y cuál es la causa vigente? |
| P2.2 | ¿El problema es que la máquina está parada, que corre lenta, o que está produciendo reproceso? |
| P2.3 | ¿Alguna línea dejó de reportar dato? |
| P2.4 | ¿Cómo va el turno comparado con las últimas 24 horas? |
| P2.5 | ¿Hay diferencias sostenidas entre el turno de noche y los de día? |

## U3 · Coordinador de mantenimiento

**Qué decide:** el plan semanal de mantenimiento, qué repuestos pide, a qué
sistema le hace intervención de fondo. Es el dueño del P-MTO-22 y quien
presenta el informe mensual.
**Frecuencia:** diaria para operar, mensual para el comité.
**Dónde se le responde:** Grafana para el día, Power BI para el mes.

| # | Pregunta |
|---|---|
| P3.1 | ¿Qué pocas causas explican el 80 % del tiempo perdido? (Pareto) |
| P3.2 | ¿Qué **sistema físico** de la máquina me cuesta más tiempo, sin importar si el tiempo se perdió por falla, por servicios o por ajuste operativo? |
| P3.3 | ¿Cada cuántas horas falla cada línea (MTBF) y cuánto tardo en devolverla a producción (MTTR)? |
| P3.4 | ¿La confiabilidad está mejorando o empeorando respecto del año pasado? |
| P3.5 | ¿Cuánto del tiempo perdido es realmente imputable a mantenimiento? |
| P3.6 | ¿En qué proporción los registros llegan sin causa raíz especificada? |

> **P3.2 es la pregunta que el Excel no puede responder.** Las ramas de
> subcódigos 1.x (falla electromecánica), 3.x (servicios) y 5.x (ajuste
> operativo) viven en columnas separadas de la hoja, así que nadie puede sumar
> el tiempo que cuesta el sistema dosificador. El modelo las une con un
> atributo conformado y la respuesta resulta ser contundente: **el sistema
> dosificador de pintura explica el 44,6 % del tiempo perdido por las causas
> con raíz identificable**: 992 de las 2.222,8 horas de los códigos 01/03/05, y
> el 11,8 % del tiempo perdido total de la planta.

## U4 · Jefe de producción

**Qué decide:** la asignación de referencias a líneas, la secuencia de órdenes,
la formación del personal.
**Frecuencia:** semanal.
**Dónde se le responde:** Power BI.

| # | Pregunta |
|---|---|
| P4.1 | ¿Qué referencias nos alejan más del estándar de ingeniería? |
| P4.2 | ¿Cuánto cuesta el cambio de referencia y conviene agrupar órdenes? |
| P4.3 | ¿Hay diferencias de desempeño entre turnos? |
| P4.4 | ¿Cuánto producto dejamos de envasar por los paros? |

## U5 · Gerencia / alta dirección

**Qué decide:** inversión en equipos, contratación de un turno adicional,
metas del año.
**Frecuencia:** mensual, en el comité.
**Dónde se le responde:** Power BI.

| # | Pregunta |
|---|---|
| P5.1 | ¿Cuál es el OEE de la planta y cómo evolucionó frente al año anterior? |
| P5.2 | ¿Qué línea justifica una inversión y cuál solo necesita disciplina operativa? |
| P5.3 | ¿Cuánta capacidad instalada estamos dejando sin programar? |
| P5.4 | ¿Cuántas unidades dejamos de vender por el tiempo perdido evitable? |
| P5.5 | ¿Podemos confiar en estos números? |

> **P5.5 no es una pregunta retórica.** Hoy el informe que llega al comité
> está inflado por 42 registros duplicados: **+129 horas, +1.019 pacas y
> +18,12 horas de paro**. Es poco en magnitud, pero es un error sistemático
> del que nadie se había dado cuenta, y nace de que el formulario del Excel no
> tiene ningún control que impida guardar dos veces el mismo registro.

---

## Resumen: quién pregunta qué, y dónde

| Usuario | Horizonte | Decisión típica | Herramienta |
|---|---|---|---|
| U1 Operaria | La hora en curso | Avisar | Grafana (piso de planta) |
| U2 Supervisor | El turno | Reasignar recursos | Grafana |
| U3 Coord. mantenimiento | Día y mes | Plan de mantenimiento, repuestos | Grafana + Power BI |
| U4 Jefe de producción | Semana | Secuencia y mezcla de producto | Power BI |
| U5 Gerencia | Mes y año | Inversión, metas, capacidad | Power BI |

El patrón que explica el reparto de herramientas: **a medida que el horizonte
de la decisión se alarga, la pregunta deja de ser «qué está pasando» y pasa a
ser «qué está cambiando»**. La primera necesita el último dato; la segunda
necesita comparar periodos. Son dos problemas técnicos distintos y por eso se
resuelven con dos herramientas distintas, como se detalla en
[08-powerbi-vs-grafana.md](08-powerbi-vs-grafana.md).
