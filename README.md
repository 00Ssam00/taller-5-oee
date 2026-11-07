# Solución de Inteligencia de Negocios · OEE en líneas de envasado

Solución de BI de extremo a extremo para una fábrica de vinilos y témperas, que
integra los registros históricos de producción y paros de cuatro líneas de
envasado (`Vinilos_1` a `Vinilos_4`) en un modelo dimensional sobre PostgreSQL,
mediante un ETL reproducible con validación de calidad de datos, y los expone
en dos capas de consumo: **Grafana** para la operación del turno y
**Power BI** para el análisis gerencial.

**Autor:** Samuel Alvarez Becerra
**Asignatura:** Inteligencia de Negocios · Proyecto Final
**Fuente:** `Seguimiento Temperas y Vinilos Actividad.xlsm` y procedimiento
`P-MTO-22 V1`

---

## Qué resuelve

La planta lleva tres años registrando producción y paros en un Excel con
macros. Ese archivo calcula un indicador que llama **«% Productividad»** y que,
al reproducirlo desde los datos crudos, resulta ser exactamente la
**Disponibilidad** del OEE. Es decir: la planta cree medir su productividad y
mide solo uno de los tres componentes.

Esta solución completa el cálculo y, en el camino, responde preguntas que la
fuente contiene pero no puede responder:

| Hallazgo | Cifra |
|---|---|
| **El sistema dosificador de pintura explica el 44,6 % del tiempo perdido por las causas con raíz identificable**, y cinco sistemas explican el 81,6 % | 992 h de las 2.222,8 h de los códigos 01/03/05, el 11,8 % del tiempo perdido total. Imposible de ver en el Excel: las tres ramas de subcódigos que apuntan a ese sistema viven en columnas separadas |
| El tiempo perdido **evitable** es el 64,9 % del total | 5.468 h de 8.431 h |
| Seis códigos de paro concentran el 83,6 % del tiempo perdido | Pareto 80/20 confirmado |
| Las cifras que hoy se llevan al comité están **infladas por 42 registros duplicados** | +129 h, +1.019 pacas, +18,12 h de paro |
| La **completitud del registro** pasó del 0 % en 2022 al 95,3 % en 2025 | En 2022 ninguna fila tiene operario, referencia ni turno |
| Dos líneas ya sostienen un OEE del 72–74 % con los mismos equipos | Vinilos_3 y Vinilos_4 en 2024 (74,4 % y 72,3 %), frente al 48,7 % de Vinilos_1 |
| **Vinilos_1 no cayó: lleva dos años plano** en 49,7 % (2023) y 48,7 % (2024) | La «caída de 62 % a 48,5 %» que sugería un cálculo anterior era un artefacto de mezclar poblaciones de turnos (ver más abajo) |

---

## Arquitectura

```
  PLANTA                      CONTENEDORES (Docker)                ANFITRIÓN
  ──────                      ─────────────────────                ─────────
  Formato papel
  "hora a hora"
       │
       ▼
  ┌──────────┐    lee     ┌─────────────────────┐
  │  .xlsm   │ ─────────► │   ETL (Python)      │
  │ 8.208    │  SHA-256   │ extrae · limpia     │
  │ filas    │  registrado│ concilia (62) ·     │
  └──────────┘            │ calidad (21 reglas) │
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────────────┐
                          │  PostgreSQL 17              │        ┌──────────┐
                          │   stg → dw ← pii, aud       │◄───────┤ DBeaver  │
                          └───────┬──────────┬──────────┘ admin  └──────────┘
                                  │          │ bi_lectura        ┌──────────┐
                     ┌────────────┘          └──────────────────►│ Power BI │
                     ▼                                           └──────────┘
          ┌──────────────────┐     ┌─────────────┐
          │   GRAFANA 11.6   │◄────┤  SIMULADOR  │
          │ 12 paneles       │     │  hora a hora│
          │ alerta OEE < 50 %│────►│  + receptor │
          └──────────────────┘     └─────────────┘
```

El diagrama completo y el recorrido de un dato de principio a fin están en
[`docs/07-arquitectura.md`](docs/07-arquitectura.md).

### Componentes

| Componente | Versión | Dónde corre | Para qué |
|---|---|---|---|
| PostgreSQL | 17-alpine | Contenedor | Almacén dimensional (4 esquemas) |
| ETL | Python 3.12 | Contenedor | Extrae del Excel, limpia, concilia, carga |
| Grafana | 11.6.0 | Contenedor | Tablero operativo + alerta |
| Simulador | Python 3.12 | Contenedor | Telemetría hora a hora, en lugar del PLC |
| Power BI Desktop | — | Anfitrión (Windows) | Tablero analítico gerencial |
| DBeaver | — | Anfitrión | Administración del DDL y consultas |

---

## Reproducir desde cero

### Requisitos

- Docker con Compose v2 (probado con OrbStack en macOS)
- 2 GB de RAM libres y ~1 GB de disco

> **Importante en macOS:** el proyecto **no puede vivir en iCloud Drive**.
> Docker no puede montar esas rutas (falla con `Operation not permitted` al leer
> `/docker-entrypoint-initdb.d/`) y un repositorio git dentro de iCloud se
> corrompe por la sincronización. Úsese una ruta local, por ejemplo
> `~/Developer/proyecto-bi-oee`.

### Pasos

```bash
# 1. Colocar los insumos de la empresa en datos/fuente/
#    No están en el repositorio porque contienen nombres reales de personal.
#    Los nombres de archivo exactos y el SHA-256 para verificarlos están en
#    datos/fuente/README.md
# 2. Configurar las credenciales (NUNCA se versionan)
cp .env.example .env
$EDITOR .env          # reemplazar los valores CAMBIE_ESTA_*

# 3. Levantar toda la solución con UN comando
docker compose up -d --build
```

Eso es todo. El comando:

1. Crea el volumen de PostgreSQL y ejecuta los **8 scripts de DDL** en orden
   (`sql/init/00` a `70`): esquemas, roles, staging, dimensiones, hechos,
   índices, vistas, permisos y diccionario.
2. Espera a que la base esté **sana** (`pg_isready`) y lanza el ETL.
3. El ETL carga el Excel, aplica **21 reglas de calidad** y **62 pruebas de
   conciliación**, y escribe sus informes en `etl/salida/`.
4. Espera a que el ETL **termine con éxito**
   (`service_completed_successfully`) y arranca Grafana, que carga por
   *provisioning* su datasource, su tablero y su alerta. **Cero configuración
   manual.**
5. Arranca el simulador, que alimenta la telemetría hora a hora.

**Tiempo medido de arranque completo desde cero: 12 segundos.**

### Verificar que funcionó

```bash
docker compose logs etl | tail -20
```

Salida esperada:

```
  hecho_produccion_turno        5,138 filas
  hecho_paro                   16,482 filas
  Conciliacion      : 58 pruebas OK, 4 informativas, 0 fallidas
  Calidad de datos  : 21 reglas evaluadas, 18 con advertencia
  ETL COMPLETADO CORRECTAMENTE
```

### Acceder

| Qué | Dónde | Credenciales |
|---|---|---|
| **Grafana** | http://localhost:3000 | Las de `GF_SECURITY_ADMIN_*` en `.env` |
| **PostgreSQL** (DBeaver, Power BI) | `localhost:55432`, base `bi_oee` | Las de `BI_READONLY_*` en `.env` |

> Desde una máquina virtual (Power BI en Windows) hay que usar **la IP del
> anfitrión**, no `localhost`. El procedimiento está en
> [`powerbi/GUIA-POWERBI.md`](powerbi/GUIA-POWERBI.md).

### Volver a empezar de cero

```bash
docker compose down -v        # -v borra los volúmenes
docker compose up -d --build
```

La prueba de reproducibilidad es precisamente esta: los resultados del ETL son
idénticos en cada reconstrucción.

---

## Estructura del repositorio

```
proyecto-bi-oee/
├── README.md                       Este archivo
├── docker-compose.yml              Toda la solución, un comando
├── .env.example                    Plantilla de variables (.env NO se versiona)
├── .gitignore
│
├── datos/fuente/                   Los insumos de la empresa. NO se versionan:
│                                contienen nombres reales (ver su README.md)
│
├── sql/
│   ├── init/                       DDL, ejecutado automáticamente al crear la BD
│   │   ├── 00_roles_y_esquemas.sql       Esquemas stg/dw/pii/aud + justificación del motor
│   │   ├── 10_ddl_staging.sql            Zona de aterrizaje (todo TEXT)
│   │   ├── 20_ddl_dimensiones.sql        10 dimensiones + justificación del esquema
│   │   ├── 30_ddl_hechos.sql             3 hechos + tablas de auditoría
│   │   ├── 40_indices_y_restricciones.sql  63 índices, 21 CHECK, justificados
│   │   ├── 50_vistas_analiticas.sql      7 vistas para los tableros
│   │   ├── 60_permisos.sql               Mínimo privilegio + RLS sobre pii
│   │   └── 70_diccionario.sql            187 COMMENT ON COLUMN
│   └── consultas/
│       └── consultas_negocio.sql   12 consultas (C01-C12) con funciones de ventana
│
├── etl/
│   ├── Dockerfile  requirements.txt
│   ├── bi_oee/                     El paquete: extraccion, dimensiones, hechos,
│   │                               calidad, conciliacion, catalogos, cli
│   └── salida/                     Informes generados en cada ejecución
│
├── simulador/                      Telemetría hora a hora + receptor de alertas
│
├── grafana/
│   ├── provisioning/               datasource · tablero · alerta (automático)
│   └── dashboards/oee-operativo.json     12 paneles, 3 variables
│
├── powerbi/
│   ├── OEE-Envasado.pbip           Proyecto en formato versionable (PBIP/TMDL)
│   ├── OEE-Envasado.SemanticModel/ 8 tablas, 36 medidas DAX, 10 relaciones
│   ├── OEE-Envasado.Report/        4 páginas, 15 visuales
│   ├── GUIA-POWERBI.md             Cómo abrirlo y conectarlo
│   └── MEDIDAS-DAX.md              Las 36 medidas, generadas desde el TMDL
│
├── herramientas/                   Generadores (diccionario, DAX, tablero)
│
├── docs/                           La documentación del proyecto
│   └── evidencias/                 Capturas de los tableros (NO versionadas)
│
└── entregables/
    └── BI_ProyectoFinal_Alvarez_Becerra.pdf    60 páginas · el informe
```

### Por qué las capturas no están en el repositorio y el PDF sí

Las capturas de `docs/evidencias/` son la salida de una sesión en vivo: Grafana
con el simulador corriendo y la alerta disparada, Power BI conectado a la base.
Volver a generarlas da imágenes distintas cada vez, porque el simulador produce
telemetría nueva. Versionarlas crearía un historial de binarios que cambian en
cada ejecución sin que cambie nada del código.

**El registro congelado de lo que mostraban es el PDF de `entregables/`**, que
sí se versiona y que no debe cambiar después de la entrega. Quien quiera ver
las evidencias las encuentra ahí, en su contexto y con su explicación.

La consecuencia práctica, dicha sin rodeos: en un clon limpio,
`herramientas/gen_pdf.py` reconstruye el informe pero sin las figuras
(«capturas: 0 de 7»). Es deliberado. Para rehacerlas hay que levantar la
solución y ejecutar `herramientas/gen_capturas.py` (Grafana) y tomar a mano las
de Power BI, siguiendo `powerbi/GUIA-POWERBI.md`.

---

## Documentación

| Documento | Contenido |
|---|---|
| [01 · Usuarios y preguntas de negocio](docs/01-usuarios-y-preguntas-de-negocio.md) | 5 perfiles de usuario y sus preguntas, con la herramienta que responde cada una |
| [02 · Diagnóstico de la fuente](docs/02-diagnostico-de-la-fuente.md) | Estructura del Excel, problemas de calidad cuantificados, límites del esquema de reporte actual |
| [03 · Catálogo de indicadores](docs/03-catalogo-de-indicadores.md) | Los 3 indicadores del P-MTO-22 + 13 nuevos, con fórmula, granularidad, meta justificada y usuario |
| [04 · Modelo dimensional](docs/04-modelo-dimensional.md) | Justificación del esquema, grano declarado, jerarquía de paros, **matriz de bus**, SCD Tipo 2 |
| [05 · Diccionario de datos](docs/05-diccionario-de-datos.md) | 13 tablas, 187 columnas, generado desde el catálogo de PostgreSQL |
| [06 · ETL, calidad y conciliación](docs/06-etl-calidad-y-conciliacion.md) | Justificación de la herramienta, 21 reglas con conteos antes/después, 62 pruebas de conciliación |
| [07 · Arquitectura](docs/07-arquitectura.md) | Diagrama completo, decisiones de contenerización, recorrido de un dato |
| [08 · Power BI y Grafana](docs/08-powerbi-vs-grafana.md) | Qué resuelve cada uno, para qué usuario, por qué no se intercambian |
| [09 · Evolución a PLC/SCADA](docs/09-evolucion-plc-scada.md) | Qué instrumentar, arquitectura propuesta, plan por fases |
| [10 · Datos personales y seguridad](docs/10-datos-personales-y-seguridad.md) | Pseudonimización, RLS, mínimo privilegio, **con la evidencia ejecutada** |

---

## El modelo de datos en una página

**Esquema en constelación** con tres tablas de hechos que comparten dimensiones
conformadas. La justificación de esta elección frente a una estrella única o un
copo de nieve está en [`docs/04`](docs/04-modelo-dimensional.md).

| Tabla de hechos | Grano | Filas |
|---|---|---|
| `dw.hecho_produccion_turno` | Un turno de una máquina en una fecha, para una referencia | 5.138 |
| `dw.hecho_paro` | Un evento de paro de un código concreto dentro de un turno | 16.482 |
| `dw.hecho_produccion_hora` | Una hora de reloj de una máquina (telemetría) | variable |

| Dimensión | Filas | Nota |
|---|---|---|
| `dim_fecha` | 1.826 | **Construida por el equipo**: festivos de Colombia (Ley Emiliani), llaves interanuales precalculadas |
| `dim_paro` | 65 | Jerarquía **desbalanceada** de 4 niveles; el nivel «sistema físico» es un atributo conformado construido por el equipo |
| `dim_estandar` | 137 | **SCD Tipo 2** con vigencia e índice único parcial |
| `dim_maquina` · `dim_turno` · `dim_referencia` | 4 · 8 · 63 | Dimensiones conformadas |
| `dim_operario` · `dim_personal_mantenimiento` | 44 · 39 | **Pseudonimizadas**; los nombres viven solo en `pii` |
| `dim_tipo_paro_cabecera` · `dim_area_involucrada` | 13 · 7 | |

### Los cuatro esquemas

| Esquema | Contiene | Lo lee |
|---|---|---|
| `stg` | Zona de aterrizaje, todo `TEXT` | Solo `bi_admin` |
| `dw` | El modelo dimensional | Grafana y Power BI (`bi_lectura`) |
| `pii` | Nombres reales, con **RLS** | Solo `pii_reidentificacion` |
| `aud` | Calidad, conciliación, ejecuciones | Grafana y Power BI |

---

## Seguridad y datos personales

- **Ningún archivo versionado contiene credenciales** ni cadenas de conexión
  con contraseña. Todo va por variables de entorno; `.env` está excluido y se
  versiona `.env.example`.
- **Los insumos de origen tampoco se versionan.** El `.xlsm` contiene los
  nombres reales de 45 personas: publicarlo contradiría el propio modelo de
  protección del proyecto. `datos/fuente/README.md` documenta cómo reponerlo y
  su SHA-256 para verificarlo.
- Los nombres de operarios y personal de mantenimiento **no llegan al modelo
  analítico**: se sustituyen por pseudónimos estables derivados por HMAC-SHA256
  con semilla secreta. Los nombres viven en un esquema aparte con seguridad a
  nivel de fila.
- El rol que usan los tableros **no puede** leer `pii` ni `stg`, ni escribir en
  `dw`. Está **comprobado y documentado**, no solo afirmado:
  [`docs/10`](docs/10-datos-personales-y-seguridad.md), sección 6.

---

## Cómo se calcula el OEE

`OEE = Disponibilidad × Rendimiento`. Dos reglas lo definen, y las dos son
decisiones de diseño que conviene leer antes de interpretar cualquier cifra.

**1. Los dos factores se miden sobre los mismos turnos.** La Disponibilidad se
puede calcular en cualquier registro, porque solo necesita horas. El
Rendimiento exige un estándar de ingeniería (unidades por minuto del par
máquina–referencia), y la fuente solo lo trae en una parte de los registros.
Multiplicar la Disponibilidad de *todos* los turnos por el Rendimiento de *unos
pocos* produce un número que no describe ninguna operación real: en Vinilos_1
2023, donde solo el 28 % de los turnos trae estándar, daba un OEE del 62,0 %
frente al 49,7 % correcto, e inventaba una caída de 13 puntos hacia 2024 que
nunca ocurrió. Por eso el indicador restringe los dos factores al mismo
subconjunto (`tiene_estandar AND NOT rendimiento_implausible`).

**2. Se agrega como razón de sumas, nunca promediando el OEE de cada turno.**

```
OEE = SUM(horas_operativas)    / SUM(horas_programadas)
    × SUM(unidades_producidas) / SUM(unidades_posibles)
```

El OEE es un producto de ratios: el promedio de los productos no es el producto
de los promedios. Agregarlo desde los sumandos es lo único que da el mismo
valor en cualquier nivel de la jerarquía y lo único que concilia contra los
totales de la fuente. La columna `oee_ad` de la tabla de hechos existe para
auditar fila a fila; **no se agrega**.

Como consecuencia, el OEE **se publica siempre junto a su cobertura**, la
fracción de turnos del periodo que entra en el cálculo:

| Año | Cobertura | V1 | V2 | V3 | V4 |
|---|---|---|---|---|---|
| 2022 | 0 % | — | — | — | — |
| 2023 | 17–30 % | 49,7 | 45,7 | 67,2 | 65,3 |
| 2024 | 70–91 % | 48,7 | 53,0 | 74,4 | 72,3 |
| 2025 | 48–100 % | 66,8 | 48,3 | 67,6 | 71,3 |

En 2022 la cobertura es cero y el OEE sale nulo, que es lo correcto: ese año la
fuente no registró ninguna meta por hora. El OEE global de todo el histórico es
del **64,8 %**.

Hay un hallazgo en esa restricción que merece mencionarse: en 2023 los turnos
**con** estándar tienen peor disponibilidad que el conjunto (61,4 % contra
76,6 % en Vinilos_1). El registro del estándar no era aleatorio. En 2024, con
la cobertura por encima del 70 %, ambas cifras ya convergen.

La medida `Disponibilidad` del modelo semántico se calcula a propósito sobre
**todos** los turnos, porque es la que reproduce el «% Productividad» del Excel
y sostiene el hallazgo del proyecto. El factor que entra en el OEE es
`Disponibilidad (OEE)`. No son la misma medida.

---

## Alerta de OEE crítico

Es la alerta que carga el provisioning de Grafana y la que hay que atender en
el turno.

| | |
|---|---|
| **Condición** | OEE promedio de las últimas 2 horas < **50 %**, por línea |
| **Evaluación** | Cada 30 s; dispara si se sostiene **1 minuto** |
| **Por qué el 50 %** | Es la frontera en la que dos líneas llevan años: Vinilos_1 (49,7 % en 2023 y 48,7 % en 2024) y Vinilos_2 (45,7 % en 2023, 48,3 % en 2025). Por debajo de ese valor la línea produce menos de la mitad de su capacidad mientras consume el 100 % de la mano de obra, la energía y el aire comprimido |
| **Destino** | Punto de contacto por webhook, con una instancia de alerta **por línea** |

### Qué hacer cuando se dispara

1. **Mirar cuál de los tres componentes cayó**, en el panel «Componentes del
   OEE» del tablero operativo.
2. **Si cayó la Disponibilidad** — la línea está parada. Ir al panel de causas
   de paro del período. Históricamente el **sistema dosificador de pintura**
   explica el 44,6 % del tiempo perdido con causa raíz identificable, así que
   es el primer sitio donde mirar.
3. **Si cayó el Rendimiento** — la línea corre, pero por debajo del estándar de
   ingeniería. Revisar velocidad, ajuste y si la referencia en proceso es la
   que el tablero cree.
4. **Si cayó la Calidad** — hay reproceso en curso (código 11).
5. **Si el panel «Líneas sin reportar» está en rojo**, el problema no es la
   máquina sino el dato: la línea dejó de enviar telemetría y el OEE que se ve
   está congelado.

> Una línea en verde porque no llega información es peor que una línea en rojo.
> Por eso el panel de líneas sin reportar va al lado del semáforo.

---

## Notas de implementación

- **Power BI en formato PBIP/TMDL** y no `.pbix`, porque `.pbix` es un binario
  que no admite revisión en un control de versiones. El TMDL es texto plano:
  un cambio en una medida DAX se lee en el diff. La justificación completa está
  en [`powerbi/GUIA-POWERBI.md`](powerbi/GUIA-POWERBI.md).
- **El tablero de Grafana se provisiona con `allowUiUpdates: false`**: el JSON
  del repositorio es la única verdad y nadie puede editarlo desde la interfaz
  dejando el repositorio desactualizado.
- **El OEE se define en una sola capa.** La fórmula vive en la medida DAX, en
  la consulta C01 y en la vista `dw.v_oee_mes_maquina`, y las tres dan el mismo
  número; está verificado. La vista publica además `disponibilidad_oee` y
  `cobertura_oee` para que la diferencia con la Disponibilidad de cobertura
  total quede a la vista en lugar de esconderse en el cálculo.
- **El simulador existe para ocupar el lugar del PLC.** Está calibrado con la
  disponibilidad histórica real de cada línea y usa un proceso de Poisson para
  los paros, de modo que la demostración es verosímil y no una secuencia
  inventada. Se retiraría el día que llegue dato de planta.
