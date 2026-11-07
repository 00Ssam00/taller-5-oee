#!/usr/bin/env python3
"""Arma el PDF entregable a partir de los documentos de `docs/`.

Convierte el Markdown a un unico HTML con portada, indice y saltos de pagina,
y lo imprime con Chrome en modo headless (la unica herramienta de PDF
disponible en el equipo).

    python3 herramientas/gen_pdf.py
"""
from __future__ import annotations

import html as html_mod
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
SALIDA = RAIZ / "entregables"
# Chrome se busca segun el sistema: la ruta de macOS no existe en Windows.
# Se puede forzar con la variable de entorno CHROME.
def _buscar_chrome() -> str:
    import os, shutil, sys
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    candidatos = {
        "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "win32": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")],
    }.get(sys.platform, [])
    for c in candidatos:
        if os.path.exists(c):
            return c
    for n in ("chrome", "google-chrome", "chromium", "msedge"):
        if (hallado := shutil.which(n)):
            return hallado
    raise SystemExit("No se encontro Chrome. Defina la variable CHROME con su ruta.")

CHROME = _buscar_chrome()

AUTOR = "Samuel Alvarez Becerra"
TITULO = "Solución de Inteligencia de Negocios: OEE en líneas de envasado"
ASIGNATURA = "Inteligencia de Negocios · Proyecto Final"
# Se reemplaza por la URL real cuando el repositorio se publique.
REPOSITORIO = "(repositorio local, sin publicar aún)"

# Orden de los capitulos y su titulo en el indice.
CAPITULOS = [
    ("01-usuarios-y-preguntas-de-negocio.md", "Usuarios y preguntas de negocio"),
    ("02-diagnostico-de-la-fuente.md",        "Diagnóstico de la fuente"),
    ("03-catalogo-de-indicadores.md",         "Catálogo de indicadores"),
    ("04-modelo-dimensional.md",              "Modelo dimensional"),
    ("05-diccionario-de-datos.md",            "Diccionario de datos"),
    ("06-etl-calidad-y-conciliacion.md",      "ETL, calidad de datos y conciliación"),
    ("07-arquitectura.md",                    "Arquitectura de la solución"),
    ("08-powerbi-vs-grafana.md",              "Power BI y Grafana"),
    ("09-evolucion-plc-scada.md",             "Evolución a PLC/SCADA"),
    ("10-datos-personales-y-seguridad.md",    "Datos personales y seguridad"),
]

# Capturas de los tableros. El PDF se arma igual si todavia no existen: deja
# un recuadro indicando que falta, para que la ausencia sea visible y no un
# hueco silencioso.
EVIDENCIAS = [
    ("grafana-tablero.png",     "Grafana · tablero operativo completo"),
    ("grafana-estado-actual.png","Grafana · estado actual por máquina"),
    ("grafana-alerta.png",      "Grafana · alerta de OEE crítico disparada"),
    ("powerbi-resumen.png",     "Power BI · resumen gerencial"),
    ("powerbi-paros.png",       "Power BI · drill-down de la jerarquía de paros"),
    ("powerbi-pareto.png",      "Power BI · Pareto de causas de paro"),
    ("powerbi-tiempo.png",      "Power BI · comparativo interanual"),
]


def _md(texto: str) -> str:
    import markdown
    return markdown.markdown(
        texto,
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"],
    )


def _mermaid_a_pre(texto: str) -> str:
    """Quita los bloques Mermaid y el subtitulo que los contrasta.

    En los .md cada diagrama va dos veces: en Mermaid, para que GitHub lo
    dibuje, y en arte ASCII bajo el subtitulo "Version en texto". El PDF no
    renderiza Mermaid, asi que se queda solo con el ASCII; si ademas no se
    quitara ese subtitulo, anunciaria una version grafica que en el PDF no
    existe.
    """
    texto = re.sub(r"```mermaid.*?```", "", texto, flags=re.S)
    return re.sub(r"^#{2,4} +Versi[oó]n en texto *$\n+", "", texto, flags=re.M)


def construir_html() -> str:
    partes: list[str] = []

    # ---- Portada -------------------------------------------------------
    partes.append(f"""
<section class="portada">
  <div class="sello">{html_mod.escape(ASIGNATURA)}</div>
  <h1>{html_mod.escape(TITULO)}</h1>
  <p class="subtitulo">Diseño, implementación y despliegue contenerizado de una
     solución de BI de extremo a extremo sobre los registros de producción y
     paros de cuatro líneas de envasado</p>
  <table class="ficha">
    <tr><th>Integrante</th><td>{html_mod.escape(AUTOR)}</td></tr>
    <tr><th>Repositorio</th><td>{html_mod.escape(REPOSITORIO)}</td></tr>
    <tr><th>Fuente de datos</th><td>Seguimiento Temperas y Vinilos Actividad.xlsm<br>
        Procedimiento P-MTO-22 V1 (vigente desde el 14/05/2025)</td></tr>
    <tr><th>Motor</th><td>PostgreSQL 17 · Grafana 11.6 · Power BI (PBIP/TMDL)</td></tr>
  </table>
</section>
""")

    # ---- Indice --------------------------------------------------------
    filas = "\n".join(
        f'<li><a href="#cap{i}">{html_mod.escape(t)}</a></li>'
        for i, (_, t) in enumerate(CAPITULOS, 1)
    )
    partes.append(f"""
<section class="indice">
  <h1>Contenido</h1>
  <ol class="toc">{filas}
    <li><a href="#evidencias">Capturas de los tableros</a></li>
  </ol>
</section>
""")

    # ---- Capitulos -----------------------------------------------------
    for i, (archivo, titulo) in enumerate(CAPITULOS, 1):
        ruta = DOCS / archivo
        if not ruta.exists():
            sys.exit(f"falta {ruta}")
        texto = _mermaid_a_pre(ruta.read_text())
        # El primer encabezado del documento se sustituye por el numerado.
        texto = re.sub(r"^#\s+.*?$", "", texto, count=1, flags=re.M)
        cuerpo = _md(texto)
        partes.append(
            f'<section class="capitulo" id="cap{i}">'
            f'<h1><span class="num">{i}</span>{html_mod.escape(titulo)}</h1>'
            f"{cuerpo}</section>"
        )

    # ---- Evidencias ----------------------------------------------------
    bloques = []
    carpeta = DOCS / "evidencias"
    for nombre, pie in EVIDENCIAS:
        ruta = carpeta / nombre
        if ruta.exists():
            bloques.append(
                f'<figure><img src="evidencias/{nombre}" alt="{html_mod.escape(pie)}">'
                f"<figcaption>{html_mod.escape(pie)}</figcaption></figure>"
            )
        else:
            bloques.append(
                f'<figure class="falta"><div class="hueco">Captura pendiente:'
                f"<br><code>docs/evidencias/{nombre}</code></div>"
                f"<figcaption>{html_mod.escape(pie)}</figcaption></figure>"
            )
    partes.append(
        '<section class="capitulo" id="evidencias"><h1>'
        '<span class="num">11</span>Capturas de los tableros</h1>'
        + "\n".join(bloques)
        + "</section>"
    )

    return PLANTILLA.replace("{{CUERPO}}", "\n".join(partes))


PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>BI ProyectoFinal</title>
<style>
  @page { size: Letter; margin: 16mm 15mm; }
  @page :first { margin: 0; }

  * { box-sizing: border-box; }
  body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
         font-size: 9pt; line-height: 1.38; color: #1a1a1a; margin: 0; }

  /* --- Portada --- */
  .portada { height: 100vh; padding: 38mm 24mm; display: flex;
             flex-direction: column; justify-content: center;
             border-left: 10mm solid #1a1a1a; page-break-after: always; }
  .sello { font-size: 9pt; letter-spacing: .18em; text-transform: uppercase;
           color: #666; margin-bottom: 10mm; }
  .portada h1 { font-size: 26pt; line-height: 1.18; margin: 0 0 6mm;
                font-weight: 700; letter-spacing: -.01em; }
  .subtitulo { font-size: 11pt; color: #444; line-height: 1.5;
               margin: 0 0 14mm; max-width: 125mm; }
  table.ficha { border-collapse: collapse; font-size: 9.5pt; max-width: 140mm;
                width: auto; margin: 0; }
  table.ficha th { text-align: left; padding: 2.4mm 10mm 2.4mm 0; color: #777;
                   font-weight: 500; white-space: nowrap; vertical-align: top;
                   background: none; border: none; border-top: 1px solid #ddd;
                   font-size: 8.5pt; letter-spacing: .04em;
                   text-transform: uppercase; }
  table.ficha td { padding: 2.4mm 0; border: none; border-top: 1px solid #ddd;
                   vertical-align: top; background: none; }
  table.ficha tr:nth-child(even) td { background: none; }

  /* --- Indice --- */
  .indice { page-break-after: always; }
  .indice h1 { font-size: 20pt; margin: 0 0 8mm; }
  ol.toc { list-style: none; counter-reset: cap; padding: 0; font-size: 11pt; }
  ol.toc li { counter-increment: cap; padding: 2.6mm 0;
              border-bottom: 1px solid #eee; }
  ol.toc li::before { content: counter(cap) ". "; color: #999;
                      display: inline-block; min-width: 9mm; }
  ol.toc a { color: #1a1a1a; text-decoration: none; }

  /* --- Capitulos --- */
  .capitulo { page-break-before: always; }
  .capitulo > h1 { font-size: 16pt; margin: 0 0 4.5mm; padding-bottom: 2mm;
                   border-bottom: 2px solid #1a1a1a; font-weight: 700; }
  .capitulo > h1 .num { display: inline-block; min-width: 9mm; color: #999; }
  h2 { font-size: 11.5pt; margin: 5mm 0 2mm; font-weight: 700;
       page-break-after: avoid; }
  h3 { font-size: 10pt; margin: 3.5mm 0 1.5mm; font-weight: 700;
       page-break-after: avoid; }
  h4 { font-size: 9pt; margin: 2.5mm 0 1mm; font-weight: 700; }
  p  { margin: 0 0 2mm; text-align: justify; hyphens: auto; }
  ul, ol { margin: 0 0 2mm; padding-left: 5mm; }
  li { margin-bottom: 0.7mm; }
  strong { font-weight: 700; }

  /* --- Tablas --- */
  /* Las tablas PUEDEN partirse entre paginas. Con `avoid`, una tabla que no
     cabia en el hueco restante saltaba entera a la pagina siguiente y dejaba
     media hoja en blanco; en el diccionario, con 13 tablas largas, eso solo
     costaba seis paginas de huecos. Lo que no se parte es la fila. */
  table { border-collapse: collapse; width: 100%; font-size: 7.5pt;
          margin: 2mm 0 3.5mm; page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  thead { display: table-header-group; }   /* encabezado en cada pagina */
  th { background: #f2f2f2; text-align: left; font-weight: 700;
       padding: 1.1mm 1.5mm; border: 1px solid #ccc; }
  td { padding: 1.1mm 1.5mm; border: 1px solid #ddd; vertical-align: top; }
  /* El diccionario de datos son 187 filas de referencia, no prosa: se
     consulta puntualmente, asi que admite un cuerpo mas pequeno. Es el
     capitulo mas largo con diferencia. */
  #cap5 table { font-size: 6.6pt; table-layout: fixed; }
  #cap5 td, #cap5 th { padding: 0.8mm 1.2mm; word-wrap: break-word; }
  #cap5 h2 { margin: 3.5mm 0 1.5mm; }
  /* Reparto del ancho: por defecto el navegador daba a "Llave" —vacia en casi
     todas las filas— tanto espacio como a la descripcion, que quedaba en una
     columna estrecha y estiraba cada fila a seis o siete lineas. */
  /* Cuatro columnas. Columna y Tipo van holgadas a proposito: si un nombre
     como rendimiento_implausible o un tipo como numeric(12,6) se parten, la
     fila entera crece una linea, y son 187 filas. */
  #cap5 table th:nth-child(1), #cap5 table td:nth-child(1) { width: 21%; }
  #cap5 table th:nth-child(2), #cap5 table td:nth-child(2) { width: 15%; }
  #cap5 table th:nth-child(3), #cap5 table td:nth-child(3) { width: 9%; }
  #cap5 table th:nth-child(4), #cap5 table td:nth-child(4) { width: 55%; }
  tr:nth-child(even) td { background: #fafafa; }

  /* --- Codigo --- */
  pre { background: #f6f6f6; border: 1px solid #e0e0e0; border-left: 3px solid #999;
        padding: 1.8mm 2.2mm; font-family: "SF Mono", Menlo, Consolas, monospace;
        font-size: 6.8pt; line-height: 1.3; overflow-wrap: break-word;
        white-space: pre-wrap; margin: 1.8mm 0 2.8mm; page-break-inside: avoid; }
  code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 7.8pt;
         background: #f2f2f2; padding: 0 .6mm; border-radius: 1px; }
  pre code { background: none; padding: 0; font-size: inherit; }

  /* --- Citas --- */
  blockquote { margin: 2mm 0 2.8mm; padding: 1.8mm 3mm; background: #f7f7f7;
               border-left: 3px solid #1a1a1a; page-break-inside: avoid; }
  blockquote p:last-child { margin-bottom: 0; }

  /* --- Figuras --- */
  /* Las capturas fluyen: a ancho completo entran dos por pagina y siguen
     siendo legibles, en lugar de gastar una hoja entera cada una. */
  figure { margin: 0 0 5mm; page-break-inside: avoid; }
  figure img { width: 100%; border: 1px solid #ccc; }
  figcaption { font-size: 8pt; color: #666; margin-top: 1.5mm;
               font-style: italic; }
  figure.falta .hueco { border: 2px dashed #bbb; background: #fafafa;
                        padding: 22mm 6mm; text-align: center; color: #888;
                        font-size: 9pt; }
  figure.falta code { font-size: 8pt; }

  hr { border: none; border-top: 1px solid #ddd; margin: 3.5mm 0; }
  a { color: #1a1a1a; }
</style></head>
<body>{{CUERPO}}</body></html>
"""


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    (DOCS / "evidencias").mkdir(exist_ok=True)

    html_doc = construir_html()
    # El HTML se deja junto a docs/ para que las rutas de las imagenes
    # (evidencias/*.png) resuelvan sin copiarlas.
    tmp = DOCS / "_informe.html"
    tmp.write_text(html_doc)

    destino = SALIDA / "BI_ProyectoFinal_Alvarez_Becerra.pdf"
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={destino}", tmp.as_uri()],
        check=True, capture_output=True,
    )

    faltan = [n for n, _ in EVIDENCIAS if not (DOCS / "evidencias" / n).exists()]
    kb = destino.stat().st_size // 1024
    print(f"{destino.relative_to(RAIZ)}  ({kb} KB)")
    print(f"  capitulos : {len(CAPITULOS)}")
    print(f"  capturas  : {len(EVIDENCIAS) - len(faltan)} de {len(EVIDENCIAS)}")
    for n in faltan:
        print(f"    pendiente: docs/evidencias/{n}")


if __name__ == "__main__":
    main()
