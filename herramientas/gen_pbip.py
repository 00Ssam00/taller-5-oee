# -*- coding: utf-8 -*-
"""Genera el proyecto Power BI en formato PBIP con modelo semantico en TMDL."""
import pathlib
import json, os, pathlib, uuid

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "powerbi"
NOMBRE = "OEE-Envasado"
SM = RAIZ / f"{NOMBRE}.SemanticModel"
RP = RAIZ / f"{NOMBRE}.Report"
HOST = "192.168.1.49:55432"
BD = "bi_oee"

NS = uuid.UUID("6b1e0c1a-9f3d-4a7b-8e2c-5d4f3a2b1c0d")
def lt(*partes):
    return str(uuid.uuid5(NS, "/".join(partes)))

T = "\t"
def esc(txt):
    return txt

# ===========================================================================
#  Definicion de las tablas: (nombre PBI, esquema.objeto, descripcion, columnas)
#  columna = (nombre, tipo, resumen, descripcion, formato|None, oculta)
# ===========================================================================
TEXTO, ENTERO, DECIMAL, FECHA, BOOL = "string", "int64", "double", "dateTime", "boolean"

TABLAS = [
 ("Fecha", "dw.dim_fecha",
  "Dimension de calendario construida por el equipo. Cubre 2022-2026 e incluye "
  "los festivos de Colombia calculados con la Ley 51 de 1983 (Emiliani). Es la "
  "tabla marcada como tabla de fechas, requisito para las funciones de "
  "inteligencia de tiempo de DAX.",
  [("fecha_key", ENTERO, "none", "Llave surrogada con formato AAAAMMDD.", "0", True),
   ("fecha", FECHA, "none", "Fecha del calendario. Columna marcada como fecha del modelo.", "dd/MM/yyyy", False),
   ("anio", ENTERO, "none", "Ano del calendario.", "0", False),
   ("trimestre", ENTERO, "none", "Numero de trimestre, 1 a 4.", "0", True),
   ("nombre_trimestre", TEXTO, "none", "Trimestre como texto, por ejemplo T1.", None, False),
   ("mes", ENTERO, "none", "Numero de mes, 1 a 12. Ordena el nombre del mes.", "0", True),
   ("nombre_mes", TEXTO, "none", "Nombre del mes en espanol.", None, False),
   ("anio_mes", ENTERO, "none", "Periodo como entero AAAAMM, para ordenar.", "0", True),
   ("etiqueta_anio_mes", TEXTO, "none", "Periodo legible, por ejemplo 2024-03.", None, False),
   ("dia", ENTERO, "none", "Dia del mes.", "0", True),
   ("nombre_dia", TEXTO, "none", "Nombre del dia de la semana.", None, False),
   ("dia_semana_iso", ENTERO, "none", "Dia de la semana ISO, 1 lunes a 7 domingo.", "0", True),
   ("semana_iso", ENTERO, "none", "Numero de semana ISO.", "0", False),
   ("es_festivo", BOOL, "none", "Verdadero si es festivo en Colombia.", None, False),
   ("es_dia_habil", BOOL, "none", "Verdadero si no es fin de semana ni festivo.", None, False)]),

 ("Maquina", "dw.dim_maquina",
  "Las cuatro lineas de envasado. El factor de produccion es el multiplicador "
  "de capacidad de la linea, que estaba escondido dentro de una formula de "
  "texto en la hoja Tiempos del Excel.",
  [("maquina_key", ENTERO, "none", "Llave surrogada.", "0", True),
   ("codigo_maquina", TEXTO, "none", "Codigo de la linea, Vinilos_1 a Vinilos_4.", None, False),
   ("nombre_maquina", TEXTO, "none", "Nombre legible de la linea.", None, False),
   ("numero_linea", ENTERO, "none", "Numero de linea, para ordenar.", "0", True),
   ("familia_producto", TEXTO, "none", "Familia de producto que envasa la linea.", None, False),
   ("grupo_capacidad", TEXTO, "none", "Agrupacion por capacidad relativa.", None, False),
   ("factor_produccion", DECIMAL, "none", "Multiplicador de capacidad de la linea.", "0.000", False)]),

 ("Turno", "dw.dim_turno",
  "Los turnos de trabajo. Incluye los miembros de relleno 'No aplica' y "
  "'Descanso' para no usar NULL en la tabla de hechos.",
  [("turno_key", ENTERO, "none", "Llave surrogada.", "0", True),
   ("codigo_turno", TEXTO, "none", "Codigo corto del turno.", None, False),
   ("nombre_turno", TEXTO, "none", "Nombre del turno con su horario.", None, False),
   ("duracion_horas", DECIMAL, "none", "Duracion nominal del turno en horas.", "0.0", False),
   ("tipo_jornada", TEXTO, "none", "Ordinario, Extendido o No aplica.", None, False),
   ("es_nocturno", BOOL, "none", "Verdadero si el turno es nocturno.", None, False),
   ("orden_presentacion", ENTERO, "none", "Orden de presentacion del turno.", "0", True),
   ("es_valido", BOOL, "none", "Falso para los miembros de relleno.", None, False)]),

 ("Referencia", "dw.dim_referencia",
  "Catalogo de productos envasados, depurado: la fuente traia 52 referencias "
  "con erratas de digitacion que se consolidaron en 63 miembros limpios.",
  [("referencia_key", ENTERO, "none", "Llave surrogada.", "0", True),
   ("nombre_referencia", TEXTO, "none", "Nombre de la referencia.", None, False),
   ("linea_comercial", TEXTO, "none", "Linea comercial del producto.", None, False),
   ("volumen_cc", DECIMAL, "none", "Volumen del envase en centimetros cubicos.", "0.0", False),
   ("etiqueta_presentacion", TEXTO, "none", "Presentacion legible del producto.", None, False),
   ("numero_colores", ENTERO, "none", "Numero de colores de la presentacion.", "0", False),
   ("unidades_por_paca", ENTERO, "none", "Unidades que contiene una paca. Convierte pacas a unidades comparables.", "0", False),
   ("es_no_aplica", BOOL, "none", "Verdadero para el miembro de relleno.", None, False)]),

 ("Paro", "dw.dim_paro",
  "Dimension de causas de paro con la jerarquia de cuatro niveles. Es la tabla "
  "sobre la que se hace el drill-down del tablero. El nombre del sistema es un "
  "atributo CONFORMADO construido por el equipo: une las ramas 1.x (falla "
  "electromecanica), 3.x (servicios) y 5.x (ajuste operativo) en el sistema "
  "fisico de la maquina, algo que el Excel no puede hacer porque esas ramas "
  "viven en columnas separadas.",
  [("paro_key", ENTERO, "none", "Llave surrogada.", "0", True),
   ("area_impacto", TEXTO, "none", "Nivel 1 de la jerarquia: area responsable del paro.", None, False),
   ("codigo_paro", TEXTO, "none", "Codigo de paro de dos digitos.", None, True),
   ("etiqueta_codigo_paro", TEXTO, "none", "Nivel 2 de la jerarquia: codigo con su descripcion.", None, False),
   ("nombre_codigo_paro", TEXTO, "none", "Descripcion del codigo de paro.", None, True),
   ("naturaleza_paro", TEXTO, "none", "Planeado o No planeado. Separa el tiempo perdido evitable del inevitable.", None, False),
   ("es_imputable_mantenimiento", BOOL, "none", "Verdadero si el paro es responsabilidad de mantenimiento.", None, False),
   ("nombre_sistema", TEXTO, "none", "Nivel 3 de la jerarquia: sistema fisico de la maquina. Atributo conformado.", None, False),
   ("codigo_subcodigo", TEXTO, "none", "Codigo del subcodigo de causa raiz.", None, True),
   ("nombre_subcodigo", TEXTO, "none", "Nivel 4 de la jerarquia: causa raiz concreta.", None, False),
   ("nivel_detalle", ENTERO, "none", "Profundidad real del miembro en la jerarquia desbalanceada.", "0", False),
   ("orden_presentacion", ENTERO, "none", "Orden de presentacion.", "0", True)]),

 ("Operario", "dw.dim_operario",
  "Personal de envasado PSEUDONIMIZADO. Solo contiene el alias 'Operario NNN'. "
  "El nombre real vive en el esquema pii, al que el rol de lectura que usa "
  "Power BI NO tiene acceso, de modo que el informe no puede reidentificar a "
  "nadie ni por error.",
  [("operario_key", ENTERO, "none", "Llave surrogada.", "0", True),
   ("alias_operario", TEXTO, "none", "Alias pseudonimizado del operario.", None, False),
   ("rol", TEXTO, "none", "Rol del trabajador.", None, False),
   ("es_identificado", BOOL, "none", "Falso para el miembro 'Sin informar'.", None, False),
   ("turnos_registrados", ENTERO, "sum", "Numero de turnos en que aparece.", "0", False)]),

 ("Produccion por turno", "dw.hecho_produccion_turno",
  "TABLA DE HECHOS. Grano declarado: un registro por turno de produccion de "
  "una maquina en una fecha, para una referencia. 5.138 filas.",
  [("fecha_key", ENTERO, "none", "Llave a Fecha.", "0", True),
   ("maquina_key", ENTERO, "none", "Llave a Maquina.", "0", True),
   ("turno_key", ENTERO, "none", "Llave a Turno.", "0", True),
   ("operario_key", ENTERO, "none", "Llave a Operario.", "0", True),
   ("referencia_key", ENTERO, "none", "Llave a Referencia.", "0", True),
   ("horas_programadas", DECIMAL, "sum", "Horas trabajadas programadas en el turno.", "0.0", True),
   ("horas_paro_total", DECIMAL, "sum", "Horas totales de paro del turno.", "0.0", True),
   ("horas_paro_planeado", DECIMAL, "sum", "Horas de paro planeado.", "0.0", True),
   ("horas_paro_no_planeado", DECIMAL, "sum", "Horas de paro no planeado, es decir evitable.", "0.0", True),
   ("horas_operativas", DECIMAL, "sum", "Horas programadas menos paro.", "0.0", True),
   ("eventos_paro", ENTERO, "sum", "Numero de eventos de paro del turno.", "0", True),
   ("pacas_producidas", ENTERO, "sum", "Pacas producidas.", "0", True),
   ("unidades_producidas", ENTERO, "sum", "Pacas convertidas a unidades comparables.", "0", True),
   ("unidades_posibles", ENTERO, "sum", "Unidades que el estandar permitiria en el tiempo operativo.", "0", True),
   ("unidades_perdidas_paro", ENTERO, "sum", "Unidades que se dejaron de producir por los paros.", "0", True),
   ("tiene_estandar", BOOL, "none", "Verdadero si existe estandar de ingenieria para el par maquina-referencia.", None, False),
   ("rendimiento_implausible", BOOL, "none", "Verdadero si el rendimiento supera el 150% del maximo teorico: dato erroneo.", None, False),
   ("es_registro_completo", BOOL, "none", "Verdadero si el formato se diligencio completo.", None, False),
   ("turno_imputado", BOOL, "none", "Verdadero si el turno se imputo porque la fuente no lo traia.", None, False),
   ("operario_no_informado", BOOL, "none", "Verdadero si la fuente no registro el operario.", None, False),
   ("referencia_no_informada", BOOL, "none", "Verdadero si la fuente no registro la referencia.", None, False)]),

 ("Eventos de paro", "dw.hecho_paro",
  "TABLA DE HECHOS. Grano declarado: un registro por evento de paro de un "
  "codigo concreto en un turno de una maquina. 16.482 filas, resultado de "
  "despivotar los 18 pares de columnas del Excel.",
  [("fecha_key", ENTERO, "none", "Llave a Fecha.", "0", True),
   ("maquina_key", ENTERO, "none", "Llave a Maquina.", "0", True),
   ("turno_key", ENTERO, "none", "Llave a Turno.", "0", True),
   ("referencia_key", ENTERO, "none", "Llave a Referencia.", "0", True),
   ("paro_key", ENTERO, "none", "Llave a Paro.", "0", True),
   ("minutos_paro", DECIMAL, "sum", "Duracion del paro en minutos, tal como la registra la fuente.", "0.0", True),
   ("horas_paro", DECIMAL, "sum", "Duracion del paro en horas.", "0.000", True),
   ("unidades_no_producidas", ENTERO, "sum", "Unidades que se dejaron de producir por este paro.", "0", True),
   ("es_paro_planeado", BOOL, "none", "Verdadero si el paro es planeado.", None, False),
   ("subcodigo_imputado", BOOL, "none", "Verdadero si la causa raiz no venia especificada en la fuente.", None, False),
   ("observacion_paro", TEXTO, "none", "Observacion libre que escribio mantenimiento.", None, False)]),
]

# ===========================================================================
#  Medidas DAX
#  (tabla, nombre, expresion, formato, carpeta, descripcion)
# ===========================================================================
PT = "Produccion por turno"
EP = "Eventos de paro"

MEDIDAS = [
 # --- Bloque de tiempo -----------------------------------------------------
 (PT, "Horas programadas", "SUM('Produccion por turno'[horas_programadas])",
  "#,0.0", "01 Tiempo",
  "Horas que la planta programo para producir. Es el denominador de la Disponibilidad."),
 (PT, "Horas operativas", "SUM('Produccion por turno'[horas_operativas])",
  "#,0.0", "01 Tiempo",
  "Horas en que la linea estuvo efectivamente produciendo."),
 (PT, "Horas de paro", "SUM('Produccion por turno'[horas_paro_total])",
  "#,0.0", "01 Tiempo",
  "Tiempo total perdido por paros."),
 (PT, "Horas de paro no planeado",
  "SUM('Produccion por turno'[horas_paro_no_planeado])",
  "#,0.0", "01 Tiempo",
  "Tiempo perdido EVITABLE. Es la cifra sobre la que se puede actuar."),
 (PT, "% de paro evitable",
  "DIVIDE([Horas de paro no planeado], [Horas de paro])",
  "0.0%", "01 Tiempo",
  "Que proporcion del tiempo perdido era evitable."),

 # --- Bloque OEE -----------------------------------------------------------
 (PT, "Disponibilidad", "DIVIDE([Horas operativas], [Horas programadas])",
  "0.0%", "02 OEE",
  "Primer componente del OEE. REPRODUCE EXACTAMENTE el '% Productividad' que "
  "el Excel calcula hoy: se verifico a seis decimales contra las tablas "
  "dinamicas de la fuente."),
 (PT, "Horas programadas (OEE)",
  "CALCULATE(\n"
  "    SUM('Produccion por turno'[horas_programadas]),\n"
  "    'Produccion por turno'[tiene_estandar] = TRUE(),\n"
  "    'Produccion por turno'[rendimiento_implausible] = FALSE()\n"
  ")",
  "#,0.0", "02 OEE",
  "Denominador del factor de Disponibilidad DENTRO del OEE. Se restringe al "
  "mismo subconjunto de turnos que el Rendimiento para que el producto de los "
  "dos factores sea coherente: ambos miden la misma poblacion de turnos."),
 (PT, "Horas operativas (OEE)",
  "CALCULATE(\n"
  "    SUM('Produccion por turno'[horas_operativas]),\n"
  "    'Produccion por turno'[tiene_estandar] = TRUE(),\n"
  "    'Produccion por turno'[rendimiento_implausible] = FALSE()\n"
  ")",
  "#,0.0", "02 OEE",
  "Numerador del factor de Disponibilidad dentro del OEE, sobre los mismos "
  "turnos auditables que el Rendimiento."),
 (PT, "Disponibilidad (OEE)",
  "DIVIDE([Horas operativas (OEE)], [Horas programadas (OEE)])",
  "0.0%", "02 OEE",
  "Factor de Disponibilidad que entra en el OEE. NO es el mismo que la medida "
  "'Disponibilidad': esa se calcula sobre TODOS los turnos porque solo "
  "necesita horas, y es la que reproduce el '% Productividad' del Excel. Esta "
  "se limita a los turnos con estandar para no multiplicar dos factores "
  "medidos sobre poblaciones distintas."),
 (PT, "Cobertura del OEE",
  "DIVIDE(\n"
  "    CALCULATE(\n"
  "        [Turnos registrados],\n"
  "        'Produccion por turno'[tiene_estandar] = TRUE(),\n"
  "        'Produccion por turno'[rendimiento_implausible] = FALSE()\n"
  "    ),\n"
  "    [Turnos registrados]\n"
  ")",
  "0.0%", "02 OEE",
  "Que porcentaje de los turnos del periodo entra en el calculo del OEE. Hay "
  "que declararla junto al OEE: en 2023 solo el 24 % de los turnos tiene "
  "estandar de ingenieria, asi que el OEE de ese ano describe una cuarta parte "
  "de la operacion."),
 (PT, "Unidades producidas",
  "CALCULATE(\n"
  "    SUM('Produccion por turno'[unidades_producidas]),\n"
  "    'Produccion por turno'[tiene_estandar] = TRUE(),\n"
  "    'Produccion por turno'[rendimiento_implausible] = FALSE()\n"
  ")",
  "#,0", "02 OEE",
  "Unidades producidas, contando solo los turnos con estandar de ingenieria y "
  "excluyendo los 22 turnos con rendimiento implausible. El filtro es "
  "deliberado: sin estandar no hay con que comparar, y un dato erroneo inflaria "
  "el indicador."),
 (PT, "Unidades posibles",
  "CALCULATE(\n"
  "    SUM('Produccion por turno'[unidades_posibles]),\n"
  "    'Produccion por turno'[tiene_estandar] = TRUE(),\n"
  "    'Produccion por turno'[rendimiento_implausible] = FALSE()\n"
  ")",
  "#,0", "02 OEE",
  "Unidades que el estandar de ingenieria permitiria producir en el tiempo que "
  "la linea estuvo operando."),
 (PT, "Rendimiento", "DIVIDE([Unidades producidas], [Unidades posibles])",
  "0.0%", "02 OEE",
  "Segundo componente del OEE. El Excel NO lo calcula: es uno de los "
  "indicadores nuevos que habilita este modelo."),
 (PT, "Calidad (proxy)",
  "VAR Reproceso =\n"
  "    CALCULATE(\n"
  "        SUM('Eventos de paro'[unidades_no_producidas]),\n"
  "        'Paro'[codigo_paro] = \"11\"\n"
  "    )\n"
  "VAR Producidas = [Unidades producidas]\n"
  "RETURN\n"
  "    IF(\n"
  "        Producidas > 0,\n"
  "        1 - DIVIDE(Reproceso, Producidas)\n"
  "    )",
  "0.0%", "02 OEE",
  "Tercer componente del OEE, como PROXY declarado. La fuente no registra "
  "unidades defectuosas, asi que la perdida de calidad se estima con el tiempo "
  "de reproceso (codigo 11). Es una COTA INFERIOR de la perdida real: el OEE "
  "verdadero no puede ser mayor que este."),
 (PT, "OEE", "[Disponibilidad (OEE)] * [Rendimiento]",
  "0.0%", "02 OEE",
  "OEE auditable: Disponibilidad por Rendimiento, ambos medidos sobre los "
  "MISMOS turnos (los que tienen estandar y rendimiento plausible). Se agrega "
  "como razon de sumas, no como promedio de los OEE por turno, para que valga "
  "en cualquier nivel de la jerarquia. Declarar siempre la 'Cobertura del "
  "OEE' al lado."),
 (PT, "OEE completo",
  "[Disponibilidad (OEE)] * [Rendimiento] * [Calidad (proxy)]",
  "0.0%", "02 OEE",
  "OEE con los tres componentes, usando el proxy de Calidad. Se presenta junto "
  "al OEE auditable para dejar claro cuanto pesa la parte estimada."),
 (PT, "Meta de OEE", "0.65",
  "0.0%", "02 OEE",
  "Meta del 65%. No es arbitraria: es el nivel que Vinilos_3 y Vinilos_4 ya "
  "sostienen con los mismos equipos y el mismo producto, asi que esta "
  "demostrado que es alcanzable."),
 (PT, "Brecha vs meta", "[OEE] - [Meta de OEE]",
  "+0.0%;-0.0%;0.0%", "02 OEE",
  "Puntos porcentuales por encima o por debajo de la meta."),

 # --- Bloque inteligencia de tiempo ---------------------------------------
 (PT, "OEE del ano anterior",
  "CALCULATE(\n"
  "    [OEE],\n"
  "    SAMEPERIODLASTYEAR('Fecha'[fecha])\n"
  ")",
  "0.0%", "03 Inteligencia de tiempo",
  "MEDIDA DE INTELIGENCIA DE TIEMPO. El mismo periodo del ano anterior, usando "
  "SAMEPERIODLASTYEAR sobre la tabla de fechas marcada. Permite comparar marzo "
  "contra marzo sin que la estacionalidad distorsione la lectura."),
 (PT, "Variacion de OEE interanual",
  "VAR Actual = [OEE]\n"
  "VAR Anterior = [OEE del ano anterior]\n"
  "RETURN\n"
  "    IF(\n"
  "        NOT ISBLANK(Actual) && NOT ISBLANK(Anterior),\n"
  "        Actual - Anterior\n"
  "    )",
  "+0.0%;-0.0%;0.0%", "03 Inteligencia de tiempo",
  "Cuantos puntos porcentuales gano o perdio la linea frente al mismo periodo "
  "del ano pasado. Devuelve vacio si falta alguno de los dos periodos, para no "
  "mostrar una caida del 100% donde en realidad no hay dato comparable."),
 (PT, "OEE acumulado del ano",
  "TOTALYTD([OEE], 'Fecha'[fecha])",
  "0.0%", "03 Inteligencia de tiempo",
  "OEE acumulado del ano hasta la fecha, con TOTALYTD. Es la cifra que se "
  "presenta en el comite: suaviza el mes malo aislado."),
 (PT, "Horas de paro del ano anterior",
  "CALCULATE(\n"
  "    [Horas de paro],\n"
  "    SAMEPERIODLASTYEAR('Fecha'[fecha])\n"
  ")",
  "#,0.0", "03 Inteligencia de tiempo",
  "Tiempo perdido en el mismo periodo del ano anterior."),
 (PT, "Disponibilidad movil 3 meses",
  "VAR Ultimo = MAX('Fecha'[fecha])\n"
  "RETURN\n"
  "    CALCULATE(\n"
  "        [Disponibilidad],\n"
  "        DATESINPERIOD('Fecha'[fecha], Ultimo, -3, MONTH)\n"
  "    )",
  "0.0%", "03 Inteligencia de tiempo",
  "Promedio movil de tres meses con DATESINPERIOD. Aisla la tendencia del "
  "ruido de un mes suelto."),

 # --- Bloque paros y Pareto ------------------------------------------------
 (EP, "Horas perdidas", "SUM('Eventos de paro'[horas_paro])",
  "#,0.0", "04 Paros",
  "Tiempo perdido medido sobre la tabla de eventos de paro, que es la que "
  "permite abrir la causa hasta el cuarto nivel de la jerarquia."),
 (EP, "Numero de eventos", "COUNTROWS('Eventos de paro')",
  "#,0", "04 Paros",
  "Numero de eventos de paro registrados."),
 (EP, "Duracion media del paro",
  "DIVIDE([Horas perdidas], [Numero de eventos])",
  "0.00", "04 Paros",
  "Horas por evento. Junto con el numero de eventos distingue el problema "
  "cronico (muchos paros cortos) del problema grave (pocos pero largos)."),
 (EP, "Unidades no producidas",
  "SUM('Eventos de paro'[unidades_no_producidas])",
  "#,0", "04 Paros",
  "Traduce el tiempo perdido al lenguaje del negocio: cuantas unidades se "
  "dejaron de envasar."),
 (EP, "Horas perdidas acumuladas",
  "VAR HorasDeLaCausa = [Horas perdidas]\n"
  "VAR TodasLasCausas =\n"
  "    ADDCOLUMNS(\n"
  "        ALLSELECTED('Paro'[etiqueta_codigo_paro]),\n"
  "        \"@horas\", [Horas perdidas]\n"
  "    )\n"
  "VAR Acumulado =\n"
  "    SUMX(\n"
  "        FILTER(TodasLasCausas, [@horas] >= HorasDeLaCausa),\n"
  "        [@horas]\n"
  "    )\n"
  "RETURN\n"
  "    IF(NOT ISBLANK(HorasDeLaCausa), Acumulado)",
  "#,0.0", "05 Pareto",
  "Suma acumulada de horas perdidas recorriendo las causas de mayor a menor. "
  "Es la mitad de la curva de Pareto."),
 (EP, "% acumulado de tiempo perdido",
  "DIVIDE(\n"
  "    [Horas perdidas acumuladas],\n"
  "    CALCULATE([Horas perdidas], ALLSELECTED('Paro'))\n"
  ")",
  "0.0%", "05 Pareto",
  "Porcentaje acumulado del tiempo perdido. Es la LINEA del grafico de Pareto: "
  "donde cruza el 80% estan las pocas causas que explican casi todo el "
  "problema."),
 (EP, "Meta Pareto 80%", "0.8",
  "0\\ %;-0\\ %;0\\ %", "05 Pareto",
  "Segunda linea del grafico de Pareto, fija en el 80 %. Va como medida y no "
  "como linea constante de Power BI porque la linea constante se ancla al eje "
  "de las columnas (horas) y quedaba pegada al piso, no al eje del porcentaje "
  "acumulado."),
 (EP, "Clasificacion Pareto",
  "IF(\n"
  "    [% acumulado de tiempo perdido] <= 0.8,\n"
  "    \"Causa vital\",\n"
  "    \"Causa trivial\"\n"
  ")",
  None, "05 Pareto",
  "Marca si la causa pertenece al 80% que concentra el tiempo perdido. Sirve "
  "para colorear el grafico y para filtrar el plan de mantenimiento."),

 # --- Bloque confiabilidad y gobierno del dato -----------------------------
 (EP, "MTTR",
  "VAR Fallas =\n"
  "    CALCULATE(\n"
  "        [Numero de eventos],\n"
  "        'Paro'[codigo_paro] IN {\"01\", \"02\"}\n"
  "    )\n"
  "VAR HorasReparacion =\n"
  "    CALCULATE(\n"
  "        [Horas perdidas],\n"
  "        'Paro'[codigo_paro] IN {\"01\", \"02\"}\n"
  "    )\n"
  "RETURN\n"
  "    DIVIDE(HorasReparacion, Fallas)",
  "0.00", "06 Confiabilidad",
  "Tiempo medio de reparacion, en horas. Solo cuenta falla electromecanica "
  "(01) y espera de soporte (02), que son las averias reales."),
 (PT, "MTBF",
  "VAR Fallas =\n"
  "    CALCULATE(\n"
  "        COUNTROWS('Eventos de paro'),\n"
  "        'Paro'[codigo_paro] IN {\"01\", \"02\"}\n"
  "    )\n"
  "RETURN\n"
  "    DIVIDE([Horas operativas], Fallas)",
  "#,0.0", "06 Confiabilidad",
  "Tiempo medio entre fallas, en horas operativas. Sube cuando la "
  "confiabilidad mejora."),
 (PT, "Turnos registrados", "COUNTROWS('Produccion por turno')",
  "#,0", "07 Gobierno del dato",
  "Numero de turnos cargados."),
 (PT, "Indice de completitud del registro",
  "VAR Turnos = [Turnos registrados]\n"
  "VAR ConOperario =\n"
  "    CALCULATE([Turnos registrados],\n"
  "        'Produccion por turno'[operario_no_informado] = FALSE())\n"
  "VAR ConReferencia =\n"
  "    CALCULATE([Turnos registrados],\n"
  "        'Produccion por turno'[referencia_no_informada] = FALSE())\n"
  "VAR ConTurno =\n"
  "    CALCULATE([Turnos registrados],\n"
  "        'Produccion por turno'[turno_imputado] = FALSE())\n"
  "VAR ConEstandar =\n"
  "    CALCULATE([Turnos registrados],\n"
  "        'Produccion por turno'[tiene_estandar] = TRUE())\n"
  "RETURN\n"
  # El "+ 0" obliga a que 2022 muestre 0,0 % en vez de quedar vacio: ese anio
  # ningun turno trae estandar, y el hueco se confundia con "sin datos" cuando
  # lo correcto es "completitud nula".
  "    DIVIDE(ConOperario + ConReferencia + ConTurno + ConEstandar + 0, Turnos * 4)",
  "0.0%", "07 Gobierno del dato",
  "INDICADOR NUEVO. Mide que tan completo llega el formato hora a hora. Pasa "
  "de 0% en 2022 a 100% en 2025, y explica por que el Rendimiento no es "
  "calculable antes de 2023. Sin este indicador, cualquier conclusion del "
  "tablero es fragil."),
 (PT, "Turnos sin estandar",
  "CALCULATE([Turnos registrados],\n"
  "    'Produccion por turno'[tiene_estandar] = FALSE())",
  "#,0", "07 Gobierno del dato",
  "Turnos para los que no existe estandar de ingenieria, asi que no entran al "
  "calculo del Rendimiento."),
]

# ===========================================================================
#  Relaciones:  (tabla_origen, col_origen, tabla_destino, col_destino, nota)
#  Siempre de la dimension (lado uno) al hecho (lado muchos).
# ===========================================================================
RELACIONES = [
 ("Fecha", "fecha_key", PT, "fecha_key"),
 ("Maquina", "maquina_key", PT, "maquina_key"),
 ("Turno", "turno_key", PT, "turno_key"),
 ("Operario", "operario_key", PT, "operario_key"),
 ("Referencia", "referencia_key", PT, "referencia_key"),
 ("Fecha", "fecha_key", EP, "fecha_key"),
 ("Maquina", "maquina_key", EP, "maquina_key"),
 ("Turno", "turno_key", EP, "turno_key"),
 ("Referencia", "referencia_key", EP, "referencia_key"),
 ("Paro", "paro_key", EP, "paro_key"),
]

# ===========================================================================
#  Generacion de archivos
# ===========================================================================
for d in [SM / "definition" / "tables", RP]:
    d.mkdir(parents=True, exist_ok=True)

def platform(tipo, nombre):
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": tipo, "displayName": nombre},
        "config": {"version": "2.0", "logicalId": lt(tipo, nombre)},
    }, indent=2, ensure_ascii=False) + "\n"

(SM / ".platform").write_text(platform("SemanticModel", NOMBRE))
(RP / ".platform").write_text(platform("Report", NOMBRE))

(RAIZ / f"{NOMBRE}.pbip").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",  # Microsoft movio esta ruta: con item/pbip/definitionProperties,
    # Power BI Desktop rechaza el .pbip al abrirlo.
    "version": "1.0",
    "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
    "settings": {"enableAutoRecovery": True},
}, indent=2, ensure_ascii=False) + "\n")

(SM / "definition.pbism").write_text(json.dumps(
    {"version": "4.2", "settings": {}}, indent=2) + "\n")

(RP / "definition.pbir").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
    "version": "1.0",
    "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}},
}, indent=2, ensure_ascii=False) + "\n")

# --- database.tmdl ---------------------------------------------------------
(SM / "definition" / "database.tmdl").write_text(
    "database\n" + T + "compatibilityLevel: 1567\n\n")

# --- expressions.tmdl: el origen de datos en UN solo lugar ----------------
m_origen = "\n".join([
 T + T + "let",
 T + T + '    // Cambiar aqui el servidor si la base de datos corre en otra maquina.',
 T + T + '    // Power BI se ejecuta en Windows y PostgreSQL en el contenedor del Mac,',
 T + T + '    // asi que NO sirve "localhost": hay que usar la IP del anfitrion.',
 T + T + f'    Servidor = "{HOST}",',
 T + T + f'    BaseDeDatos = "{BD}",',
 T + T + "    Origen = PostgreSQL.Database(Servidor, BaseDeDatos)",
 T + T + "in",
 T + T + "    Origen",
])
(SM / "definition" / "expressions.tmdl").write_text("\n".join([
 "/// Conexion unica a la base de datos del almacen. Todas las tablas del",
 "/// modelo se alimentan de aqui, de modo que cambiar de servidor es cambiar",
 "/// una sola linea. La contrasena NO se guarda en el proyecto: Power BI la",
 "/// pide al abrir y la almacena en el administrador de credenciales de",
 "/// Windows, por lo que el repositorio queda sin credenciales.",
 "expression 'Origen BI-OEE' =",
 m_origen,
 T + f"lineageTag: {lt('expr', 'origen')}",
 "",
 T + "annotation PBI_ResultType = Table",
 "",
]))

# --- tablas ----------------------------------------------------------------
refs_tabla = []
for nombre, objeto, descripcion, columnas in TABLAS:
    esquema, obj = objeto.split(".")
    archivo = nombre.replace(" ", " ")
    refs_tabla.append(nombre)
    L = []
    for linea in descripcion.split(". "):
        pass
    # descripcion de la tabla como comentario de documentacion
    import textwrap
    for linea in textwrap.wrap(descripcion, 74):
        L.append("/// " + linea)
    L.append(f"table '{nombre}'" if " " in nombre else f"table {nombre}")
    if nombre == "Fecha":
        # "Marcar como tabla de fechas" en la interfaz equivale a estas dos
        # cosas en el modelo tabular: dataCategory Time en la tabla e isKey
        # en la columna de fecha. Sin esto, las funciones de inteligencia de
        # tiempo pueden comportarse de forma inconsistente al cruzar las dos
        # tablas de hechos.
        L.append(T + "dataCategory: Time")
    L.append(T + f"lineageTag: {lt('table', nombre)}")
    L.append("")

    for cn, ct, cs, cd, cf, oculta in columnas:
        for linea in textwrap.wrap(cd, 70):
            L.append(T + "/// " + linea)
        L.append(T + f"column {cn}")
        L.append(T + T + f"dataType: {ct}")
        if oculta:
            L.append(T + T + "isHidden")
        if cf:
            L.append(T + T + f"formatString: {cf}")
        L.append(T + T + f"lineageTag: {lt('col', nombre, cn)}")
        L.append(T + T + f"summarizeBy: {cs}")
        L.append(T + T + f"sourceColumn: {cn}")
        if nombre == "Fecha" and cn == "fecha":
            L.append(T + T + "isKey")
        L.append("")
        L.append(T + T + "annotation SummarizationSetBy = Automatic")
        if ct == FECHA:
            L.append(T + T + "annotation UnderlyingDateTimeDataType = Date")
        L.append("")

    # medidas de esta tabla
    for mt, mn, mexp, mfmt, mcarp, mdesc in MEDIDAS:
        if mt != nombre:
            continue
        for linea in textwrap.wrap(mdesc, 70):
            L.append(T + "/// " + linea)
        L.append(T + f"measure '{mn}' =")
        for linea in mexp.split("\n"):
            L.append(T + T + T + linea)
        if mfmt:
            L.append(T + T + f"formatString: {mfmt}")
        L.append(T + T + f"lineageTag: {lt('measure', mn)}")
        L.append(T + T + f"displayFolder: {mcarp}")
        L.append("")

    # jerarquias
    if nombre == "Paro":
        L.append(T + "/// Jerarquia de paros de cuatro niveles, sobre la que se hace el")
        L.append(T + "/// drill-down del tablero. Es DESBALANCEADA a proposito: solo los")
        L.append(T + "/// codigos 01, 03 y 05 tienen subcodigos de causa raiz. En lugar de")
        L.append(T + "/// dejar NULL en los otros 15, la dimension trae miembros de relleno")
        L.append(T + "/// explicitos ('N/A', 'SIN-ESP'), de modo que el drill-down nunca")
        L.append(T + "/// aterriza en un hueco y el usuario entiende por que se detiene.")
        L.append(T + "hierarchy 'Jerarquia de paros'")
        L.append(T + T + f"lineageTag: {lt('hier', 'paros')}")
        L.append("")
        for niv, col in [("Area responsable", "area_impacto"),
                         ("Codigo de paro", "etiqueta_codigo_paro"),
                         ("Sistema de la maquina", "nombre_sistema"),
                         ("Causa raiz", "nombre_subcodigo")]:
            L.append(T + T + f"level '{niv}'")
            L.append(T + T + T + f"lineageTag: {lt('lvl', niv)}")
            L.append(T + T + T + f"column: {col}")
            L.append("")
    if nombre == "Fecha":
        L.append(T + "/// Jerarquia de calendario para navegar de ano a dia.")
        L.append(T + "hierarchy 'Calendario'")
        L.append(T + T + f"lineageTag: {lt('hier', 'calendario')}")
        L.append("")
        for niv, col in [("Ano", "anio"), ("Trimestre", "nombre_trimestre"),
                         ("Mes", "nombre_mes"), ("Dia", "dia")]:
            L.append(T + T + f"level '{niv}'")
            L.append(T + T + T + f"lineageTag: {lt('lvlf', niv)}")
            L.append(T + T + T + f"column: {col}")
            L.append("")

    # particion
    cols_sel = ", ".join(f'"{c[0]}"' for c in columnas)
    L.append(T + f"partition '{nombre}' = m")
    L.append(T + T + "mode: import")
    L.append(T + T + "source =")
    L.append(T + T + T + "let")
    L.append(T + T + T + f'    Tabla = #"Origen BI-OEE"{{[Schema="{esquema}",Item="{obj}"]}}[Data],')
    L.append(T + T + T + f"    Columnas = Table.SelectColumns(Tabla, {{{cols_sel}}})")
    L.append(T + T + T + "in")
    L.append(T + T + T + "    Columnas")
    L.append("")
    nombre_archivo = nombre + ".tmdl"
    (SM / "definition" / "tables" / nombre_archivo).write_text("\n".join(L) + "\n")

# --- relationships.tmdl ----------------------------------------------------
# SIN cabecera de comentario. Power BI rechaza el archivo si la primera
# linea no es una declaracion de objeto: ni /// (que es una DESCRIPCION y
# debe ir pegada a un objeto, no suelta) ni // valen aqui. La explicacion
# del modelo en constelacion -por que los dos hechos NO se relacionan entre
# si, sino solo a traves de las dimensiones conformadas- vive en
# docs/04-modelo-dimensional.md, que es donde se lee.
L = []
for do, co, dd, cd in RELACIONES:
    rid = lt("rel", do, co, dd, cd)
    L.append(f"relationship {rid}")
    L.append(T + f"fromColumn: '{dd}'.{cd}" if " " in dd else T + f"fromColumn: {dd}.{cd}")
    L.append(T + f"toColumn: '{do}'.{co}" if " " in do else T + f"toColumn: {do}.{co}")
    L.append("")
(SM / "definition" / "relationships.tmdl").write_text("\n".join(L) + "\n")

# --- model.tmdl ------------------------------------------------------------
L = ["model Model",
     T + "culture: es-CO",
     T + "defaultPowerBIDataSourceVersion: powerBI_V3",
     T + "sourceQueryCulture: es-CO",
     T + "dataAccessOptions",
     T + T + "legacyRedirects",
     T + T + "returnErrorValuesAsNull",
     "",
     T + "annotation PBI_QueryOrder = " + json.dumps(
         ["Origen BI-OEE"] + [t[0] for t in TABLAS], ensure_ascii=False),
     "",
     T + "annotation PBI_ProTooling = [\"TMDL\"]",
     ""]
for t in TABLAS:
    n = t[0]
    L.append(f"ref table '{n}'" if " " in n else f"ref table {n}")
L.append("")
L.append("ref expression 'Origen BI-OEE'")
L.append("")
(SM / "definition" / "model.tmdl").write_text("\n".join(L) + "\n")

# --- report.json minimo valido --------------------------------------------
paginas = [("Resumen gerencial", "p1"), ("Pareto de causas", "p2"),
           ("Drill-down de paros", "p3"), ("Calidad del dato", "p4")]
(RP / "report.json").write_text(json.dumps({
    "config": json.dumps({
        "version": "5.55",
        "themeCollection": {"baseTheme": {"name": "CY24SU10"}},
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "settings": {"useStylableVisualContainerHeader": True,
                     "allowChangeFilterTypes": True},
    }),
    "layoutOptimization": 0,
    "resourcePackages": [{"resourcePackage": {
        "disabled": False, "items": [
            {"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": 202}],
        "name": "SharedResources", "type": 2}}],
    "sections": [{
        "config": "{}",
        "displayName": nombre,
        "displayOption": 1,
        "height": 720.0,
        "width": 1280.0,
        "name": lt("page", clave),
        "ordinal": i,
        "visualContainers": [],
    } for i, (nombre, clave) in enumerate(paginas)],
}, indent=2, ensure_ascii=False) + "\n")

n_med = len(MEDIDAS)
n_col = sum(len(t[3]) for t in TABLAS)
print(f"PBIP generado: {len(TABLAS)} tablas, {n_col} columnas, {n_med} medidas DAX, "
      f"{len(RELACIONES)} relaciones, 2 jerarquias, {len(paginas)} paginas")
