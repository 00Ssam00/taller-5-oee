"""Construccion de las dimensiones de dw a partir de stg y de los catalogos."""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict

from . import catalogos as cat
from .conexion import consultar, copiar, truncar

log = logging.getLogger("bi_oee")

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
DIAS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


# ===========================================================================
#  dim_fecha   -   DIMENSION CONSTRUIDA POR EL EQUIPO
# ===========================================================================
def _domingo_pascua(anio: int) -> dt.date:
    """Algoritmo de Butcher (Gauss) para el Domingo de Pascua gregoriano.

    Necesario para los festivos moviles de Colombia (Jueves y Viernes Santo,
    Ascension, Corpus Christi, Sagrado Corazon).
    """
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(anio, mes, dia)


def _festivos_colombia(anio: int) -> dict[dt.date, str]:
    """Festivos colombianos del anio, aplicando la Ley 51 de 1983 (Emiliani),
    que traslada varios festivos al lunes siguiente."""
    festivos: dict[dt.date, str] = {}

    for (mes, dia), nombre in cat.FESTIVOS_FIJOS.items():
        festivos[dt.date(anio, mes, dia)] = nombre

    def trasladar_a_lunes(fecha: dt.date) -> dt.date:
        # weekday(): 0=lunes .. 6=domingo
        return fecha + dt.timedelta(days=(7 - fecha.weekday()) % 7)

    for (mes, dia), nombre in cat.FESTIVOS_TRASLADABLES.items():
        festivos[trasladar_a_lunes(dt.date(anio, mes, dia))] = nombre

    pascua = _domingo_pascua(anio)
    for dias, nombre, se_traslada in cat.FESTIVOS_PASCUA:
        fecha = pascua + dt.timedelta(days=dias)
        festivos[trasladar_a_lunes(fecha) if se_traslada else fecha] = nombre

    return festivos


def construir_dim_fecha(conexion, anio_inicio: int, anio_fin: int) -> int:
    truncar(conexion, "dw.dim_fecha")
    festivos: dict[dt.date, str] = {}
    for anio in range(anio_inicio - 1, anio_fin + 2):
        festivos.update(_festivos_colombia(anio))

    columnas = [
        "fecha_key", "fecha", "anio", "trimestre", "nombre_trimestre", "mes",
        "nombre_mes", "nombre_mes_corto", "anio_mes", "etiqueta_anio_mes", "dia",
        "dia_del_anio", "dia_semana_iso", "nombre_dia", "nombre_dia_corto",
        "semana_iso", "anio_semana_iso", "es_fin_semana", "es_festivo",
        "nombre_festivo", "es_dia_habil", "fecha_key_anio_ant", "anio_mes_anio_ant",
    ]

    def generar():
        fecha = dt.date(anio_inicio, 1, 1)
        fin = dt.date(anio_fin, 12, 31)
        un_dia = dt.timedelta(days=1)
        while fecha <= fin:
            iso_anio, iso_semana, iso_dia = fecha.isocalendar()
            trimestre = (fecha.month - 1) // 3 + 1
            es_fin_semana = iso_dia >= 6
            nombre_festivo = festivos.get(fecha)
            es_festivo = nombre_festivo is not None
            # Mismo dia del ano anterior; el 29 de febrero se mapea al 28.
            try:
                fecha_ant = fecha.replace(year=fecha.year - 1)
            except ValueError:
                fecha_ant = dt.date(fecha.year - 1, 2, 28)
            yield [
                int(fecha.strftime("%Y%m%d")),
                fecha,
                fecha.year,
                trimestre,
                f"T{trimestre}",
                fecha.month,
                MESES_ES[fecha.month - 1],
                MESES_ES[fecha.month - 1][:3],
                fecha.year * 100 + fecha.month,
                f"{fecha.year}-{fecha.month:02d}",
                fecha.day,
                fecha.timetuple().tm_yday,
                iso_dia,
                DIAS_ES[iso_dia - 1],
                DIAS_ES[iso_dia - 1][:3],
                iso_semana,
                iso_anio * 100 + iso_semana,
                es_fin_semana,
                es_festivo,
                nombre_festivo,
                not es_fin_semana and not es_festivo,
                int(fecha_ant.strftime("%Y%m%d")),
                (fecha.year - 1) * 100 + fecha.month,
            ]
            fecha += un_dia

    return copiar(conexion, "dw.dim_fecha", columnas, generar())


# ===========================================================================
#  Dimensiones de catalogo fijo
# ===========================================================================
def construir_dim_maquina(conexion) -> int:
    truncar(conexion, "dw.dim_maquina")
    filas = [
        [key, codigo, nombre, linea, "Planta Vinilos y Temperas",
         "Vinilos y temperas", factor, grupo, True]
        for key, codigo, nombre, linea, factor, grupo in cat.MAQUINAS
    ]
    return copiar(
        conexion, "dw.dim_maquina",
        ["maquina_key", "codigo_maquina", "nombre_maquina", "numero_linea", "planta",
         "familia_producto", "factor_produccion", "grupo_capacidad", "es_activa"],
        filas,
    )


def construir_dim_turno(conexion) -> int:
    truncar(conexion, "dw.dim_turno")
    filas = []
    for (key, codigo, nombre, etiqueta, inicio, fin, duracion,
         jornada, nocturno, orden, valido) in cat.TURNOS:
        filas.append([
            key, codigo, nombre, etiqueta,
            dt.time.fromisoformat(inicio) if inicio else None,
            dt.time.fromisoformat(fin) if fin else None,
            duracion, jornada, nocturno, orden, valido,
        ])
    return copiar(
        conexion, "dw.dim_turno",
        ["turno_key", "codigo_turno", "nombre_turno", "etiqueta_fuente", "hora_inicio",
         "hora_fin", "duracion_horas", "tipo_jornada", "es_nocturno",
         "orden_presentacion", "es_valido"],
        filas,
    )


def construir_dim_area(conexion) -> int:
    truncar(conexion, "dw.dim_area_involucrada")
    return copiar(
        conexion, "dw.dim_area_involucrada",
        ["area_key", "codigo_area", "nombre_area", "es_area_soporte"],
        [list(a) for a in cat.AREAS_INVOLUCRADAS],
    )


def construir_dim_tipo_paro(conexion) -> int:
    truncar(conexion, "dw.dim_tipo_paro_cabecera")
    filas = [
        [key, codigo, nombre, grupo, taxonomia,
         " | ".join(variantes) if variantes else None]
        for key, codigo, nombre, grupo, taxonomia, variantes in cat.TIPOS_PARO_CABECERA
    ]
    return copiar(
        conexion, "dw.dim_tipo_paro_cabecera",
        ["tipo_paro_key", "codigo_tipo", "nombre_tipo", "grupo_tipo",
         "taxonomia_origen", "variantes_fuente"],
        filas,
    )


# ===========================================================================
#  dim_paro   -   jerarquia de cuatro niveles, grano subcodigo
# ===========================================================================
def construir_dim_paro(conexion) -> tuple[int, dict[tuple[str, str], int]]:
    """Genera un miembro por cada combinacion valida codigo x subcodigo, mas
    los miembros de relleno de la jerarquia ragged."""
    truncar(conexion, "dw.dim_paro")
    sistemas = dict(cat.SISTEMAS)
    filas: list[list] = []
    indice: dict[tuple[str, str], int] = {}
    key = 0
    orden = 0

    for codigo, nombre, area, naturaleza, imputable, admite_sub in cat.CODIGOS_PARO:
        etiqueta = f"[{codigo}] {nombre}"

        # --- Miembro de relleno: el paro reportado sin subcodigo -----------
        key += 1
        orden += 1
        if admite_sub:
            cod_sub, nom_sub, nivel = "SIN-ESP", "Sin subcodigo informado", 2
        else:
            cod_sub, nom_sub, nivel = "N/A", "No aplica (codigo sin subcodigos)", 2
        filas.append([
            key, area, codigo, int(codigo), nombre, etiqueta, naturaleza, imputable,
            "SYS-NA", sistemas["SYS-NA"], cod_sub, nom_sub, nivel, admite_sub,
            False, orden,
        ])
        indice[(codigo, cod_sub)] = key

        if not admite_sub:
            continue

        # --- Miembros con subcodigo, ordenados por su numeracion natural ---
        propios = [
            (sc, nom) for sc, (padre, nom) in cat.SUBCODIGOS.items() if padre == codigo
        ]

        def clave_orden(par):
            partes = par[0].split(".")
            nivel4 = partes[2] if len(partes) > 2 else ""
            return (int(partes[0]), int(partes[1]), nivel4)

        for subcodigo, nombre_sub in sorted(propios, key=clave_orden):
            key += 1
            orden += 1
            prefijo3 = ".".join(subcodigo.split(".")[:2])
            cod_sys = cat.PREFIJO_A_SISTEMA.get(prefijo3, "SYS-NA")
            es_nivel4 = len(subcodigo.split(".")) == 3
            filas.append([
                key, area, codigo, int(codigo), nombre, etiqueta, naturaleza, imputable,
                cod_sys, sistemas[cod_sys],
                subcodigo, f"{subcodigo} {nombre_sub}",
                4 if es_nivel4 else 4, True, True, orden,
            ])
            indice[(codigo, subcodigo)] = key

    total = copiar(
        conexion, "dw.dim_paro",
        ["paro_key", "area_impacto", "codigo_paro", "codigo_paro_numero",
         "nombre_codigo_paro", "etiqueta_codigo_paro", "naturaleza_paro",
         "es_imputable_mantenimiento", "codigo_sistema", "nombre_sistema",
         "codigo_subcodigo", "nombre_subcodigo", "nivel_detalle", "admite_subcodigo",
         "es_subcodigo_especificado", "orden_presentacion"],
        filas,
    )
    return total, indice


# ===========================================================================
#  Dimensiones pseudonimizadas de personas
# ===========================================================================
def construir_dim_operario(conexion, salt: str) -> tuple[int, dict[str, int]]:
    """Construye dim_operario sin nombres y pii.operario_identidad con ellos.

    TRATAMIENTO DE DATOS PERSONALES: el nombre de la operaria solo se escribe
    en el esquema pii, al que el rol de los tableros no tiene acceso.
    """
    truncar(conexion, "pii.operario_identidad")
    truncar(conexion, "dw.dim_operario")

    nombres = consultar(conexion, """
        SELECT DISTINCT operario FROM (
            SELECT operario FROM stg.base_datos      WHERE operario IS NOT NULL
            UNION SELECT operario FROM stg.catalogo_operario WHERE operario IS NOT NULL
        ) t ORDER BY operario
    """)

    # Agrupar por clave canonica: resuelve diferencias de espaciado.
    canonicos: dict[str, str] = {}
    for (nombre,) in nombres:
        limpio = cat.limpiar(nombre)
        if limpio is None:
            continue
        canonicos.setdefault(cat.clave_comparacion(limpio), limpio)

    # Los marcadores de ausencia se consolidan en un unico miembro tecnico.
    marcadores = {k for k in canonicos if k in cat.MARCADORES_SIN_DATO}
    reales = sorted(k for k in canonicos if k not in marcadores)

    filas_dim, filas_pii = [], []
    indice: dict[str, int] = {}

    # Miembro tecnico 0: operario no informado.
    filas_dim.append([0, "OPR-000", "Sin informar",
                      "Sin informar", False, None, None, 0])
    for k in marcadores:
        indice[k] = 0
    indice[""] = 0

    for i, clave in enumerate(reales, 1):
        nombre = canonicos[clave]
        h = cat.pseudonimo(nombre, salt)
        # La huella `h` va UNICAMENTE a pii: es la llave de vinculacion con el
        # nombre real y no debe salir del esquema restringido.
        filas_dim.append([
            i, f"OPR-{i:03d}", f"Operario {i:03d}",
            "Operario de envasado", True, None, None, 0,
        ])
        filas_pii.append([i, nombre, h])
        indice[clave] = i

    total = copiar(
        conexion, "dw.dim_operario",
        ["operario_key", "codigo_operario", "alias_operario", "rol",
         "es_identificado", "primera_aparicion", "ultima_aparicion", "turnos_registrados"],
        filas_dim,
    )
    copiar(conexion, "pii.operario_identidad",
           ["operario_key", "nombre_fuente", "hash_identidad"], filas_pii)
    log.info("    (pii) %d identidades reales almacenadas en esquema restringido",
             len(filas_pii))
    return total, indice


def construir_dim_personal(conexion, salt: str) -> tuple[int, dict[str, int]]:
    truncar(conexion, "pii.personal_identidad")
    truncar(conexion, "dw.dim_personal_mantenimiento")

    nombres = consultar(conexion, """
        SELECT DISTINCT cod05_personal FROM stg.base_datos
        WHERE cod05_personal IS NOT NULL ORDER BY 1
    """)
    canonicos: dict[str, str] = {}
    for (nombre,) in nombres:
        limpio = cat.limpiar(nombre)
        if limpio is None:
            continue
        canonicos.setdefault(cat.clave_comparacion(limpio), limpio)

    marcadores = {k for k in canonicos if k in cat.MARCADORES_SIN_DATO}
    reales = sorted(k for k in canonicos if k not in marcadores)

    filas_dim = [[0, "TEC-000", "Sin informar", "Mantenimiento", False]]
    filas_pii = []
    indice: dict[str, int] = {k: 0 for k in marcadores}
    indice[""] = 0

    for i, clave in enumerate(reales, 1):
        nombre = canonicos[clave]
        h = cat.pseudonimo(nombre, salt)
        filas_dim.append([i, f"TEC-{i:03d}", f"Tecnico {i:03d}", "Mantenimiento", True])
        filas_pii.append([i, nombre, h])
        indice[clave] = i

    total = copiar(
        conexion, "dw.dim_personal_mantenimiento",
        ["personal_key", "codigo_personal", "alias_personal",
         "area", "es_identificado"],
        filas_dim,
    )
    copiar(conexion, "pii.personal_identidad",
           ["personal_key", "nombre_fuente", "hash_identidad"], filas_pii)
    return total, indice


# ===========================================================================
#  dim_referencia
# ===========================================================================
def construir_dim_referencia(conexion) -> tuple[int, dict[str, int], dict[str, int]]:
    """Consolida las referencias del catalogo y de los hechos.

    Devuelve (total, indice clave_canonica -> key, unidades_por_paca por key).
    """
    truncar(conexion, "dw.dim_referencia")

    del_catalogo = consultar(conexion, """
        SELECT referencia,
               max(nullif(unidades_por_paca,'')::numeric)  AS unid_paca,
               max(nullif(numero_colores,'')::numeric)     AS colores,
               max(nullif(display,'')::numeric)            AS display
        FROM stg.catalogo_estandar
        WHERE referencia IS NOT NULL
        GROUP BY referencia
    """)
    de_hechos = consultar(conexion, """
        SELECT DISTINCT referencia FROM stg.base_datos WHERE referencia IS NOT NULL
    """)

    # --- Paso 1: consolidar por clave canonica, aplicando las correcciones --
    datos: dict[str, dict] = {}
    variantes: dict[str, set[str]] = defaultdict(set)

    def registrar(nombre_crudo: str, unid_paca=None, colores=None, display=None):
        limpio = cat.limpiar(nombre_crudo)
        if limpio is None:
            return
        clave = cat.clave_comparacion(limpio)
        # REGLA DE LIMPIEZA: correccion de erratas tipograficas conocidas.
        if clave in cat.CORRECCION_REFERENCIA:
            canonico = cat.CORRECCION_REFERENCIA[clave]
            clave = cat.clave_comparacion(canonico)
            variantes[clave].add(f"{limpio} (corregido)")
            limpio = canonico
        else:
            variantes[clave].add(limpio)
        registro = datos.setdefault(clave, {"nombre": limpio})
        # Preferir el nombre con el formato del catalogo (mas prolijo).
        if " col)" in limpio and " col)" not in registro["nombre"]:
            registro["nombre"] = limpio
        for campo, valor in (("unid_paca", unid_paca), ("colores", colores),
                             ("display", display)):
            if valor is not None and registro.get(campo) is None:
                registro[campo] = float(valor)

    for nombre, unid_paca, colores, display in del_catalogo:
        registrar(nombre, unid_paca, colores, display)
    for (nombre,) in de_hechos:
        registrar(nombre)

    # --- Paso 2: construir las filas de la dimension ----------------------
    filas, indice, unid_paca_por_key = [], {}, {}
    # Miembro tecnico 0 para los hechos sin referencia informada.
    filas.append([0, "SIN-INFORMAR", "Sin informar", "Sin informar", None, None,
                  None, None, None, True, False, None])
    indice[""] = 0
    unid_paca_por_key[0] = None

    for i, clave in enumerate(sorted(datos, key=lambda k: datos[k]["nombre"]), 1):
        registro = datos[clave]
        nombre = registro["nombre"]
        analisis = cat.analizar_referencia(nombre)
        colores = registro.get("colores") or analisis["numero_colores"]
        display = registro.get("display")
        unid_paca = registro.get("unid_paca")
        # Si falta, se deriva: unidades por paca = colores x display por paca.
        if unid_paca is None and colores and display:
            unid_paca = colores * display
        es_na = cat.clave_comparacion(nombre) in cat.MARCADORES_SIN_DATO

        filas.append([
            i, nombre, nombre, analisis["linea_comercial"],
            analisis["volumen_cc"], analisis["etiqueta_presentacion"],
            int(colores) if colores else None,
            int(display) if display else None,
            int(unid_paca) if unid_paca else None,
            es_na,
            registro.get("unid_paca") is not None,
            " | ".join(sorted(variantes[clave])) if len(variantes[clave]) > 1 else None,
        ])
        indice[clave] = i
        unid_paca_por_key[i] = int(unid_paca) if unid_paca else None

    total = copiar(
        conexion, "dw.dim_referencia",
        ["referencia_key", "codigo_referencia", "nombre_referencia", "linea_comercial",
         "volumen_cc", "etiqueta_presentacion", "numero_colores", "display_por_paca",
         "unidades_por_paca", "es_no_aplica", "tiene_estandar", "variantes_fuente"],
        filas,
    )
    return total, indice, unid_paca_por_key


# ===========================================================================
#  dim_estandar   -   SCD TIPO 2
# ===========================================================================
def construir_dim_estandar(
    conexion, indice_referencia: dict[str, int], unid_paca_por_key: dict[int, int | None]
) -> tuple[int, dict[tuple[int, int], tuple[int, float, str]]]:
    """Construye el estandar de produccion por par maquina x referencia.

    ESTRATEGIA DE RESOLUCION EN CASCADA (documentada y auditable):
      1. El par (maquina, referencia) existe en el catalogo de la fuente
         -> se usa su tasa tal cual.              origen = 'Catalogo fuente'
      2. El par no existe, pero la referencia SI tiene tasa en otra maquina
         -> se toma la mediana de esas tasas y se ajusta por el cociente de
            factores de produccion de las maquinas.
                                                  origen = 'Inferido por referencia'
      3. No hay ninguna tasa para la referencia
         -> no se crea estandar; el turno queda con tiene_estandar = false y
            se excluye del calculo de Rendimiento (nunca se inventa un dato).
                                                  origen = 'Sin estandar'

    SCD TIPO 2: se crea la version 1 con valido_desde = inicio de la serie
    historica. La estructura (version / valido_desde / valido_hasta /
    es_vigente) queda lista para que la proxima reestandarizacion de
    ingenieria cierre la fila vigente y abra una nueva sin reescribir el
    historico, que es justamente lo que protege los comparativos interanuales.
    """
    truncar(conexion, "dw.dim_estandar")

    maquina_por_codigo = {codigo: key for key, codigo, *_ in cat.MAQUINAS}
    factor_por_key = {key: factor for key, _c, _n, _l, factor, _g in cat.MAQUINAS}

    catalogo = consultar(conexion, """
        SELECT maquina, referencia,
               max(nullif(unidades_por_minuto,'')::numeric) AS tasa,
               max(nullif(unidades_por_paca,'')::numeric)   AS unid_paca
        FROM stg.catalogo_estandar
        WHERE referencia IS NOT NULL AND maquina IS NOT NULL
        GROUP BY maquina, referencia
    """)

    # Pares que aparecen realmente en los hechos (para decidir que inferir).
    pares_hechos = consultar(conexion, """
        SELECT DISTINCT maquina, referencia FROM stg.base_datos
        WHERE maquina IS NOT NULL AND referencia IS NOT NULL
    """)

    # --- Tasas directas del catalogo --------------------------------------
    directo: dict[tuple[int, int], tuple[float, int | None]] = {}
    tasas_por_referencia: dict[int, list[tuple[int, float]]] = defaultdict(list)

    for maquina, referencia, tasa, unid_paca in catalogo:
        m_key = maquina_por_codigo.get(cat.limpiar(maquina) or "")
        r_key = indice_referencia.get(cat.clave_comparacion(cat.limpiar(referencia)))
        if m_key is None or r_key is None or tasa is None:
            continue
        tasa = float(tasa)
        if tasa <= 0:
            continue   # las filas 'No aplica' del catalogo traen 0
        directo[(m_key, r_key)] = (tasa, int(unid_paca) if unid_paca else None)
        tasas_por_referencia[r_key].append((m_key, tasa))

    # --- Inferencia para los pares de hechos sin catalogo -----------------
    inferido: dict[tuple[int, int], float] = {}
    sin_estandar: set[tuple[int, int]] = set()

    for maquina, referencia in pares_hechos:
        m_key = maquina_por_codigo.get(cat.limpiar(maquina) or "")
        clave_ref = cat.clave_comparacion(cat.limpiar(referencia))
        # Aplicar la correccion de erratas antes de buscar.
        if clave_ref in cat.CORRECCION_REFERENCIA:
            clave_ref = cat.clave_comparacion(cat.CORRECCION_REFERENCIA[clave_ref])
        r_key = indice_referencia.get(clave_ref)
        if m_key is None or r_key is None or r_key == 0:
            continue
        if (m_key, r_key) in directo:
            continue
        candidatas = tasas_por_referencia.get(r_key, [])
        if not candidatas:
            sin_estandar.add((m_key, r_key))
            continue
        valores = sorted(t for _m, t in candidatas)
        mediana = valores[len(valores) // 2]
        # Ajuste por capacidad relativa de las maquinas.
        factor_origen = sum(factor_por_key[m] for m, _t in candidatas) / len(candidatas)
        inferido[(m_key, r_key)] = round(mediana * factor_por_key[m_key] / factor_origen, 3)

    # --- Materializar las filas SCD2 --------------------------------------
    INICIO_HISTORIA = dt.date(2022, 1, 1)
    FIN_ABIERTO = dt.date(9999, 12, 31)
    filas, indice = [], {}
    key = 0

    for (m_key, r_key), (tasa, unid_paca_cat) in sorted(directo.items()):
        unid_paca = unid_paca_cat or unid_paca_por_key.get(r_key) or 1
        key += 1
        filas.append([
            key, m_key, r_key, tasa, unid_paca,
            round(tasa * 60 / unid_paca, 3),
            1, INICIO_HISTORIA, FIN_ABIERTO, True,
            "Catalogo fuente", "Carga inicial del historico",
        ])
        indice[(m_key, r_key)] = (key, tasa, "Catalogo fuente")

    for (m_key, r_key), tasa in sorted(inferido.items()):
        unid_paca = unid_paca_por_key.get(r_key) or 1
        key += 1
        filas.append([
            key, m_key, r_key, tasa, unid_paca,
            round(tasa * 60 / unid_paca, 3),
            1, INICIO_HISTORIA, FIN_ABIERTO, True,
            "Inferido por referencia",
            "Par maquina-referencia ausente del catalogo de la fuente",
        ])
        indice[(m_key, r_key)] = (key, tasa, "Inferido por referencia")

    total = copiar(
        conexion, "dw.dim_estandar",
        ["estandar_key", "maquina_key", "referencia_key", "unidades_por_minuto",
         "unidades_por_paca", "pacas_meta_hora", "version", "valido_desde",
         "valido_hasta", "es_vigente", "origen_estandar", "motivo_cambio"],
        filas,
    )
    log.info("    estandares: %d del catalogo, %d inferidos, %d pares sin estandar",
             len(directo), len(inferido), len(sin_estandar))
    return total, indice
