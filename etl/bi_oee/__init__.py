"""ETL del proyecto BI-OEE: Excel de seguimiento -> modelo dimensional PostgreSQL.

Paquete organizado por responsabilidad:

    config        parametros desde variables de entorno
    conexion      conexion a PostgreSQL y utilidades de carga masiva
    catalogos     REGLAS DE NEGOCIO: normalizacion y mapeo de taxonomias
    extraccion    hojas del Excel  ->  esquema stg
    dimensiones   stg + catalogos  ->  dimensiones de dw (incluye SCD Tipo 2)
    hechos        despivote y carga de las tablas de hechos
    calidad       reglas de calidad de datos con conteos antes/despues
    conciliacion  comprobacion de los totales contra la fuente
    cli           orquestacion
"""

VERSION = "1.0.0"
