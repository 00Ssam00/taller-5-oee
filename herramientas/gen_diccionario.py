# -*- coding: utf-8 -*-
"""Genera docs/05-diccionario-de-datos.md leyendo el catalogo de PostgreSQL.

El diccionario NO se escribe a mano: se extrae de la base, de modo que tipos,
llaves, restricciones y descripciones son necesariamente los reales.
"""
import pathlib
import os, pathlib, subprocess, textwrap, collections

def psql(sql):
    out = subprocess.run(
        ["docker", "exec", "bioee-postgres", "psql", "-U", "bi_admin",
         "-d", "bi_oee", "-t", "-A", "-F", "\x1f", "-c", sql],
        capture_output=True, text=True, check=True).stdout
    filas = []
    for l in out.split("\n"):
        if not l.strip():
            continue
        filas.append(l.split("\x1f"))
    # psql omite el separador final cuando el ultimo campo es vacio, asi que
    # las filas pueden llegar cortas: se rellenan para poder desempacarlas.
    ancho = max(len(f) for f in filas) if filas else 0
    return [f + [""] * (ancho - len(f)) for f in filas]

ORDEN = ["hecho_produccion_turno", "hecho_paro", "hecho_produccion_hora",
         "dim_fecha", "dim_maquina", "dim_turno", "dim_referencia",
         "dim_estandar", "dim_paro", "dim_tipo_paro_cabecera",
         "dim_area_involucrada", "dim_operario", "dim_personal_mantenimiento"]

GRANOS = {
 "hecho_produccion_turno":
   "**Un registro por turno de produccion de una maquina en una fecha, para "
   "una referencia concreta.** Si en el mismo turno la linea cambia de "
   "referencia, la fuente genera un registro nuevo, y el consecutivo lo "
   "distingue. 5.138 filas.",
 "hecho_paro":
   "**Un registro por evento de paro de un codigo concreto dentro de un turno "
   "de una maquina.** Es el resultado de despivotar los 18 pares de columnas "
   "`<minutos, horas>` que el Excel tiene en horizontal. 16.482 filas.",
 "hecho_produccion_hora":
   "**Un registro por hora de reloj y maquina.** Es el grano que entregaria un "
   "historiador de PLC/SCADA. Hoy lo alimenta el simulador; el ETL del Excel "
   "no escribe aqui porque la fuente historica no tiene grano horario.",
}

filas = psql("""
SELECT c.relname, a.attnum, a.attname,
       format_type(a.atttypid, a.atttypmod),
       CASE WHEN a.attnotnull THEN 'NO' ELSE 'si' END,
       coalesce(d.description, ''),
       coalesce(pg_get_expr(ad.adbin, ad.adrelid), '')
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = a.attnum
LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
WHERE n.nspname = 'dw' AND c.relkind = 'r'
ORDER BY c.relname, a.attnum
""")

tabla_doc = {r[0]: r[1] for r in psql("""
SELECT c.relname, coalesce(obj_description(c.oid), '')
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='dw' AND c.relkind='r'
""")}

llaves = collections.defaultdict(dict)
for t, col, tipo, ref in psql("""
SELECT c.relname, a.attname,
       CASE con.contype WHEN 'p' THEN 'PK' WHEN 'f' THEN 'FK' WHEN 'u' THEN 'UQ' END,
       CASE WHEN con.contype='f'
            THEN cf.relname || '.' || af.attname ELSE '' END
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
LEFT JOIN pg_class cf ON cf.oid = con.confrelid
LEFT JOIN unnest(con.confkey) WITH ORDINALITY AS kf(attnum, ord)
     ON kf.ord = k.ord AND con.contype='f'
LEFT JOIN pg_attribute af ON af.attrelid = con.confrelid AND af.attnum = kf.attnum
WHERE n.nspname='dw' AND c.relkind='r' AND con.contype IN ('p','f','u')
"""):
    actual = llaves[t].get(col, "")
    # Solo la tabla destino: una FK apunta siempre a su PK, y repetir
    # ".columna" aqui obligaba a una columna del doble de ancho.
    marca = tipo if tipo != "FK" else "FK → `%s`" % ref.split(".")[0]
    if marca not in actual:
        llaves[t][col] = (actual + " " + marca).strip()

restricciones = collections.defaultdict(list)
for t, nombre, definicion in psql("""
SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname='dw' AND c.relkind='r' AND con.contype = 'c'
ORDER BY c.relname, con.conname
"""):
    restricciones[t].append((nombre, definicion))

conteos = {r[0]: int(r[1]) for r in psql("""
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE schemaname='dw'
""")}

por_tabla = collections.OrderedDict()
for t, num, col, tipo, nulo, desc, default in filas:
    por_tabla.setdefault(t, []).append((col, tipo, nulo, desc, default))

L = [
 "# Diccionario de datos",
 "",
 "> **Este documento se genera automaticamente** leyendo el catalogo de",
 "> PostgreSQL (`herramientas/gen_diccionario.py`). Los tipos, las llaves y",
 "> las restricciones son los que la base tiene de verdad, no una",
 "> transcripcion; y las descripciones salen de los `COMMENT` del script",
 "> `sql/init/70_diccionario.sql`, de modo que el diccionario y la base no",
 "> pueden divergir.",
 "",
 "Cada descripcion de columna tiene tres partes:",
 "",
 "- **La descripcion** de que representa el campo.",
 "- **`ORIGEN:`** de donde sale el dato. `construida` significa que el ETL la",
 "  genera y no existe en la fuente; si viene del Excel, se nombra la columna",
 "  y la hoja exactas.",
 "- **`REGLA:`** la transformacion que se le aplico.",
 "",
 f"El esquema `dw` tiene **{len(por_tabla)} tablas** y "
 f"**{len(filas)} columnas**, todas documentadas.",
 "",
 "## Indice",
 "",
]
orden_final = [t for t in ORDEN if t in por_tabla] + \
              [t for t in por_tabla if t not in ORDEN]
for t in orden_final:
    clase = "Hecho" if t.startswith("hecho_") else "Dimension"
    L.append(f"- [`dw.{t}`](#dw{t.replace('_','')}) — {clase}, "
             f"{len(por_tabla[t])} columnas")
L.append("")

for t in orden_final:
    L += ["---", "", f"## `dw.{t}`", ""]
    if tabla_doc.get(t):
        L += [tabla_doc[t], ""]
    if t in GRANOS:
        L += ["**Grano declarado.** " + GRANOS[t], ""]
    n = conteos.get(t)
    if n:
        L += [f"*Filas cargadas: aproximadamente {n:,}.*".replace(",", "."), ""]

    # La nulabilidad va DENTRO del tipo, como en el DDL. Antes ocupaba una
    # columna propia que repetia "si" o "NO" 187 veces: dos milimetros de ancho
    # util por fila que le hacian falta a Tipo, donde "numeric(12,6)" partia en
    # dos lineas y estiraba la altura de toda la fila.
    L += ["| Columna | Tipo | Clave | Descripcion, origen y regla |",
          "|---|---|---|---|"]
    for col, tipo, nulo, desc, default in por_tabla[t]:
        k = llaves[t].get(col, "")
        d = desc.replace("|", "\\|") if desc else "—"
        if default and "nextval" not in default:
            d += f" *(Valor por defecto: `{default}`.)*"
        tipo_full = tipo if str(nulo).strip().lower() == "si" else f"{tipo} NOT NULL"
        L.append(f"| `{col}` | `{tipo_full}` | {k} | {d} |")
    L.append("")

    if restricciones.get(t):
        L += ["**Restricciones de validacion (CHECK).** Son las reglas de "
              "negocio que la base impide violar, de modo que un dato "
              "incoherente no puede entrar ni por error de programacion:", ""]
        for nombre, definicion in restricciones[t]:
            L.append(f"- `{nombre}`: `{definicion}`")
        L.append("")

destino = (pathlib.Path(__file__).resolve().parent.parent
           / "docs" / "05-diccionario-de-datos.md")
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text("\n".join(L) + "\n")
n_check = sum(len(v) for v in restricciones.values())
print(f"{destino.name}: {len(por_tabla)} tablas, {len(filas)} columnas, "
      f"{n_check} restricciones CHECK, {len(L)} lineas")
