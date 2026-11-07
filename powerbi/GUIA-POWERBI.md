# Power BI — cómo abrir el proyecto y armar el informe

Este proyecto está en formato **PBIP** (Power BI Project) con el modelo
semántico en **TMDL**. La justificación del formato está al final.

El **modelo semántico ya está completo**: 8 tablas, 10 relaciones, 2 jerarquías
y **36 medidas DAX**. Lo que falta es dibujar los visuales, que es trabajo de
ratón y además es justo lo que conviene practicar, porque en la sustentación el
docente puede pedir un panel nuevo en vivo.

---

## 1. Requisitos en Windows (una sola vez)

1. **Power BI Desktop** actualizado (versión de 2024 o posterior).
2. **Npgsql**, el proveedor que Power BI necesita para hablar con PostgreSQL.
   Sin esto el conector falla con «The specified module could not be found».
   - Descargar el instalador `.msi` de Npgsql desde su página de releases en
     GitHub (`npgsql/npgsql`), versión 4.0.x o superior.
   - En el instalador hay que marcar **«Npgsql GAC Installation»**. Si no se
     marca, Power BI no lo encuentra.
   - Reiniciar Power BI Desktop después de instalar.
3. **Habilitar el formato PBIP**: Archivo → Opciones y configuración →
   Opciones → *Características en versión preliminar* → marcar
   **«Power BI Project (.pbip) save option»** y reiniciar.

## 2. Comprobar que la base de datos se alcanza desde la VM

El contenedor de PostgreSQL corre en el Mac y Power BI en la máquina virtual,
así que **`localhost` no sirve**: hay que usar la IP del Mac en la red local.

En el Mac, con el proyecto levantado:

```bash
docker compose up -d postgres
ipconfig getifaddr en0        # imprime la IP del Mac, p. ej. 192.168.1.49
```

El proyecto viene configurado con **`192.168.1.49:55432`**. Si la IP del Mac
cambió, hay dos formas de corregirlo:

- **La fácil**: abrir
  `OEE-Envasado.SemanticModel/definition/expressions.tmdl` en cualquier editor
  de texto y cambiar la línea `Servidor = "..."`. Es el único sitio donde
  aparece el servidor en todo el proyecto.
- **Desde Power BI**: Inicio → Transformar datos → Configuración del origen de
  datos → Cambiar origen.

Desde la VM de Windows, antes de abrir Power BI, conviene comprobar que el
puerto responde:

```powershell
Test-NetConnection 192.168.1.49 -Port 55432
```

Si `TcpTestSucceeded` da `False`, el problema es la red de VMware o el
cortafuegos del Mac, no Power BI. En VMware, la VM debe estar en modo
**Bridged** o **NAT** (ambos funcionan); en el Mac, Preferencias del
Sistema → Red → Firewall debe permitir conexiones entrantes.

## 3. Abrir el proyecto

1. Doble clic en **`OEE-Envasado.pbip`**.
2. Power BI pedirá las credenciales de PostgreSQL. Usar el **rol de solo
   lectura**:

   | Campo | Valor |
   |---|---|
   | Tipo de autenticación | **Básica** (usuario y contraseña) |
   | Nombre de usuario | `bi_lectura` |
   | Contraseña | la de `BI_READONLY_PASSWORD` en el archivo `.env` |
   | Nivel de privacidad | Organizativo |
   | Cifrado de conexión | **desmarcado** (la red es local y el contenedor no expone TLS) |

   > **Importante y deliberado:** se conecta con `bi_lectura`, no con el
   > administrador. Ese rol solo tiene `SELECT` sobre los esquemas `dw` y
   > `aud`. Está **comprobado** que no puede leer el esquema `pii` (nombres
   > reales de operarios y personal de mantenimiento), ni el esquema `stg`
   > (datos sin depurar), ni escribir en el almacén. Si alguien intenta
   > reidentificar a una persona desde el informe, la base de datos lo
   > rechaza: la protección no depende de que el informe esté bien hecho.

3. Power BI carga las 8 tablas. Debe quedar así:

   | Tabla | Filas esperadas |
   |---|---|
   | Fecha | 1.826 |
   | Maquina | 4 |
   | Turno | 8 |
   | Referencia | 63 |
   | Paro | 65 |
   | Operario | 44 |
   | Produccion por turno | 5.138 |
   | Eventos de paro | 16.482 |

4. **Comprobación rápida de que el modelo está bien**: crear una tarjeta y
   poner la medida `OEE`. Con todos los años debe dar alrededor de **64,8 %**.
   Filtrando por `Maquina` = `Vinilos_2` y `Fecha[anio]` = 2024, la medida
   `Disponibilidad` debe dar **62,5 %**, que es la misma cifra que el Excel
   reporta hoy como «% Productividad». Si ese número coincide, el modelo está
   leyendo bien.

### Si el proyecto no abre

El formato PBIP es relativamente nuevo y cambia entre versiones de Power BI.
Si Power BI se queja del informe (no del modelo), hay una salida rápida que no
pierde nada del trabajo valioso:

1. Borrar la carpeta `OEE-Envasado.Report`.
2. Abrir Power BI Desktop en blanco → Modelado → Obtener datos → PostgreSQL y
   conectarse a `dw`.
3. El modelo semántico completo está en TMDL y se puede recrear con
   **Tabular Editor 2** (gratuito): Archivo → Abrir → *From Folder* →
   seleccionar `OEE-Envasado.SemanticModel/definition`.
4. Si todo lo demás falla, **`MEDIDAS-DAX.md`** tiene las 36 medidas listas
   para copiar y pegar una por una. Perder el archivo del modelo cuesta un
   rato; perder las medidas no, porque están escritas aparte a propósito.

---

## 4. Las cuatro páginas del informe

Las medidas están organizadas en carpetas de visualización, así que en el panel
de datos aparecen agrupadas (`01 Tiempo`, `02 OEE`,
`03 Inteligencia de tiempo`, `04 Paros`, `05 Pareto`, `06 Confiabilidad`,
`07 Gobierno del dato`).

### Página 1 — «Resumen gerencial»

*Responde: ¿cómo va la planta y qué línea necesita atención?*

| Visual | Campos |
|---|---|
| 4 tarjetas | `OEE`, `Disponibilidad`, `Rendimiento`, `Calidad (proxy)` |
| 1 tarjeta | `Variacion de OEE interanual` ← **la medida de inteligencia de tiempo** |
| Gráfico de columnas agrupadas | Eje: `Maquina[codigo_maquina]` · Valores: `OEE` y `OEE del ano anterior` |
| Gráfico de líneas | Eje: `Fecha[etiqueta_anio_mes]` · Valores: `Disponibilidad`, `Disponibilidad movil 3 meses` · Leyenda: `Maquina[codigo_maquina]` |
| Matriz | Filas: `Maquina[codigo_maquina]` · Columnas: `Fecha[anio]` · Valores: `OEE`, `Brecha vs meta` |
| **Segmentaciones** | `Fecha[anio]`, `Maquina[codigo_maquina]`, `Turno[nombre_turno]` |

Formato condicional útil en la matriz: `Brecha vs meta` con escala de color
rojo-verde centrada en 0.

### Página 2 — «Pareto de causas»  ← *requisito explícito*

*Responde: ¿cuáles pocas causas explican casi todo el tiempo perdido?*

1. Visual **«Gráfico de líneas y columnas agrupadas»**.
2. Eje compartido: `Paro[etiqueta_codigo_paro]`.
3. Valores de columna: `Horas perdidas`.
4. Valores de línea: `% acumulado de tiempo perdido`.
5. En Formato → Eje Y secundario, fijar **mínimo 0 y máximo 1**.
6. Ordenar el visual por `Horas perdidas` descendente. **Esto es
   imprescindible**: la curva acumulada solo tiene sentido si las barras van de
   mayor a menor.
7. Añadir una **línea constante en 0,8** (Formato → Líneas de referencia) para
   marcar el 80 %.
8. Opcional: colorear las barras con formato condicional según
   `Clasificacion Pareto`.

Al lado, una tabla con `Paro[etiqueta_codigo_paro]`, `Horas perdidas`,
`Numero de eventos`, `Duracion media del paro`, `Unidades no producidas`,
`% acumulado de tiempo perdido` y `Clasificacion Pareto`.

### Página 3 — «Drill-down de paros»  ← *requisito explícito*

*Responde: ¿qué sistema de la máquina nos está costando el tiempo?*

1. Gráfico de **barras apiladas** o **treemap**.
2. En el campo del eje, arrastrar la **jerarquía completa**
   `Paro[Jerarquia de paros]` (no las columnas sueltas: la jerarquía ya está
   creada en el modelo).
3. Valores: `Horas perdidas`.
4. Activar el drill-down con la flecha del visual y bajar los cuatro niveles:
   **Área responsable → Código de paro → Sistema de la máquina → Causa raíz**.

   El tercer nivel es el interesante y conviene señalarlo en la sustentación:
   el **Sistema de la máquina** es un atributo construido por el equipo que une
   las ramas 1.x, 3.x y 5.x de la fuente. El Excel no puede responder «¿qué
   sistema me cuesta más?» porque esas ramas viven en columnas separadas.
   Al bajar se ve que el **sistema dosificador de pintura explica el 44,6 %
   del tiempo de los codigos 01, 03 y 05** (2.222,8 h), que es el 11,8 % de
   las 8.431,5 h perdidas en total. Cuidado con decir «el 46 % de todo el
   tiempo perdido de la planta»: es falso y el dato real ya es contundente.

5. Añadir una segmentación por `Paro[naturaleza_paro]` para separar el tiempo
   perdido evitable del planeado.

### Página 4 — «Calidad del dato»

*Responde: ¿podemos confiar en estos números?*

| Visual | Campos |
|---|---|
| Gráfico de columnas | Eje: `Fecha[anio]` · Valores: `Indice de completitud del registro` · Leyenda: `Maquina[codigo_maquina]` |
| Tarjetas | `Turnos registrados`, `Turnos sin estandar` |
| Tabla | `Fecha[anio]`, `Turnos registrados`, `Turnos sin estandar`, `Indice de completitud del registro` |

Esta página es la que sostiene a las otras tres. El índice de completitud pasa
de **0 % en 2022 a 95,3 % en 2025**: en 2022 ninguna fila tiene operario,
referencia ni turno, y por eso el Rendimiento —y con él el OEE— no es
calculable antes de 2023. Mostrarlo es más honesto que presentar un OEE de 2022
que no existe.

---

## 5. Al terminar

Guardar con **Archivo → Guardar** (no «Guardar como»), para que Power BI
reescriba los archivos TMDL del proyecto y los cambios queden versionables.

---

## 6. Por qué PBIP/TMDL y no .pbix

El enunciado pide elegir y justificar un formato compatible con control de
versiones. La comparación es corta:

| | `.pbix` | **PBIP + TMDL** |
|---|---|---|
| Qué es | un archivo ZIP binario | carpetas de archivos de texto |
| En `git diff` | «archivo binario modificado» | se ve la línea exacta que cambió |
| Revisar un cambio | hay que abrir Power BI | se lee en el navegador de GitHub |
| Conflictos de fusión | irresolubles, se pierde el trabajo de alguien | se resuelven como en cualquier código |
| Historial útil | no | sí: queda registrado quién cambió qué medida y cuándo |

Un `.pbix` en git es un adjunto, no código versionado: el repositorio guarda
copias completas del binario en cada commit y nadie puede revisar qué cambió.
Con TMDL, cambiar el umbral de una medida produce un diff de una línea
legible, y por eso `.pbix` está excluido en el `.gitignore` del proyecto.

El modelo se guarda en TMDL y no en el TMSL de siempre (`model.bim`, un JSON
único) porque TMDL reparte el modelo en **un archivo por tabla**: dos personas
pueden tocar tablas distintas sin pisarse, y el formato admite **comentarios**
(las líneas `///`), así que cada medida lleva escrito al lado por qué está
definida como está. Un JSON no admite comentarios, de modo que la justificación
tendría que vivir fuera del modelo y envejecería aparte.
