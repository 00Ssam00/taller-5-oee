#!/usr/bin/env python3
"""Toma las capturas del tablero de Grafana para el informe.

Inicia sesion con las credenciales de `.env` (nunca se escriben en el codigo
ni en la URL: Chrome descarta las credenciales embebidas y Grafana redirige
al formulario) y guarda los PNG en `docs/evidencias/`, que es donde los busca
`gen_pdf.py`.

    set -a && . ./.env && set +a
    .venv/bin/python herramientas/gen_capturas.py

Para que la captura de la alerta la muestre DISPARADA hay que lanzarla
mientras dura el incidente forzado del simulador. El incidente empieza en la
hora `SIM_HORA_INICIO_INCIDENTE` de la simulacion en vivo, asi que lo comodo
es reiniciar el simulador y esperar a que la regla pase a `firing`:

    docker compose restart simulador
    # ...esperar ~90 s; el estado se consulta en
    # /api/prometheus/grafana/api/v1/rules
"""
from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "evidencias"
BASE = f"http://localhost:{os.environ.get('GRAFANA_PORT_HOST', '3000')}"
TABLERO = "/d/bioee-operativo/oee-operativo"
REGLA = "/alerting/grafana/bioee-alerta-oee-critico/view"

USUARIO = os.environ.get("GF_SECURITY_ADMIN_USER", "admin")
CLAVE = os.environ.get("GF_SECURITY_ADMIN_PASSWORD")

# (archivo, ruta, espera_ms, pagina_completa, densidad)
#
# La densidad baja a 1.5 en la captura de pagina completa: el tablero mide
# ~2.950 px de alto y a densidad doble el lienzo (3360 x 5900) hace caer el
# renderizador de Chrome con "Target page has been closed".
CAPTURAS = [
    ("grafana-tablero.png",
     f"{TABLERO}?kiosk&from=now-24h&to=now&theme=light", 15000, True, 1.5),
    ("grafana-estado-actual.png",
     f"{TABLERO}?kiosk&from=now-3h&to=now&theme=light", 12000, False, 2),
    ("grafana-alerta.png",
     f"{REGLA}?theme=light", 9000, True, 2),
]


def main() -> None:
    if not CLAVE:
        sys.exit("Falta GF_SECURITY_ADMIN_PASSWORD. Ejecute:  set -a; . ./.env; set +a")

    DESTINO.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        for archivo, ruta, espera, completa, densidad in CAPTURAS:
            # Un contexto nuevo por captura: encadenar varias de pagina
            # completa en el mismo agota el renderizador.
            navegador = p.chromium.launch(channel="chrome")
            contexto = navegador.new_context(
                viewport={"width": 1680, "height": 1050},
                device_scale_factor=densidad,
            )
            pagina = contexto.new_page()

            # `domcontentloaded` y no `networkidle`: el tablero refresca cada
            # 10 s, de modo que la red nunca queda en reposo.
            pagina.goto(f"{BASE}/login", wait_until="domcontentloaded")
            pagina.fill('input[name="user"]', USUARIO)
            pagina.fill('input[name="password"]', CLAVE)
            pagina.click('button[type="submit"]')
            pagina.wait_for_url(lambda u: "/login" not in u, timeout=30000)

            pagina.goto(BASE + ruta, wait_until="domcontentloaded")
            pagina.wait_for_timeout(espera)

            salida = DESTINO / archivo
            pagina.screenshot(path=str(salida), full_page=completa)
            print(f"  {archivo:28s} {salida.stat().st_size // 1024:5d} KB")
            navegador.close()


if __name__ == "__main__":
    main()
