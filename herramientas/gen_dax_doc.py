# -*- coding: utf-8 -*-
"""Extrae las medidas del TMDL y genera MEDIDAS-DAX.md.

El documento se GENERA desde el modelo, no se escribe a mano, para que no
pueda quedar desactualizado respecto de lo que Power BI realmente carga.
"""
import pathlib, re, collections

BASE = pathlib.Path(__file__).resolve().parent.parent / "powerbi"
DEF = BASE / "OEE-Envasado.SemanticModel" / "definition" / "tables"

medidas = []
for archivo in sorted(DEF.glob("*.tmdl")):
    tabla = archivo.stem
    # splitlines() y no split("\n"): Power BI Desktop reescribe los TMDL con
    # CRLF cuando el proyecto se guarda en Windows, y el "\r" colgando al final
    # de cada linea rompia todas las expresiones regulares ancladas con "$".
    lineas = archivo.read_text(encoding="utf-8-sig").splitlines()
    i = 0
    doc = []
    while i < len(lineas):
        ln = lineas[i]
        if re.match(r"^\t/// ", ln):
            doc.append(ln.strip()[4:])
            i += 1
            continue
        # El nombre va entre comillas simples solo si lleva espacios o signos;
        # la expresion va en la misma linea si es corta, o sangrada debajo.
        m = re.match(r"^\tmeasure (?:'([^']+)'|([^ =]+)) = ?(.*)$", ln)
        if m:
            nombre = m.group(1) or m.group(2)
            resto = m.group(3).strip()
            i += 1
            expr = [resto] if resto else []
            while i < len(lineas) and lineas[i].startswith("\t\t\t"):
                expr.append(lineas[i][3:])
                i += 1
            fmt = carpeta = None
            while i < len(lineas) and lineas[i].startswith("\t\t"):
                if lineas[i].strip().startswith("formatString:"):
                    fmt = lineas[i].split(":", 1)[1].strip()
                if lineas[i].strip().startswith("displayFolder:"):
                    carpeta = lineas[i].split(":", 1)[1].strip()
                i += 1
            medidas.append({"tabla": tabla, "nombre": nombre,
                            "desc": " ".join(doc), "expr": "\n".join(expr),
                            "fmt": fmt, "carpeta": carpeta or "Sin carpeta"})
            doc = []
            continue
        if ln.strip() == "" or not ln.startswith("\t/// "):
            doc = []
        i += 1

grupos = collections.OrderedDict()
for m in sorted(medidas, key=lambda x: (x["carpeta"], x["nombre"])):
    grupos.setdefault(m["carpeta"], []).append(m)

L = [
 "# Catálogo de medidas DAX",
 "",
 "**Este archivo se genera automáticamente** desde los archivos TMDL del",
 "modelo semántico (`herramientas/gen_dax_doc.py`), para que no pueda quedar",
 "desactualizado respecto de lo que Power BI carga de verdad.",
 "",
 f"El modelo define **{len(medidas)} medidas**, agrupadas en",
 f"{len(grupos)} carpetas de visualización.",
 "",
 "Sirve para dos cosas: documentar el modelo semántico en el PDF entregable,",
 "y tener las expresiones listas para pegar si hubiera que recrear alguna",
 "medida a mano.",
 "",
 "## Índice",
 "",
]
for carpeta, ms in grupos.items():
    L.append(f"- **{carpeta}** — {', '.join('`' + m['nombre'] + '`' for m in ms)}")
L.append("")

for carpeta, ms in grupos.items():
    L += ["---", "", f"## {carpeta}", ""]
    for m in ms:
        L.append(f"### `{m['nombre']}`")
        L.append("")
        L.append(f"*Tabla:* `{m['tabla']}`" +
                 (f" · *Formato:* `{m['fmt']}`" if m["fmt"] else ""))
        L.append("")
        if m["desc"]:
            L.append(m["desc"])
            L.append("")
        L.append("```dax")
        L.append(f"{m['nombre']} =")
        L.append(m["expr"])
        L.append("```")
        L.append("")

destino = BASE / "MEDIDAS-DAX.md"
destino.write_text("\n".join(L))
print(f"{destino.name}: {len(medidas)} medidas en {len(grupos)} carpetas, "
      f"{len(L)} lineas")
for c, ms in grupos.items():
    print(f"  {c:32s} {len(ms)} medidas")
