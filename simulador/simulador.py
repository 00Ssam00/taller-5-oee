"""Simulador de telemetria hora a hora para el tablero operativo.

PARA QUE SIRVE
--------------
El requisito del proyecto pide "simular la llegada de datos hora a hora,
demostrando que el tablero y la alerta reaccionan". La fuente real es un Excel
que se digita en diferido, asi que no existe un flujo en vivo con el que probar
el tablero de Grafana. Este servicio ocupa ese lugar: escribe en
dw.hecho_produccion_hora, que es el mismo grano horario que entregaria un
historiador de PLC/SCADA el dia que la planta se instrumente.

NO ES UN GENERADOR DE RUIDO
---------------------------
Los parametros estan calibrados con el historico ya cargado:

  * La probabilidad y la duracion de los paros salen de la distribucion real
    de dw.hecho_paro, ponderada por horas perdidas. Si el sistema dosificador
    explica el 46% del tiempo perdido, aqui aparece con ese mismo peso.
  * La disponibilidad objetivo de cada maquina es la que esa maquina mostro
    en 2024, no un numero inventado.
  * La tasa ideal viene de dim_estandar (SCD2), igual que en el ETL.

Asi, cuando el tablero muestre que Vinilos_2 esta en rojo, lo estara por la
misma razon por la que lo esta en la realidad.

PARAMETROS (variables de entorno)
---------------------------------
  SIM_SEGUNDOS_POR_HORA   segundos reales que dura una hora simulada (20)
  SIM_PROB_PARO           probabilidad de que una hora tenga paro (0.35)
  SIM_FORZAR_INCIDENTE    si true, provoca un incidente sostenido en una
                          maquina para demostrar que la alerta se dispara
  SIM_HORAS_HISTORIA      horas de historia que se precargan al arrancar (48)
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

import psycopg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("simulador")

# --- Parametros -------------------------------------------------------------
SEGUNDOS_POR_HORA = float(os.getenv("SIM_SEGUNDOS_POR_HORA", "20"))
PROB_PARO = float(os.getenv("SIM_PROB_PARO", "0.35"))
FORZAR_INCIDENTE = os.getenv("SIM_FORZAR_INCIDENTE", "true").lower() == "true"
HORAS_HISTORIA = int(os.getenv("SIM_HORAS_HISTORIA", "48"))

# Maquina y momento del incidente forzado. Se elige Vinilos_2 porque es la que
# peor disponibilidad muestra en el historico (62,6% en 2024): el incidente es
# verosimil, no arbitrario.
MAQUINA_INCIDENTE = os.getenv("SIM_MAQUINA_INCIDENTE", "Vinilos_2")
HORA_INICIO_INCIDENTE = int(os.getenv("SIM_HORA_INICIO_INCIDENTE", "3"))
DURACION_INCIDENTE = int(os.getenv("SIM_DURACION_INCIDENTE", "8"))

ZONA = timezone(timedelta(hours=-5))      # America/Bogota, sin horario de verano

PUERTO_WEBHOOK = int(os.getenv("SIM_PUERTO_WEBHOOK", "9099"))


# ===========================================================================
#  Receptor de notificaciones de Grafana
# ===========================================================================
#  El punto de contacto que Grafana carga por provisioning apunta aqui. Sirve
#  para DEMOSTRAR la alerta de punta a punta: no basta con que la regla cambie
#  de estado en la interfaz, hay que probar que la notificacion sale y llega a
#  su destinatario. En produccion este destino seria el correo del coordinador
#  de mantenimiento o un canal de mensajeria; aqui es este servicio, que
#  escribe la notificacion en el log del contenedor.
#
#      docker compose logs -f simulador
# ===========================================================================
class ReceptorAlertas(BaseHTTPRequestHandler):
    def do_POST(self):                                    # noqa: N802
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo) if largo else b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"recibido":true}')

        try:
            aviso = json.loads(cuerpo)
        except json.JSONDecodeError:
            log.warning("  [ALERTA] notificacion ilegible recibida.")
            return

        estado = str(aviso.get("status", "?")).upper()
        log.info("")
        log.info("  " + "*" * 72)
        log.info("  *  NOTIFICACION DE GRAFANA RECIBIDA  -  estado: %s", estado)
        for a in aviso.get("alerts", []):
            etiquetas = a.get("labels", {})
            valores = a.get("values") or {}
            log.info("  *  regla     : %s", etiquetas.get("alertname", "?"))
            log.info("  *  linea     : %s", etiquetas.get("metric",
                                                          etiquetas.get("maquina", "?")))
            log.info("  *  severidad : %s", etiquetas.get("severidad", "?"))
            if valores:
                log.info("  *  valores   : %s",
                         ", ".join(f"{k}={v}" for k, v in valores.items()))
            resumen = (a.get("annotations") or {}).get("summary")
            if resumen:
                log.info("  *  resumen   : %s", resumen)
        log.info("  " + "*" * 72)
        log.info("")

    def log_message(self, *_args):      # silencia el log HTTP por defecto
        return


def arrancar_receptor():
    """Levanta el receptor en un hilo aparte; no debe bloquear la simulacion."""
    try:
        servidor = HTTPServer(("0.0.0.0", PUERTO_WEBHOOK), ReceptorAlertas)
    except OSError as exc:
        log.warning("No se pudo abrir el receptor de alertas en el puerto %d: %s",
                    PUERTO_WEBHOOK, exc)
        return
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    log.info("Receptor de notificaciones de Grafana escuchando en el puerto %d.",
             PUERTO_WEBHOOK)

_seguir = True


def _parar(_signo, _marco):
    global _seguir
    _seguir = False
    log.info("Senal de parada recibida; cerrando ordenadamente.")


signal.signal(signal.SIGTERM, _parar)
signal.signal(signal.SIGINT, _parar)


def conectar() -> psycopg.Connection:
    """Abre la conexion leyendo las credenciales del entorno.

    No hay ninguna cadena de conexion con contrasena en el codigo: todo viene
    de variables de entorno inyectadas por Docker Compose desde el .env, que
    esta excluido del repositorio.
    """
    for intento in range(1, 31):
        try:
            cx = psycopg.connect(
                host=os.environ["PGHOST"],
                port=os.getenv("PGPORT", "5432"),
                dbname=os.environ["PGDATABASE"],
                user=os.environ["PGUSER"],
                password=os.environ["PGPASSWORD"],
                autocommit=True,
            )
            log.info("Conectado a PostgreSQL en %s.", os.environ["PGHOST"])
            return cx
        except psycopg.OperationalError as exc:
            log.info("Esperando a la base de datos (intento %d/30): %s",
                     intento, str(exc).strip().splitlines()[0])
            time.sleep(2)
    raise SystemExit("No se pudo conectar a la base de datos.")


# ===========================================================================
class Planta:
    """Estado de las cuatro lineas, calibrado con el historico cargado."""

    def __init__(self, cx: psycopg.Connection):
        self.cx = cx
        self.rng = random.Random(20261031)   # semilla fija: simulacion repetible
        self._cargar_dimensiones()
        self._cargar_calibracion()

    # -- Dimensiones --------------------------------------------------------
    def _cargar_dimensiones(self):
        with self.cx.cursor() as cur:
            cur.execute("""
                SELECT maquina_key, codigo_maquina, nombre_maquina
                FROM dw.dim_maquina WHERE es_activa ORDER BY maquina_key
            """)
            self.maquinas = [
                {"key": k, "codigo": c, "nombre": n} for k, c, n in cur.fetchall()
            ]

            # Turnos reales de 8 horas. El turno se deduce de la hora del dia.
            cur.execute("""
                SELECT codigo_turno, turno_key, hora_inicio
                FROM dw.dim_turno WHERE es_valido AND tipo_jornada = 'Ordinario'
            """)
            self.turnos = {c: (k, hi) for c, k, hi in cur.fetchall()}

            # Operario de respaldo: el miembro 'sin informar'. El simulador NO
            # inventa personas reales; usa el miembro de relleno, coherente con
            # el tratamiento de datos personales del proyecto.
            cur.execute("""
                SELECT operario_key FROM dw.dim_operario
                WHERE NOT es_identificado ORDER BY operario_key LIMIT 1
            """)
            self.operario_key = cur.fetchone()[0]

            # Para cada maquina, el par (referencia, estandar) mas usado en el
            # historico: es el producto que esa linea realmente corre.
            cur.execute("""
                SELECT DISTINCT ON (h.maquina_key)
                       h.maquina_key, h.referencia_key, r.nombre_referencia,
                       h.tasa_ideal_unid_min, count(*) OVER (
                           PARTITION BY h.maquina_key, h.referencia_key) AS n
                FROM dw.hecho_produccion_turno h
                JOIN dw.dim_referencia r ON r.referencia_key = h.referencia_key
                WHERE h.tiene_estandar AND h.tasa_ideal_unid_min > 0
                  AND NOT r.es_no_aplica
                ORDER BY h.maquina_key, n DESC, h.referencia_key
            """)
            self.referencia = {
                mk: {"key": rk, "nombre": nom, "tasa": float(tasa)}
                for mk, rk, nom, tasa, _ in cur.fetchall()
            }

    # -- Calibracion con el historico ---------------------------------------
    def _cargar_calibracion(self):
        with self.cx.cursor() as cur:
            # Disponibilidad real de 2024 por maquina: es el objetivo que la
            # simulacion reproduce en promedio.
            cur.execute("""
                SELECT h.maquina_key,
                       sum(h.horas_operativas) / sum(h.horas_programadas)
                FROM dw.hecho_produccion_turno h
                JOIN dw.dim_fecha f ON f.fecha_key = h.fecha_key
                WHERE f.anio = 2024
                GROUP BY h.maquina_key
            """)
            self.disp_objetivo = {k: float(v) for k, v in cur.fetchall()}

            # Distribucion real de causas de paro, ponderada por horas perdidas
            # y por maquina. Es lo que hace creible el Pareto del tablero.
            cur.execute("""
                SELECT hp.maquina_key, hp.paro_key,
                       p.etiqueta_codigo_paro, p.nombre_subcodigo,
                       sum(hp.horas_paro)  AS horas,
                       avg(hp.minutos_paro) AS min_promedio
                FROM dw.hecho_paro hp
                JOIN dw.dim_paro p ON p.paro_key = hp.paro_key
                JOIN dw.dim_fecha f ON f.fecha_key = hp.fecha_key
                WHERE f.anio >= 2024 AND NOT hp.es_paro_planeado
                GROUP BY hp.maquina_key, hp.paro_key,
                         p.etiqueta_codigo_paro, p.nombre_subcodigo
                HAVING sum(hp.horas_paro) > 1
            """)
            self.causas: dict[int, list[dict]] = {}
            for mk, pk, etiqueta, sub, horas, min_prom in cur.fetchall():
                self.causas.setdefault(mk, []).append({
                    "paro_key": pk,
                    "etiqueta": etiqueta,
                    "subcodigo": sub,
                    "peso": float(horas),
                    "minutos": max(2.0, min(55.0, float(min_prom))),
                })

            # Causa dominante de cada maquina: la que se usa en el incidente
            # forzado, para que el incidente sea el escenario mas probable y
            # no una rareza.
            self.causa_dominante = {
                mk: max(lista, key=lambda c: c["peso"])
                for mk, lista in self.causas.items()
            }

        # --- Calibracion de la FRECUENCIA de paros --------------------------
        # Los paros se modelan como un proceso de Poisson: una hora puede
        # tener cero, uno o varios paros cortos, que es como se comporta una
        # linea de envasado real. La alternativa -un unico paro por hora- da
        # horas o perfectas o catastroficas, y eso no se parece a la planta.
        #
        # La intensidad lambda se despeja de la disponibilidad historica:
        #     minutos perdidos por hora = lambda x duracion media del paro
        # de modo que la simulacion converge a la disponibilidad que la
        # maquina mostro de verdad en 2024.
        #
        # SUPUESTO DECLARADO: la fuente NO registra paros individuales. Cada
        # celda del Excel es el TOTAL de minutos de ese codigo en un turno de
        # 8 horas, asi que el promedio historico (unos 30 a 48 minutos por
        # celda) no es la duracion de un paro sino la suma de varios. Para
        # repartirlos dentro de la hora se asume el patron tipico de una linea
        # de envasado: paros frecuentes y cortos. Se divide la duracion media
        # entre el numero de horas de un turno y se acota a 12 minutos, lo que
        # NO altera la disponibilidad simulada -lambda se ajusta en sentido
        # contrario- pero si produce una serie horaria legible en lugar de
        # horas alternadamente perfectas y catastroficas.
        # El dia que lleguen datos de PLC este supuesto se reemplaza por la
        # distribucion medida.
        HORAS_POR_TURNO = 8
        TOPE_DURACION_PARO = 12.0
        self.lambda_paro: dict[int, float] = {}
        self.duracion_media: dict[int, float] = {}
        for mk, lista in self.causas.items():
            peso_total = sum(c["peso"] for c in lista)
            media_turno = sum(c["minutos"] * c["peso"] for c in lista) / peso_total
            media = max(3.0, min(TOPE_DURACION_PARO, media_turno / HORAS_POR_TURNO))
            objetivo = self.disp_objetivo.get(mk, 0.75)
            minutos_esperados = (1 - objetivo) * 60
            lam = minutos_esperados / media
            # SIM_PROB_PARO actua como PISO de la frecuencia: si la
            # disponibilidad historica ya implica mas paros que ese piso, se
            # respeta el dato y no el parametro.
            piso = -math.log(1 - PROB_PARO)
            self.lambda_paro[mk] = max(lam, piso)
            self.duracion_media[mk] = media

        for m in self.maquinas:
            mk = m["key"]
            lam = self.lambda_paro.get(mk, 0.0)
            log.info("  %-10s disp. objetivo %.1f%% | %d causas | %.2f paros/hora "
                     "(%.0f%% de las horas con paro) | paro medio %.0f min | "
                     "ref. '%s' a %.0f u/min",
                     m["codigo"], 100 * self.disp_objetivo.get(mk, 0.75),
                     len(self.causas.get(mk, [])), lam,
                     100 * (1 - math.exp(-lam)), self.duracion_media.get(mk, 0),
                     self.referencia[mk]["nombre"], self.referencia[mk]["tasa"])

    # -- Generacion de una hora ---------------------------------------------
    def turno_de(self, hora: int) -> tuple[int, str]:
        if 6 <= hora < 14:
            codigo = "T1"
        elif 14 <= hora < 22:
            codigo = "T2"
        else:
            codigo = "T3"
        return self.turnos[codigo][0], codigo

    def _poisson(self, lam: float) -> int:
        """Numero de eventos en la hora. Algoritmo de Knuth, sin numpy."""
        objetivo = math.exp(-lam)
        acumulado = 1.0
        n = 0
        while True:
            acumulado *= self.rng.random()
            if acumulado <= objetivo:
                return n
            n += 1

    def _elegir_causa(self, maquina_key: int) -> dict | None:
        lista = self.causas.get(maquina_key)
        if not lista:
            return None
        pesos = [c["peso"] for c in lista]
        return self.rng.choices(lista, weights=pesos, k=1)[0]

    def generar_hora(self, instante: datetime, maquina: dict,
                     en_incidente: bool) -> dict:
        mk = maquina["key"]
        ref = self.referencia[mk]
        tasa = ref["tasa"]
        turno_key, _ = self.turno_de(instante.astimezone(ZONA).hour)

        minutos_prog = 60.0
        causa = None
        minutos_paro = 0.0

        if en_incidente:
            # Incidente sostenido: la causa dominante de la maquina deja la
            # linea parada entre 35 y 50 minutos de cada hora. Es lo que lleva
            # el OEE por debajo del umbral critico y dispara la alerta.
            causa = self.causa_dominante.get(mk)
            minutos_paro = self.rng.uniform(35.0, 50.0)
        else:
            # Numero de paros de esta hora, segun el proceso de Poisson ya
            # calibrado con la disponibilidad historica de la maquina.
            lam = self.lambda_paro.get(mk, 0.5)
            media = self.duracion_media.get(mk, 15.0)
            n_paros = self._poisson(lam)
            causas_hora = []
            for _ in range(n_paros):
                c = self._elegir_causa(mk)
                if c is None:
                    continue
                # Duracion de cada paro: distribucion asimetrica (muchos
                # cortos, pocos largos), como en el historico.
                dur = min(45.0, max(1.0, self.rng.lognormvariate(
                    math.log(media) - 0.18, 0.6)))
                causas_hora.append((c, dur))
                minutos_paro += dur
            if causas_hora:
                # Al tablero se reporta la causa que mas tiempo consumio en la
                # hora: es la que el supervisor necesita ver primero.
                causa = max(causas_hora, key=lambda x: x[1])[0]

        minutos_paro = round(min(minutos_paro, minutos_prog), 2)
        minutos_oper = round(minutos_prog - minutos_paro, 2)

        # Produccion: el rendimiento ronda el 92% del estandar, con dispersion.
        # No se fuerza a 100% -ninguna linea real corre al estandar exacto- y
        # se acota en 1,0 para no publicar un OEE superior al 100%, que en un
        # tablero operativo se lee como un error de medicion.
        u_posibles = int(round(tasa * minutos_oper))
        factor = min(1.0, max(0.0, self.rng.gauss(0.92, 0.08)))
        unidades = int(round(u_posibles * factor))
        rechazadas = int(round(unidades * max(0.0, self.rng.gauss(0.012, 0.008))))

        disponibilidad = minutos_oper / minutos_prog
        rendimiento = (unidades / u_posibles) if u_posibles > 0 else 0.0
        calidad = (1 - rechazadas / unidades) if unidades > 0 else 1.0
        oee = disponibilidad * rendimiento * calidad

        unid_paca = 24     # valor tipico; solo alimenta el conteo de pacas
        return {
            "instante": instante,
            "fecha_key": int(instante.astimezone(ZONA).strftime("%Y%m%d")),
            "hora_del_dia": instante.astimezone(ZONA).hour,
            "maquina_key": mk,
            "turno_key": turno_key,
            "referencia_key": ref["key"],
            "operario_key": self.operario_key,
            "paro_key": causa["paro_key"] if causa and minutos_paro > 0 else None,
            "minutos_programados": minutos_prog,
            "minutos_paro": minutos_paro,
            "minutos_operativos": minutos_oper,
            "pacas_producidas": unidades // unid_paca,
            "unidades_producidas": unidades,
            "unidades_rechazadas": rechazadas,
            "tasa_ideal_unid_min": round(tasa, 3),
            "unidades_posibles": u_posibles,
            "disponibilidad": round(min(disponibilidad, 9.9), 6),
            "rendimiento": round(min(rendimiento, 9.9), 6),
            "calidad": round(min(max(calidad, 0.0), 1.0), 6),
            "oee": round(min(oee, 9.9), 6),
            "_causa": causa["etiqueta"] if causa and minutos_paro > 0 else None,
        }


COLUMNAS = [
    "instante", "fecha_key", "hora_del_dia", "maquina_key", "turno_key",
    "referencia_key", "operario_key", "paro_key", "minutos_programados",
    "minutos_paro", "minutos_operativos", "pacas_producidas",
    "unidades_producidas", "unidades_rechazadas", "tasa_ideal_unid_min",
    "unidades_posibles", "disponibilidad", "rendimiento", "calidad", "oee",
]

INSERTAR = f"""
INSERT INTO dw.hecho_produccion_hora ({", ".join(COLUMNAS)})
VALUES ({", ".join("%s" for _ in COLUMNAS)})
ON CONFLICT (instante, maquina_key) DO UPDATE SET
    paro_key            = EXCLUDED.paro_key,
    minutos_paro        = EXCLUDED.minutos_paro,
    minutos_operativos  = EXCLUDED.minutos_operativos,
    pacas_producidas    = EXCLUDED.pacas_producidas,
    unidades_producidas = EXCLUDED.unidades_producidas,
    unidades_rechazadas = EXCLUDED.unidades_rechazadas,
    unidades_posibles   = EXCLUDED.unidades_posibles,
    disponibilidad      = EXCLUDED.disponibilidad,
    rendimiento         = EXCLUDED.rendimiento,
    calidad             = EXCLUDED.calidad,
    oee                 = EXCLUDED.oee,
    registrado_en       = now()
"""


def escribir(cx, filas: list[dict]):
    with cx.cursor() as cur:
        cur.executemany(INSERTAR, [[f[c] for c in COLUMNAS] for f in filas])


# ===========================================================================
def main():
    log.info("=" * 78)
    log.info("  SIMULADOR DE TELEMETRIA HORA A HORA  -  lineas de envasado")
    log.info("=" * 78)
    log.info("  Una hora simulada = %.0f s reales | prob. de paro %.0f%% | "
             "incidente forzado: %s", SEGUNDOS_POR_HORA, 100 * PROB_PARO,
             "si" if FORZAR_INCIDENTE else "no")

    arrancar_receptor()
    cx = conectar()
    planta = Planta(cx)

    ahora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    # --- Limpieza del flujo anterior ---------------------------------------
    # IMPRESCINDIBLE, y la razon merece explicacion.
    #
    # En modo acelerado el simulador adelanta el reloj de produccion: una hora
    # simulada cada SIM_SEGUNDOS_POR_HORA segundos de reloj de pared. Eso
    # significa que escribe marcas de tiempo POR DELANTE del momento actual.
    # Si el servicio se reinicia, su contador vuelve a uno y empieza a escribir
    # desde el presente, pero en la tabla siguen estando las filas de la corrida
    # anterior, que estan MAS ADELANTE en el tiempo.
    #
    # Como la vista de estado actual y la regla de alerta se anclan en
    # max(instante) -el instante mas reciente del flujo-, el ancla se quedaria
    # clavada en esas filas viejas y tanto el tablero como la alerta evaluarian
    # datos congelados de la corrida anterior. Se detecto exactamente ese
    # comportamiento: la alerta seguia disparada con un OEE de 41% mientras el
    # simulador ya reportaba 65%.
    #
    # Se borra la ventana que esta corrida va a reescribir y todo lo que quede
    # por delante. Es seguro porque dw.hecho_produccion_hora la alimenta
    # unicamente este simulador: el ETL del Excel no escribe en ella, porque la
    # fuente historica no tiene grano horario. El dia que llegue un
    # historiador de PLC, este bloque desaparece.
    desde = ahora - timedelta(hours=HORAS_HISTORIA)
    with cx.cursor() as cur:
        cur.execute("DELETE FROM dw.hecho_produccion_hora WHERE instante >= %s",
                    (desde,))
        borradas = cur.rowcount
    if borradas:
        log.info("")
        log.info("  Se descartaron %d filas de una corrida anterior del "
                 "simulador (desde %s en adelante).",
                 borradas, desde.astimezone(ZONA).strftime("%d/%m %H:00"))

    # --- Precarga de historia ----------------------------------------------
    # Sin esto el panel de series de tiempo arrancaria vacio y no se podria
    # juzgar si la linea mejora o empeora.
    log.info("")
    log.info("  Precargando %d horas de historia...", HORAS_HISTORIA)
    lote = []
    for h in range(HORAS_HISTORIA, 0, -1):
        instante = ahora - timedelta(hours=h)
        for maquina in planta.maquinas:
            lote.append(planta.generar_hora(instante, maquina, en_incidente=False))
    escribir(cx, lote)
    log.info("  %d registros precargados (%d maquinas x %d horas).",
             len(lote), len(planta.maquinas), HORAS_HISTORIA)

    # --- Bucle en vivo -----------------------------------------------------
    log.info("")
    log.info("  Generando en vivo. El tablero de Grafana debe moverse cada %.0f s.",
             SEGUNDOS_POR_HORA)
    if FORZAR_INCIDENTE:
        log.info("  INCIDENTE PROGRAMADO: %s entrara en falla sostenida en la "
                 "hora %d y durante %d horas. La alerta de OEE critico debe "
                 "pasar a estado de disparo.",
                 MAQUINA_INCIDENTE, HORA_INICIO_INCIDENTE, DURACION_INCIDENTE)

    iteracion = 0
    while _seguir:
        iteracion += 1
        instante = (datetime.now(timezone.utc)
                    .replace(minute=0, second=0, microsecond=0)
                    + timedelta(hours=iteracion))

        en_ventana = (FORZAR_INCIDENTE
                      and HORA_INICIO_INCIDENTE
                      <= iteracion
                      < HORA_INICIO_INCIDENTE + DURACION_INCIDENTE)

        filas = []
        for maquina in planta.maquinas:
            incidente = en_ventana and maquina["codigo"] == MAQUINA_INCIDENTE
            filas.append(planta.generar_hora(instante, maquina, incidente))
        escribir(cx, filas)

        resumen = "  ".join(
            f"{m['codigo'].replace('Vinilos_', 'V')}:{100 * f['oee']:4.0f}%"
            f"{'!' if f['_causa'] else ' '}"
            for m, f in zip(planta.maquinas, filas)
        )
        marca = "  <<< INCIDENTE" if en_ventana else ""
        log.info("  hora %-3d %s  |  %s%s",
                 iteracion, instante.astimezone(ZONA).strftime("%d/%m %H:00"),
                 resumen, marca)

        if en_ventana:
            causa = next(f["_causa"] for m, f in zip(planta.maquinas, filas)
                         if m["codigo"] == MAQUINA_INCIDENTE)
            log.info("            %s en falla: %s", MAQUINA_INCIDENTE, causa)

        # Espera fraccionada para poder atender SIGTERM sin demora.
        restante = SEGUNDOS_POR_HORA
        while restante > 0 and _seguir:
            time.sleep(min(0.5, restante))
            restante -= 0.5

    cx.close()
    log.info("Simulador detenido.")


if __name__ == "__main__":
    main()
