"""REGLAS DE NEGOCIO del ETL: normalizacion de valores y mapeo de taxonomias.

Este modulo concentra todas las decisiones de limpieza para que sean
auditables en un solo lugar y queden versionadas en Git. Cada diccionario de
mapeo documenta el problema de calidad que resuelve.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

# ===========================================================================
#  UTILIDADES DE NORMALIZACION DE TEXTO
# ===========================================================================

_ESPACIOS = re.compile(r"\s+")


def limpiar(valor) -> str | None:
    """Normaliza un valor de texto de la fuente.

    Colapsa espacios repetidos, recorta extremos y convierte en None los
    marcadores de vacio que usa el Excel (' ', '', 'None').
    """
    if valor is None:
        return None
    texto = _ESPACIOS.sub(" ", str(valor)).strip()
    if texto == "" or texto.lower() in {"none", "nan", "-"}:
        return None
    return texto


def sin_tildes(texto: str) -> str:
    """Quita diacriticos para poder comparar claves de forma robusta."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def clave_comparacion(texto: str | None) -> str:
    """Clave canonica para comparar dos cadenas de la fuente.

    Mayusculas, sin tildes, sin signos de puntuacion ni espacios. Es lo que
    permite reconocer que 'Klips 15cc (12col)' y 'Klips 15cc (12 col)' son la
    misma referencia.
    """
    if texto is None:
        return ""
    base = sin_tildes(texto).upper()
    return re.sub(r"[^A-Z0-9]", "", base)


def pseudonimo(nombre: str, salt: str) -> str:
    """HMAC-SHA256 del nombre con una semilla secreta.

    Se usa HMAC y no un SHA plano porque el universo de nombres de pila es
    pequeno: un hash sin clave seria reversible por fuerza bruta en segundos.
    """
    return hmac.new(salt.encode("utf-8"), nombre.encode("utf-8"), hashlib.sha256).hexdigest()


# ===========================================================================
#  MAQUINAS
#  factor_produccion recuperado de la formula de texto de la hoja "Tiempos":
#     SI(maquina="Vinilos_1";1,1; SI(maquina="Vinilos_2";1,16; ... 1))
# ===========================================================================
MAQUINAS = [
    # (key, codigo, nombre, linea, factor, grupo_capacidad)
    (1, "Vinilos_1", "Linea Vinilos 1", 1, 1.100, "Alta"),
    (2, "Vinilos_2", "Linea Vinilos 2", 2, 1.160, "Alta"),
    (3, "Vinilos_3", "Linea Vinilos 3", 3, 1.000, "Estandar"),
    (4, "Vinilos_4", "Linea Vinilos 4", 4, 1.000, "Estandar"),
]

# ===========================================================================
#  TURNOS
#  PROBLEMA DE CALIDAD: la fuente usa 7 etiquetas distintas para 6 turnos,
#  unas con sufijo "(Turno N)" y otras sin el. Ademas 3.912 de 8.208 filas no
#  traen turno, y en 687 de ellas el valor quedo en la columna equivocada
#  ("Unidad por display"), por un desalineamiento del formulario de captura.
#  REGLA: se unifica por el rango horario, que es el dato estable.
# ===========================================================================
TURNOS = [
    # (key, codigo, nombre, etiqueta_canonica, inicio, fin, duracion,
    #  tipo_jornada, nocturno, orden, valido)
    (1, "T1",  "Turno 1 (06:00-14:00)",  "6am-2pm (Turno 1)",   "06:00", "14:00",  8.0, "Ordinario",  False, 1, True),
    (2, "T2",  "Turno 2 (14:00-22:00)",  "2pm-10pm (Turno 2)",  "14:00", "22:00",  8.0, "Ordinario",  False, 2, True),
    (3, "T3",  "Turno 3 (22:00-06:00)",  "10pm-6am (Turno 3)",  "22:00", "06:00",  8.0, "Ordinario",  True,  3, True),
    (4, "TE1", "Extendido (06:00-16:30)", "6am-4:30pm",         "06:00", "16:30", 10.5, "Extendido",  False, 4, True),
    (5, "TE2", "Extendido (06:00-18:00)", "6am-6pm",            "06:00", "18:00", 12.0, "Extendido",  False, 5, True),
    (6, "TE3", "Extendido (18:00-06:00)", "6pm-6am",            "18:00", "06:00", 12.0, "Extendido",  True,  6, True),
    (7, "NA",  "No aplica",               "No aplica",          None,    None,    None, "No aplica",  False, 7, False),
    (8, "DESC","Sin informar",            "Sin informar",       None,    None,    None, "No aplica",  False, 8, False),
]

# Mapeo de cada variante encontrada en la fuente a su clave de turno.
_TURNO_VARIANTES = {
    "6AM2PMTURNO1": 1, "6AM2PM": 1,
    "2PM10PMTURNO2": 2, "2PM10PM": 2,
    "10PM6AMTURNO3": 3, "10PM6AM": 3,
    "6AM430PM": 4,
    "6AM6PM": 5,
    "6PM6AM": 6,
    "NOAPLICA": 7,
}


def resolver_turno(valor: str | None) -> tuple[int, bool]:
    """Devuelve (turno_key, fue_imputado).

    fue_imputado=True significa que la fuente no traia un turno reconocible y
    se asigno el miembro tecnico 'Sin informar'. Esa bandera viaja al hecho
    para que el tablero pueda excluir esos registros.
    """
    clave = clave_comparacion(valor)
    if clave in _TURNO_VARIANTES:
        return _TURNO_VARIANTES[clave], False
    return 8, True


# ===========================================================================
#  REFERENCIAS DE PRODUCTO
#  PROBLEMA DE CALIDAD: 52 valores distintos en los hechos para ~49 productos
#  reales. Erratas tipograficas y de espaciado detectadas:
# ===========================================================================
CORRECCION_REFERENCIA = {
    # errata en la fuente            ->  valor canonico del catalogo
    "ALOCDOR22CC6COL":   "Alocolor 22cc (6 col)",    # 'Alocdor' por 'Alocolor'
    "STILOKIDS22CC6COL": "Estilo Kids 22cc (6 col)", # falta la E inicial
    "KLIPS15CC12COL":    "Klips 15cc (12 col)",      # faltaba el espacio en '(12col)'
}

# Patron de los nombres de referencia:  '<Linea> <volumen>cc (<n> col)'
_PATRON_REFERENCIA = re.compile(
    r"^(?P<linea>.+?)\s+(?P<vol>\d+(?:[.,]\d+)?)\s*cc\s*\((?P<col>\d+)\s*col\)\s*$",
    re.IGNORECASE,
)
# Variantes sin parentesis de colores: 'Parchesitos 125 cc'
_PATRON_REFERENCIA_SIMPLE = re.compile(
    r"^(?P<linea>.+?)\s+(?P<vol>\d+(?:[.,]\d+)?)\s*cc\s*$", re.IGNORECASE
)


def analizar_referencia(nombre: str) -> dict:
    """Descompone el nombre de la referencia en atributos dimensionales.

    La fuente guarda una sola cadena de texto; de ella se derivan la linea
    comercial, el volumen de la presentacion y el numero de colores, que son
    las jerarquias que necesita el tablero gerencial.
    """
    resultado = {
        "linea_comercial": nombre,
        "volumen_cc": None,
        "numero_colores": None,
        "etiqueta_presentacion": None,
    }
    for patron in (_PATRON_REFERENCIA, _PATRON_REFERENCIA_SIMPLE):
        m = patron.match(nombre)
        if m:
            vol = float(m.group("vol").replace(",", "."))
            resultado["linea_comercial"] = m.group("linea").strip()
            resultado["volumen_cc"] = vol
            resultado["etiqueta_presentacion"] = (
                f"{int(vol) if vol.is_integer() else vol} cc"
            )
            if "col" in patron.pattern:
                try:
                    resultado["numero_colores"] = int(m.group("col"))
                except IndexError:
                    pass
            return resultado
    # 'Vinilos x 30 Blanco', 'No aplica' y similares no siguen el patron.
    return resultado


# ===========================================================================
#  CODIGOS DE PARO  (nivel 1 y 2 de la jerarquia)
#  Fuente: hoja "Tablas Desplegables" (columnas AREA DE IMPACTO / PARO) y
#  listado del procedimiento P-MTO-22.
#
#  NATURALEZA DEL PARO: clasificacion propia. El Excel actual NO distingue
#  entre paro planeado y no planeado, por lo que su "% Productividad" castiga
#  por igual una falla electromecanica y la pausa activa de ley.
# ===========================================================================
CODIGOS_PARO = [
    # (codigo, nombre, area_impacto, naturaleza, imputable_mantenimiento, admite_subcodigo)
    ("01", "Falla del sistema electromecanico y/o de control",
     "Mantenimiento", "No planeado", True,  True),
    ("02", "Espera de soporte de mantenimiento",
     "Mantenimiento", "No planeado", True,  False),
    ("03", "Novedad en los sistemas de potencia (aire, energia, vapor)",
     "Mantenimiento", "No planeado", True,  True),
    ("04", "Mantenimiento preventivo",
     "Mantenimiento", "Planeado",    True,  False),
    ("05", "Ajuste operativo",
     "Produccion",    "No planeado", False, True),
    ("06", "Limpieza por derrame operativo",
     "Produccion",    "No planeado", False, False),
    ("07", "Alistamiento de maquina / cambio de referencia",
     "Produccion",    "No planeado", False, False),
    ("08", "Capacitacion / reunion",
     "Produccion",    "Planeado",    False, False),
    ("09", "Falta de operario",
     "Produccion",    "No planeado", False, False),
    ("10", "Paro por ventaja / evacuacion",
     "Produccion",    "No planeado", False, False),
    ("11", "Reproceso",
     "Produccion",    "No planeado", False, False),
    ("12", "Materia prima defectuosa o material de empaque no conforme",
     "Calidad",       "No planeado", False, False),
    ("13", "En espera por el aval del laboratorio de microbiologia",
     "Calidad",       "No planeado", False, False),
    ("14", "Falta de materia prima",
     "Almacen de materias primas", "No planeado", False, False),
    ("15", "Cambio de insumos (roscadores, O-ring, etiquetas)",
     "Paro programado", "Planeado",  False, False),
    ("16", "Alimentacion y aseo de la zona de trabajo y la maquina",
     "Paro programado", "Planeado",  False, False),
    ("17", "Pausa activa",
     "Paro programado", "Planeado",  False, False),
    ("18", "Paro de maquina por ventas",
     "Ventas",        "Planeado",    False, False),
]

# ===========================================================================
#  SISTEMAS DE LA MAQUINA  (nivel 3 de la jerarquia)
#
#  ATRIBUTO CONFORMADO CONSTRUIDO POR EL EQUIPO. La fuente mantiene dos arboles
#  paralelos y desconectados: las ramas "1.x" (fallas, codigo 01), "3.x"
#  (servicios industriales, codigo 03) y "5.x" (ajustes operativos, codigo 05).
#  Al asignar a cada subcodigo el SISTEMA FISICO al que pertenece, los tres
#  arboles quedan comparables y se puede responder: "cual sistema de la linea
#  pierde mas tiempo, sin importar si la causa fue una falla o un ajuste".
# ===========================================================================
SISTEMAS = [
    ("SYS-ALIM-ENV",  "Sistema alimentador de envases"),
    ("SYS-DOSIF",     "Sistema de dosificacion de pintura"),
    ("SYS-BANDA-ENT", "Banda transportadora de entrada"),
    ("SYS-BANDA-SAL", "Banda transportadora de salida"),
    ("SYS-TAPADO",    "Sistema de tapado (transfer y pisador)"),
    ("SYS-ALIM-TAPA", "Sistema alimentador de tapa y tobogan"),
    ("SYS-VIDEOJET",  "Sistema Video Jet (codificado)"),
    ("SYS-SUJECION",  "Sistema de sujecion y roscadores"),
    ("SYS-ETIQ",      "Sistema etiquetadora"),
    ("SYS-ENERGIA",   "Suministro de energia electrica"),
    ("SYS-AIRE",      "Red de aire comprimido"),
    ("SYS-FRIO",      "Red de enfriamiento / chiller"),
    ("SYS-VAPOR",     "Red de vapor / caldera"),
    ("SYS-NA",        "No aplica"),
]

# Prefijo del subcodigo  ->  sistema conformado
PREFIJO_A_SISTEMA = {
    # Codigo 01: fallas electromecanicas
    "1.1": "SYS-ALIM-ENV",
    "1.2": "SYS-DOSIF",
    "1.3": "SYS-BANDA-ENT",
    "1.4": "SYS-TAPADO",
    "1.5": "SYS-ALIM-TAPA",
    "1.6": "SYS-VIDEOJET",
    "1.7": "SYS-SUJECION",
    "1.8": "SYS-ETIQ",
    # Codigo 03: servicios industriales
    "3.1": "SYS-ENERGIA",
    "3.2": "SYS-ENERGIA",
    "3.3": "SYS-AIRE",
    "3.4": "SYS-FRIO",
    "3.5": "SYS-VAPOR",
    # Codigo 05: ajustes operativos
    "5.1": "SYS-ALIM-ENV",
    "5.2": "SYS-DOSIF",
    "5.3": "SYS-BANDA-ENT",
    "5.4": "SYS-BANDA-SAL",
    "5.5": "SYS-TAPADO",
    "5.6": "SYS-ALIM-TAPA",
    "5.7": "SYS-VIDEOJET",
    "5.8": "SYS-SUJECION",
    "5.9": "SYS-ETIQ",
    "5.10": "SYS-DOSIF",   # purga de color
    "5.11": "SYS-DOSIF",   # lavado de boquilla
}

# ===========================================================================
#  SUBCODIGOS  (nivel 4 de la jerarquia)  -  catalogo vigente
# ===========================================================================
SUBCODIGOS = {
    # --- Codigo 01 ---------------------------------------------------------
    "1.1":   ("01", "Sistema alimentador de envases"),
    "1.1.A": ("01", "Banda"),
    "1.1.B": ("01", "Motor"),
    "1.1.C": ("01", "Sensor"),
    "1.2":   ("01", "Sistema de dosificacion"),
    "1.2.A": ("01", "Cambio de racores"),
    "1.2.B": ("01", "Ajuste de sensor"),
    "1.2.C": ("01", "Cambio de valvula"),
    "1.2.D": ("01", "Retenedores"),
    "1.2.E": ("01", "O-ring"),
    "1.3":   ("01", "Sistema de banda de entrada"),
    "1.3.A": ("01", "Banda"),
    "1.3.B": ("01", "Motor"),
    "1.4":   ("01", "Sistema de tapado"),
    "1.4.A": ("01", "Motor del transfer"),
    "1.4.B": ("01", "Pisador de tapa"),
    "1.4.C": ("01", "Sensor"),
    "1.5":   ("01", "Sistema de alimentacion de tapa"),
    "1.5.A": ("01", "Banda"),
    "1.5.B": ("01", "Motor"),
    "1.5.C": ("01", "Sensor"),
    "1.6":   ("01", "Sistema Video Jet"),
    "1.6.A": ("01", "Fotocelda"),
    "1.6.B": ("01", "Sensor"),
    "1.7":   ("01", "Sistema de sujecion y roscadores"),
    "1.7.A": ("01", "Banda de sujecion"),
    "1.7.B": ("01", "Roscadores"),
    "1.8":   ("01", "Sistema etiquetadora"),
    "1.8.A": ("01", "Banda"),
    "1.8.B": ("01", "Motor"),
    "1.8.C": ("01", "Sensor"),
    # --- Codigo 03 ---------------------------------------------------------
    "3.1":   ("03", "Fallo en la subestacion"),
    "3.2":   ("03", "Fallo en la red publica"),
    "3.3":   ("03", "Falla en la red neumatica o el compresor"),
    "3.4":   ("03", "Falla en la red de enfriamiento o el chiller"),
    "3.5":   ("03", "Falla en la red de vapor o la caldera"),
    # --- Codigo 05 ---------------------------------------------------------
    "5.1":   ("05", "Sistema alimentador de envases"),
    "5.2":   ("05", "Sistema de dosificacion de pintura, frontal y posterior"),
    "5.3":   ("05", "Banda transportadora de entrada"),
    "5.4":   ("05", "Banda transportadora de salida"),
    "5.5":   ("05", "Transfer y pisador de tapa"),
    "5.6":   ("05", "Sistema alimentador de tapa y tobogan"),
    "5.7":   ("05", "Video Jet"),
    "5.8":   ("05", "Banda de sujecion y roscadores"),
    "5.9":   ("05", "Sistema de etiquetado"),
    "5.10":  ("05", "Purga de color"),
    "5.11":  ("05", "Lavado de boquilla"),
}

# ---------------------------------------------------------------------------
#  MAPEO DE LA TAXONOMIA HISTORICA A LA VIGENTE
#
#  PROBLEMA DE CALIDAD MAYOR: la columna "Subcodigo 5" contiene DOS versiones
#  de la taxonomia conviviendo. La rama antigua esta numerada "4.x" y escrita
#  en mayusculas; la vigente es "5.x". Son el mismo arbol renumerado:
#     475 filas dicen '4.2  SISTEMA DOSIFICADOR DE PINTURA, FRONTAL Y POSTERIOR.'
#     775 filas dicen '5.2 Sistema de dosificacion de pintura, frontal posterior'
#  Sin este mapeo el Pareto de causas partiria cada causa en dos y ninguna
#  alcanzaria el umbral de atencion. Lo mismo ocurre en "Sub Codigo de paro 1",
#  donde hay 45 variantes de escritura para ~25 subcodigos reales.
#
#  Observese que la rama antigua "4.x" no tenia un equivalente de la banda de
#  salida: '4.4 TRANSFER Y PISADOR DE TAPADO' corresponde a la actual 5.5, no
#  a la 5.4.
# ---------------------------------------------------------------------------
MAPEO_TAXONOMIA_HISTORICA = {
    # --- rama 4.x (historica) -> 5.x (vigente) -----------------------------
    "4.1": "5.1",
    "4.2": "5.2",
    "4.3": "5.3",
    "4.4": "5.5",   # transfer y pisador de tapado
    "4.5": "5.6",
    "4.6": "5.7",
    "4.7": "5.8",
    "4.8": "5.9",
    # --- erratas de numeracion dentro de la rama 1.x -----------------------
    "1.4.3": "1.4.C",   # el catalogo fuente escribe '1.4.3 Sensor' en vez de '1.4.C'
}

# Marcadores de "no informado" presentes en la fuente.
MARCADORES_SIN_DATO = {
    "SINESPECIFICAR", "NOAPLICA", "NO", "NA", "SINDATO", "NINGUNO", "",
}

# Patron para extraer el prefijo jerarquico de un subcodigo escrito de
# cualquier forma:  '1.2D  RETENEDORES Y ORING ' -> ('1', '2', 'D')
_PATRON_SUBCODIGO = re.compile(
    r"^\s*(?P<n1>\d)[.\-]\s*(?P<n2>\d{1,2})\s*[.\-]?\s*(?P<n3>[A-Ea-e]|\d)?(?=[\s.\-]|$)"
)


def resolver_subcodigo(valor: str | None, codigo_paro: str) -> tuple[str, bool]:
    """Normaliza un subcodigo escrito de cualquier forma al catalogo vigente.

    Devuelve (codigo_subcodigo, fue_imputado).

    Estrategia: se confia en el PREFIJO NUMERICO, no en el texto descriptivo,
    porque el texto cambia de redaccion entre anios mientras la numeracion es
    estable. Luego se aplica el mapeo de la taxonomia historica.

    Si el subcodigo no es reconocible se devuelve el miembro de relleno
    'SIN-ESP' y fue_imputado=True, lo que alimenta el indicador de completitud.
    """
    texto = limpiar(valor)
    if texto is None or clave_comparacion(texto) in MARCADORES_SIN_DATO:
        return "SIN-ESP", True

    m = _PATRON_SUBCODIGO.match(texto)
    if not m:
        return "SIN-ESP", True

    n1, n2, n3 = m.group("n1"), m.group("n2"), m.group("n3")
    # Quitar ceros a la izquierda que aparecen en algunas filas ('5.02').
    n2 = str(int(n2))

    nivel3 = f"{n1}.{n2}"
    candidato = f"{nivel3}.{n3.upper()}" if n3 else nivel3

    # Mapeo de la taxonomia historica (primero el nivel 4, luego el nivel 3).
    if candidato in MAPEO_TAXONOMIA_HISTORICA:
        candidato = MAPEO_TAXONOMIA_HISTORICA[candidato]
    elif nivel3 in MAPEO_TAXONOMIA_HISTORICA:
        nuevo3 = MAPEO_TAXONOMIA_HISTORICA[nivel3]
        # La rama historica 4.x no tiene cuarto nivel: se degrada al nivel 3.
        candidato = nuevo3

    if candidato in SUBCODIGOS and SUBCODIGOS[candidato][0] == codigo_paro:
        return candidato, False

    # El prefijo de nivel 3 si existe aunque el cuarto nivel no sea valido
    # (p. ej. '1.7A CAMBIO DE ROSCADORES', cuyo texto corresponde a 1.7.B).
    if nivel3 in SUBCODIGOS and SUBCODIGOS[nivel3][0] == codigo_paro:
        return nivel3, False

    return "SIN-ESP", True


# ===========================================================================
#  TIPO DE PARO DE LA CABECERA
#  PROBLEMA DE CALIDAD: una sola columna mezcla DOS taxonomias historicas
#  (prefijo "[NN]" la vigente, prefijo "N." en mayusculas la antigua), con 19
#  variantes para ~13 conceptos de negocio.
# ===========================================================================
TIPOS_PARO_CABECERA = [
    # (key, codigo, nombre, grupo, taxonomia, [variantes de la fuente])
    (1, "TPC-NA", "No aplica", "Sin paro de cabecera", "Vigente",
     ["[19] No aplica"]),
    (2, "TPC-MAQ", "Paro de maquina", "Paro de maquina", "Mixta",
     ["17. PARO DE MAQUINA", "[18] Paro de maquina por ventas"]),
    (3, "TPC-PLAN", "Falta de programacion (planeacion)", "Planeacion", "Historica",
     ["9.FALTA DE PROGRAMACION (PLANEACION)"]),
    (4, "TPC-PROC", "Paro por proceso anterior", "Cadena de proceso", "Historica",
     ["16.  PARO POR PROCESO ANTERIOR"]),
    (5, "TPC-MP", "Materia prima o empaque no conforme", "Materia prima", "Mixta",
     ["10. PARO POR MATERIA PRIMA O MATERIAL DE EMPAQUE NO CONFORME",
      "[12] Materia prima defectuosa o material de empaque no conforme"]),
    (6, "TPC-FALTAMP", "Falta de materiales o materias primas", "Materia prima", "Mixta",
     ["6. FALTA DE MATERIALES O MATERIAS PRIMAS", "[14] Falta de materia prima"]),
    (7, "TPC-LAB", "Aprobacion de laboratorio (microbiologia)", "Calidad", "Mixta",
     ["15. APROBACION DE LABORATORIO (MICROBIOLOGIA)",
      "[13] En espera por el aval del laboratorio de microbiologia"]),
    (8, "TPC-OPER", "Falta de operario", "Personal", "Vigente",
     ["[09] Falta de operario"]),
    (9, "TPC-AJUSTE", "Ajuste operativo", "Ajuste operativo", "Mixta",
     ["[05] Ajuste operativo", "4.AJUSTE DE OPERACION"]),
    (10, "TPC-CAMBIO", "Alistamiento / cambio de producto", "Cambio de referencia", "Mixta",
     ["[07] Alistamiento de maquina / Cambio de referencia",
      "5. AISLAMIENTO/CAMBIO DE PRODUCTO"]),
    (11, "TPC-SERV", "Ajuste electrico o de servicios industriales", "Servicios industriales", "Mixta",
     ["3. AJUSTE ELECTRICO O DE SERVICIOS (AIRE, CALDERA, GAS)",
      "[03] Novedad en los sistemas de potencia (Aire, energia, vapor)"]),
    (12, "TPC-LIMP", "Limpieza no programada", "Limpieza", "Historica",
     ["11. LIMPIEZA NO PROGRAMADA"]),
    (13, "TPC-SIN", "Sin informar", "Sin informar", "N/A", []),
]

# Indice clave_comparacion(variante) -> tipo_paro_key
_TIPO_PARO_INDICE: dict[str, int] = {}
for _key, _cod, _nom, _grp, _tax, _variantes in TIPOS_PARO_CABECERA:
    for _v in _variantes:
        _TIPO_PARO_INDICE[clave_comparacion(_v)] = _key


def resolver_tipo_paro_cabecera(valor: str | None) -> int:
    """Mapea la columna 'Tipo de paro' a la dimension consolidada.

    Si la variante exacta no esta catalogada, se intenta por el numero que
    encabeza el texto; como ultimo recurso se asigna 'Sin informar'.
    """
    texto = limpiar(valor)
    if texto is None:
        return 13
    clave = clave_comparacion(texto)
    if clave in _TIPO_PARO_INDICE:
        return _TIPO_PARO_INDICE[clave]
    # Reintento tolerante: busca una variante catalogada que empiece igual.
    for variante, key in _TIPO_PARO_INDICE.items():
        if variante and (clave.startswith(variante[:18]) or variante.startswith(clave[:18])):
            return key
    return 13


# ===========================================================================
#  AREAS INVOLUCRADAS EN EL AJUSTE OPERATIVO (codigo 05)
# ===========================================================================
AREAS_INVOLUCRADAS = [
    (1, "Operarios", "Operarios de la linea", False),
    (2, "Personal_de_mantenimiento", "Personal de mantenimiento", True),
    (3, "Auxiliar_de_piso", "Auxiliar de piso", True),
    (4, "Personal_de_despachos", "Personal de despachos", True),
    (5, "Personal_de_calidad", "Personal de calidad", True),
    (6, "Supervisor", "Supervisor de produccion", True),
    (7, "Sin informar", "Sin informar", False),
]

# ===========================================================================
#  FESTIVOS DE COLOMBIA  (Ley 51 de 1983: traslado al lunes siguiente)
#  Se calculan en dimensiones.py; aqui solo las fechas fijas y el offset de
#  los festivos moviles respecto al Domingo de Pascua.
# ===========================================================================
FESTIVOS_FIJOS = {
    (1, 1):   "Ano Nuevo",
    (5, 1):   "Dia del Trabajo",
    (7, 20):  "Dia de la Independencia",
    (8, 7):   "Batalla de Boyaca",
    (12, 8):  "Inmaculada Concepcion",
    (12, 25): "Navidad",
}
# Festivos que se trasladan al lunes siguiente (emiliani).
FESTIVOS_TRASLADABLES = {
    (1, 6):   "Reyes Magos",
    (3, 19):  "Dia de San Jose",
    (6, 29):  "San Pedro y San Pablo",
    (8, 15):  "Asuncion de la Virgen",
    (10, 12): "Dia de la Raza",
    (11, 1):  "Todos los Santos",
    (11, 11): "Independencia de Cartagena",
}
# (dias desde Pascua, nombre, se_traslada_a_lunes)
FESTIVOS_PASCUA = [
    (-3,  "Jueves Santo",            False),
    (-2,  "Viernes Santo",           False),
    (43,  "Ascension del Senor",     True),
    (64,  "Corpus Christi",          True),
    (71,  "Sagrado Corazon",         True),
]
