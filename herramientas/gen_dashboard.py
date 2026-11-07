import pathlib
import json

DS = {"type": "postgres", "uid": "bioee-postgres"}
UMBRAL_CRITICO, META_OEE = 50, 65

def sql(q):
    return [{"datasource": DS, "format": "table", "rawQuery": True,
             "rawSql": q, "refId": "A", "editorMode": "code"}]

def ts(q):
    return [{"datasource": DS, "format": "time_series", "rawQuery": True,
             "rawSql": q, "refId": "A", "editorMode": "code"}]

def pct_field(unidad="percent", decimales=1, umbrales=True):
    cfg = {"unit": unidad, "decimals": decimales, "min": 0, "max": 100}
    if umbrales:
        cfg["thresholds"] = {"mode": "absolute", "steps": [
            {"color": "red", "value": None},
            {"color": "orange", "value": UMBRAL_CRITICO},
            {"color": "green", "value": META_OEE}]}
    return cfg

FILTRO = ("m.codigo_maquina IN (${maquina:sqlstring})\n"
          "      AND t.codigo_turno IN (${turno:sqlstring})")

paneles = []
pid = 0
def nuevo(**kw):
    global pid
    pid += 1
    kw["id"] = pid
    paneles.append(kw)
    return kw

# ---------------------------------------------------------------- fila 1
nuevo(type="row", title="Estado actual de la planta", collapsed=False,
      gridPos={"h": 1, "w": 24, "x": 0, "y": 0}, panels=[])

nuevo(type="bargauge", title="OEE actual por linea",
      description=("OEE de la ultima hora reportada por cada linea. Verde: "
                   f"cumple la meta de {META_OEE}%. Naranja: por debajo de la "
                   f"meta. Rojo: por debajo del umbral critico de "
                   f"{UMBRAL_CRITICO}%, que es el que dispara la alerta."),
      datasource=DS, gridPos={"h": 8, "w": 7, "x": 0, "y": 1},
      targets=sql("""SELECT codigo_maquina AS "Linea", oee_pct AS "OEE"
FROM dw.v_estado_actual_maquina
WHERE codigo_maquina IN (${maquina:sqlstring})
ORDER BY codigo_maquina"""),
      fieldConfig={"defaults": pct_field(), "overrides": []},
      options={"displayMode": "gradient", "orientation": "horizontal",
               "showUnfilled": True, "minVizHeight": 24, "minVizWidth": 8,
               "valueMode": "color", "namePlacement": "left",
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/^OEE$/",
                                 "values": True}})

nuevo(type="stat", title="Lineas en estado critico",
      description=(f"Cuantas lineas estan por debajo del {UMBRAL_CRITICO}% de "
                   "OEE en este momento. Es el numero que el supervisor mira "
                   "primero al entrar al turno."),
      datasource=DS, gridPos={"h": 4, "w": 5, "x": 7, "y": 1},
      targets=sql(f"""SELECT count(*) AS "Lineas criticas"
FROM dw.v_estado_actual_maquina
WHERE codigo_maquina IN (${{maquina:sqlstring}})
  AND oee_pct < {UMBRAL_CRITICO}"""),
      fieldConfig={"defaults": {"unit": "short", "decimals": 0,
                                "thresholds": {"mode": "absolute", "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "orange", "value": 1},
                                    {"color": "red", "value": 2}]}},
                   "overrides": []},
      options={"colorMode": "background", "graphMode": "none",
               "textMode": "auto", "justifyMode": "center",
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                 "values": False}})

nuevo(type="stat", title="Lineas sin reportar (>90 min)",
      description=("Lineas que no envian dato desde hace mas de 90 minutos. "
                   "Un tablero en verde porque no llega informacion es peor "
                   "que un tablero en rojo: este panel evita ese engaño."),
      datasource=DS, gridPos={"h": 4, "w": 5, "x": 7, "y": 5},
      targets=sql("""SELECT count(*) AS "Sin reportar"
FROM dw.v_estado_actual_maquina
WHERE codigo_maquina IN (${maquina:sqlstring})
  AND NOT esta_reportando"""),
      fieldConfig={"defaults": {"unit": "short", "decimals": 0,
                                "thresholds": {"mode": "absolute", "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "red", "value": 1}]}},
                   "overrides": []},
      options={"colorMode": "background", "graphMode": "none",
               "textMode": "auto", "justifyMode": "center",
               "reduceOptions": {"calcs": ["lastNotNull"], "fields": "",
                                 "values": False}})

nuevo(type="table", title="Detalle del estado actual por linea",
      description=("Una fila por maquina con su ultimo registro: turno, "
                   "referencia en proceso, causa del paro vigente y los tres "
                   "componentes del OEE. Es la pantalla de piso de planta."),
      datasource=DS, gridPos={"h": 8, "w": 12, "x": 12, "y": 1},
      targets=sql("""SELECT
    codigo_maquina          AS "Linea",
    semaforo                AS "Estado",
    oee_pct                 AS "OEE",
    disponibilidad_pct      AS "Disponibilidad",
    rendimiento_pct         AS "Rendimiento",
    calidad_pct             AS "Calidad",
    codigo_turno            AS "Turno",
    nombre_referencia       AS "Referencia",
    coalesce(causa_paro_actual, 'Sin paro') AS "Causa del paro",
    minutos_paro            AS "Min. paro",
    unidades_producidas     AS "Unidades",
    round(minutos_desde_registro) AS "Min. desde el dato"
FROM dw.v_estado_actual_maquina
WHERE codigo_maquina IN (${maquina:sqlstring})
ORDER BY oee_pct NULLS FIRST"""),
      fieldConfig={"defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
                   "overrides": [
          {"matcher": {"id": "byRegexp", "options": "OEE|Disponibilidad|Rendimiento|Calidad"},
           "properties": [{"id": "unit", "value": "percent"},
                          {"id": "decimals", "value": 1},
                          {"id": "custom.cellOptions",
                           "value": {"type": "color-background", "mode": "gradient"}},
                          {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                              {"color": "red", "value": None},
                              {"color": "orange", "value": UMBRAL_CRITICO},
                              {"color": "green", "value": META_OEE}]}}]},
          {"matcher": {"id": "byName", "options": "Estado"},
           "properties": [{"id": "custom.cellOptions",
                           "value": {"type": "color-text"}},
                          {"id": "mappings", "value": [
              {"type": "value", "options": {
                  "Critico": {"color": "red", "index": 0},
                  "Bajo la meta": {"color": "orange", "index": 1},
                  "En meta": {"color": "green", "index": 2}}}]}]}]},
      options={"showHeader": True, "cellHeight": "sm",
               "sortBy": [{"displayName": "OEE", "desc": False}],
               "footer": {"show": False, "reducer": ["sum"], "countRows": False,
                          "fields": ""}})

# ---------------------------------------------------------------- fila 2
nuevo(type="row", title="Tendencia hora a hora", collapsed=False,
      gridPos={"h": 1, "w": 24, "x": 0, "y": 9}, panels=[])

nuevo(type="timeseries", title="OEE hora a hora por linea",
      description=("Serie de tiempo del OEE de cada linea. La linea punteada "
                   f"roja es el umbral critico ({UMBRAL_CRITICO}%) y la verde "
                   f"la meta ({META_OEE}%). Cuando el simulador provoca el "
                   "incidente, la curva de la linea afectada cruza el umbral "
                   "rojo y la alerta pasa a estado de disparo."),
      datasource=DS, gridPos={"h": 9, "w": 14, "x": 0, "y": 10},
      targets=ts(f"""SELECT
    $__timeGroupAlias(k.instante, $intervalo),
    k.codigo_maquina AS metric,
    avg(k.oee_pct)   AS "OEE"
FROM dw.v_kpi_hora k
JOIN dw.dim_maquina m ON m.codigo_maquina = k.codigo_maquina
JOIN dw.dim_turno   t ON t.codigo_turno   = k.codigo_turno
WHERE $__timeFilter(k.instante)
  AND {FILTRO}
GROUP BY 1, 2
ORDER BY 1"""),
      fieldConfig={"defaults": {**pct_field(umbrales=False),
          "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 8,
                     "showPoints": "never", "spanNulls": False,
                     "pointSize": 5, "axisSoftMin": 0, "axisSoftMax": 100,
                     "gradientMode": "opacity",
                     "scaleDistribution": {"type": "linear"}},
          "thresholds": {"mode": "absolute", "steps": [
              {"color": "transparent", "value": None}]}},
          "overrides": []},
      options={"legend": {"displayMode": "table", "placement": "right",
                          "showLegend": True,
                          "calcs": ["lastNotNull", "mean", "min"]},
               "tooltip": {"mode": "multi", "sort": "desc"}})

nuevo(type="timeseries", title="Componentes del OEE (planta)",
      description=("Descompone el OEE en Disponibilidad, Rendimiento y "
                   "Calidad. Permite ver si el problema es que la maquina "
                   "esta parada, que corre lenta o que produce reproceso: son "
                   "tres responsables distintos."),
      datasource=DS, gridPos={"h": 9, "w": 10, "x": 14, "y": 10},
      targets=ts(f"""SELECT
    $__timeGroupAlias(k.instante, $intervalo),
    round(100 * sum(k.minutos_operativos) / sum(k.minutos_operativos + k.minutos_paro), 2) AS "Disponibilidad",
    round(100 * sum(k.unidades_producidas)::numeric / nullif(sum(k.unidades_posibles), 0), 2) AS "Rendimiento",
    round(100 * (1 - sum(k.unidades_rechazadas)::numeric / nullif(sum(k.unidades_producidas), 0)), 2) AS "Calidad"
FROM dw.v_kpi_hora k
JOIN dw.dim_maquina m ON m.codigo_maquina = k.codigo_maquina
JOIN dw.dim_turno   t ON t.codigo_turno   = k.codigo_turno
WHERE $__timeFilter(k.instante)
  AND {FILTRO}
GROUP BY 1
ORDER BY 1"""),
      fieldConfig={"defaults": {**pct_field(umbrales=False),
          "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 0,
                     "showPoints": "never", "spanNulls": True,
                     "axisSoftMin": 0, "axisSoftMax": 100,
                     "scaleDistribution": {"type": "linear"}}},
          "overrides": []},
      options={"legend": {"displayMode": "list", "placement": "bottom",
                          "showLegend": True, "calcs": ["mean"]},
               "tooltip": {"mode": "multi", "sort": "desc"}})

nuevo(type="timeseries", title="Minutos de paro por hora, segun la causa",
      description=("Barras apiladas: cuanto tiempo perdio la planta en cada "
                   "hora y por que. Responde '¿que paso anoche?' sin "
                   "tener que abrir el Excel."),
      datasource=DS, gridPos={"h": 8, "w": 24, "x": 0, "y": 19},
      targets=ts(f"""SELECT
    $__timeGroupAlias(k.instante, $intervalo),
    coalesce(k.causa_paro, 'Sin paro') AS metric,
    sum(k.minutos_paro)                AS "Minutos de paro"
FROM dw.v_kpi_hora k
JOIN dw.dim_maquina m ON m.codigo_maquina = k.codigo_maquina
JOIN dw.dim_turno   t ON t.codigo_turno   = k.codigo_turno
WHERE $__timeFilter(k.instante)
  AND k.minutos_paro > 0
  AND {FILTRO}
GROUP BY 1, 2
ORDER BY 1"""),
      fieldConfig={"defaults": {"unit": "m", "decimals": 0,
          "custom": {"drawStyle": "bars", "lineWidth": 0, "fillOpacity": 85,
                     "stacking": {"mode": "normal", "group": "A"},
                     "showPoints": "never", "barAlignment": 0,
                     "scaleDistribution": {"type": "linear"}}},
          "overrides": []},
      options={"legend": {"displayMode": "table", "placement": "right",
                          "showLegend": True, "calcs": ["sum"]},
               "tooltip": {"mode": "multi", "sort": "desc"}})

# ---------------------------------------------------------------- fila 3
nuevo(type="row", title="Analisis de causas (Pareto)", collapsed=False,
      gridPos={"h": 1, "w": 24, "x": 0, "y": 27}, panels=[])

nuevo(type="barchart", title="Pareto de causas de paro del periodo",
      description=("Las causas ordenadas por tiempo perdido en el rango de "
                   "tiempo seleccionado. Es el mismo Pareto que el tablero "
                   "de Power BI, pero sobre el dato de la ultima hora en vez "
                   "del cierre mensual."),
      datasource=DS, gridPos={"h": 9, "w": 13, "x": 0, "y": 28},
      targets=sql(f"""SELECT
    k.causa_paro            AS "Causa",
    round(sum(k.minutos_paro) / 60.0, 2) AS "Horas perdidas"
FROM dw.v_kpi_hora k
JOIN dw.dim_maquina m ON m.codigo_maquina = k.codigo_maquina
JOIN dw.dim_turno   t ON t.codigo_turno   = k.codigo_turno
WHERE $__timeFilter(k.instante)
  AND k.causa_paro IS NOT NULL
  AND {FILTRO}
GROUP BY 1
ORDER BY 2 DESC
LIMIT 12"""),
      fieldConfig={"defaults": {"unit": "h", "decimals": 2,
          "custom": {"lineWidth": 1, "fillOpacity": 80, "gradientMode": "hue",
                     "axisPlacement": "auto"}},
          "overrides": []},
      options={"orientation": "horizontal", "showValue": "auto",
               "stacking": "none", "xTickLabelRotation": 0,
               "xTickLabelMaxLength": 38, "barWidth": 0.8, "groupWidth": 0.7,
               "legend": {"showLegend": False, "displayMode": "list",
                          "placement": "bottom", "calcs": []},
               "tooltip": {"mode": "single", "sort": "none"}})

nuevo(type="table", title="Causas con porcentaje acumulado",
      description=("La misma informacion con el porcentaje acumulado, para "
                   "identificar el 20% de causas que explica el 80% del "
                   "tiempo perdido. Las filas marcadas como 'vital' son "
                   "las que deben entrar al plan de mantenimiento."),
      datasource=DS, gridPos={"h": 9, "w": 11, "x": 13, "y": 28},
      targets=sql(f"""WITH causas AS (
    SELECT k.causa_paro, k.area_impacto,
           sum(k.minutos_paro) / 60.0 AS horas,
           count(*) FILTER (WHERE k.minutos_paro > 0) AS eventos
    FROM dw.v_kpi_hora k
    JOIN dw.dim_maquina m ON m.codigo_maquina = k.codigo_maquina
    JOIN dw.dim_turno   t ON t.codigo_turno   = k.codigo_turno
    WHERE $__timeFilter(k.instante)
      AND k.causa_paro IS NOT NULL
      AND {FILTRO}
    GROUP BY 1, 2
)
SELECT
    causa_paro   AS "Causa",
    area_impacto AS "Area",
    round(horas, 2) AS "Horas",
    eventos         AS "Eventos",
    round(100 * horas / sum(horas) OVER (), 1) AS "% del total",
    round(100 * sum(horas) OVER (ORDER BY horas DESC
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
          / sum(horas) OVER (), 1) AS "% acumulado",
    CASE WHEN 100 * sum(horas) OVER (ORDER BY horas DESC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / sum(horas) OVER () <= 80
         THEN 'Vital' ELSE 'Trivial' END AS "Pareto"
FROM causas
ORDER BY horas DESC"""),
      fieldConfig={"defaults": {"custom": {"align": "auto",
                                           "cellOptions": {"type": "auto"}}},
          "overrides": [
              {"matcher": {"id": "byName", "options": "% acumulado"},
               "properties": [{"id": "unit", "value": "percent"},
                              {"id": "custom.cellOptions",
                               "value": {"type": "gauge", "mode": "gradient"}},
                              {"id": "max", "value": 100},
                              {"id": "min", "value": 0}]},
              {"matcher": {"id": "byName", "options": "Pareto"},
               "properties": [{"id": "custom.cellOptions",
                               "value": {"type": "color-text"}},
                              {"id": "mappings", "value": [
                   {"type": "value", "options": {
                       "Vital": {"color": "red", "index": 0},
                       "Trivial": {"color": "text", "index": 1}}}]}]}]},
      options={"showHeader": True, "cellHeight": "sm",
               "footer": {"show": True, "reducer": ["sum"],
                          "countRows": False, "fields": ["Horas"]}})

# ---------------------------------------------------------------- variables
plantilla = {"list": [
    {"name": "maquina", "label": "Linea de envasado", "type": "query",
     "datasource": DS, "refresh": 1, "multi": True, "includeAll": True,
     "allValue": None, "sort": 1, "hide": 0,
     "description": "Filtra todos los paneles por una o varias lineas.",
     "definition": "SELECT codigo_maquina FROM dw.dim_maquina WHERE es_activa ORDER BY 1",
     "query": "SELECT codigo_maquina FROM dw.dim_maquina WHERE es_activa ORDER BY 1",
     "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    {"name": "turno", "label": "Turno", "type": "query",
     "datasource": DS, "refresh": 1, "multi": True, "includeAll": True,
     "allValue": None, "sort": 1, "hide": 0,
     "description": "Filtra los paneles de tendencia por turno de trabajo.",
     "definition": "SELECT codigo_turno FROM dw.dim_turno WHERE es_valido ORDER BY orden_presentacion",
     "query": "SELECT codigo_turno FROM dw.dim_turno WHERE es_valido ORDER BY orden_presentacion",
     "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    {"name": "intervalo", "label": "Agrupacion temporal", "type": "interval",
     "hide": 0, "auto": False, "multi": False,
     "description": "Tamano del intervalo con que se agrupan las series.",
     "query": "1h,3h,6h,12h,1d",
     "options": [{"text": v, "value": v, "selected": v == "1h"}
                 for v in ["1h", "3h", "6h", "12h", "1d"]],
     "current": {"selected": True, "text": "1h", "value": "1h"}}]}

tablero = {
    "uid": "bioee-operativo",
    "title": "OEE operativo - lineas de envasado",
    "description": ("Tablero OPERATIVO. Responde '¿como esta la planta "
                    "ahora mismo y que la esta frenando?'. Usuario: supervisor "
                    "de produccion y coordinador de mantenimiento, en pantalla "
                    "de piso de planta. Se refresca cada 10 s sobre "
                    "dw.hecho_produccion_hora. El analisis mensual y "
                    "comparativo entre periodos NO vive aqui: vive en Power BI."),
    "tags": ["oee", "operativo", "envasado", "bi-proyecto-final"],
    "timezone": "America/Bogota",
    "editable": True,
    "graphTooltip": 1,
    "schemaVersion": 39,
    "version": 1,
    "refresh": "10s",
    "time": {"from": "now-24h", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m"],
                   "hidden": False},
    "fiscalYearStartMonth": 0,
    "weekStart": "monday",
    "links": [],
    "annotations": {"list": [{
        "name": "Anotaciones", "builtIn": 1, "type": "dashboard",
        "datasource": {"type": "grafana", "uid": "-- Grafana --"},
        "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)"}]},
    "templating": plantilla,
    "panels": paneles,
}

with open(pathlib.Path(__file__).resolve().parent.parent
          / "grafana" / "dashboards" / "oee-operativo.json", "w") as f:
    json.dump(tablero, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"tablero escrito: {len(paneles)} paneles, "
      f"{len(plantilla['list'])} variables")
