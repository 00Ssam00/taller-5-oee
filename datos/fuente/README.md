# Insumos de origen (no versionados)

Esta carpeta debe contener los dos insumos que entrega la empresa. **No están
en el repositorio y no deben subirse.**

| Archivo | SHA-256 | Tamaño |
|---|---|---|
| `Seguimiento Temperas y Vinilos Actividad.xlsm` | `c7d7eabbd55844757c2be07bd61efcee9eb5e0b03aaf9fd76b798737a92d5c55` | 4,2 MB |
| `P-MTO-21-V1_Registro_paros_de_produccion_actividad.pdf` | `d8ef15912feb1b772e91536129ffe40a66e8cf0949ef4da239b18c48c8f0178b` | 720 KB |

## Por qué no se versionan

El libro de Excel contiene los **nombres reales** de 45 operarias, operarios y
técnicos de mantenimiento: la columna «Operario» (34 valores), la columna
«Personal involucrado» del código 05 (38 valores, con nombre y apellidos
completos) y la lista nominal de la hoja `Tiempos`.

Publicarlo en un repositorio sería divulgar datos personales sin autorización
de sus titulares, en contra de la **Ley 1581 de 2012** y en contradicción
directa con el modelo de protección que implementa el proyecto
(ver [`docs/10`](../../docs/10-datos-personales-y-seguridad.md)): no tendría
sentido pseudonimizar los nombres en la base de datos y a la vez dejar el
archivo con los nombres reales a la vista en GitHub.

El PDF del procedimiento `P-MTO-22` tampoco se versiona, por ser documentación
interna de la empresa.

## Cómo reproducir el proyecto

1. Copiar los dos archivos en esta carpeta, con los nombres exactos de la tabla
   de arriba.
2. Verificar que el libro es el mismo con el que se calcularon las cifras del
   informe:

   ```bash
   shasum -a 256 "datos/fuente/Seguimiento Temperas y Vinilos Actividad.xlsm"
   ```

   Debe coincidir con el SHA-256 de la tabla. El ETL registra ese valor en
   `aud.ejecucion_etl` en cada ejecución, de modo que si alguien carga otro
   archivo queda constancia en la base.

3. Levantar la solución:

   ```bash
   docker compose up -d --build
   ```
