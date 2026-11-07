# -*- coding: utf-8 -*-
"""Genera sql/init/70_diccionario.sql: el diccionario de datos vive en la base.

Cada columna lleva descripcion, ORIGEN (de donde sale el dato) y REGLA (que
transformacion se le aplico). Asi `\\d+` en DBeaver muestra el diccionario
durante la sustentacion, y el documento entregable se genera desde aqui en
vez de escribirse aparte y envejecer.
"""
import pathlib

SK = "Llave surrogada entera, generada por el ETL. ORIGEN: construida. REGLA: numeracion secuencial; el valor 0 se reserva al miembro 'no informado' para no usar NULL en las tablas de hechos."
AUD_EJ = "Identificador de la ejecucion del ETL que cargo la fila. ORIGEN: construida. REGLA: permite auditar y revertir una carga concreta."
AUD_CG = "Marca de tiempo de la carga. ORIGEN: construida. REGLA: default now()."
FILA = "Numero de fila en la hoja 'Base De Datos' del Excel (la fila 10 es la primera con datos). ORIGEN: construida. REGLA: trazabilidad: permite volver a la celda exacta del Excel ante cualquier duda."

C = {
"dim_area_involucrada": {
 "area_key": SK,
 "codigo_area": "Codigo corto del area. ORIGEN: construida. REGLA: derivado del nombre, sin tildes ni espacios.",
 "nombre_area": "Area de la empresa que atendio el paro. ORIGEN: columna 'Area involucrada' de la hoja Base De Datos. REGLA: se normalizo capitalizacion y se consolidaron variantes de escritura en 7 miembros.",
 "es_area_soporte": "Verdadero si el area es de soporte (mantenimiento, calidad, laboratorio) y no de produccion. ORIGEN: construida. REGLA: clasificacion manual del equipo, usada para separar la responsabilidad del paro.",
},
"dim_estandar": {
 "estandar_key": SK,
 "maquina_key": "Llave a dim_maquina. ORIGEN: construida. REGLA: el estandar es especifico del par maquina-referencia, porque la misma referencia corre a distinta velocidad en cada linea.",
 "referencia_key": "Llave a dim_referencia. ORIGEN: construida.",
 "unidades_por_minuto": "Tasa ideal de produccion: unidades que la linea debe envasar por minuto. ORIGEN: columna 'unidades *minuto' del bloque maquina x referencia de la hoja 'Tablas Desplegables'. REGLA: es el estandar de ingenieria y el denominador del Rendimiento del OEE. Es el dato que hacia falta para poder calcular OEE y que estaba en una hoja auxiliar, no en la hoja de hechos.",
 "unidades_por_paca": "Unidades que contiene una paca de esta referencia. ORIGEN: columna 'Unidades * paca' de la hoja 'Tablas Desplegables'. REGLA: convierte las pacas que registra el operario en unidades comparables entre referencias de 6 y de 12 colores.",
 "pacas_meta_hora": "Meta de pacas por hora derivada del estandar. ORIGEN: construida. REGLA: unidades_por_minuto * 60 / unidades_por_paca. Se expresa en pacas porque es la unidad en que piensa el operario.",
 "version": "Numero de version del estandar para el par maquina-referencia. ORIGEN: construida. REGLA: SCD Tipo 2; empieza en 1 y se incrementa en cada cambio del estandar.",
 "valido_desde": "Fecha desde la que rige esta version del estandar. ORIGEN: construida. REGLA: SCD Tipo 2.",
 "valido_hasta": "Fecha hasta la que rigio esta version; NULL si es la vigente. ORIGEN: construida. REGLA: SCD Tipo 2.",
 "es_vigente": "Verdadero en la version actual del estandar. ORIGEN: construida. REGLA: SCD Tipo 2; un indice unico parcial garantiza que solo exista una version vigente por par maquina-referencia.",
 "origen_estandar": "Como se obtuvo el estandar: 'Catalogo' si venia en Tablas Desplegables, 'Inferido' si se dedujo de otra linea ajustando por el factor de produccion, 'Sin estandar' si no fue posible. ORIGEN: construida. REGLA: hace explicito el nivel de confianza del dato; los turnos con 'Sin estandar' quedan fuera del calculo del Rendimiento.",
 "motivo_cambio": "Razon del cambio de version del estandar. ORIGEN: construida. REGLA: texto libre para auditar el historial del SCD2.",
},
"dim_fecha": {
 "fecha_key": "Llave surrogada con formato AAAAMMDD, legible a simple vista. ORIGEN: construida. REGLA: entero en lugar de fecha para que los indices y los JOIN sean mas compactos, y para poder leer la llave sin consultar la dimension.",
 "fecha": "Fecha del calendario. ORIGEN: construida. REGLA: columna marcada como fecha del modelo en Power BI; es la que usan las funciones de inteligencia de tiempo de DAX.",
 "anio": "Ano del calendario. ORIGEN: construida.",
 "trimestre": "Numero de trimestre, 1 a 4. ORIGEN: construida.",
 "nombre_trimestre": "Trimestre como texto, por ejemplo 'T1'. ORIGEN: construida.",
 "mes": "Numero de mes, 1 a 12. ORIGEN: construida. REGLA: ordena a nombre_mes, para que los meses no salgan en orden alfabetico.",
 "nombre_mes": "Nombre del mes en espanol. ORIGEN: construida. REGLA: generado en el ETL y no con to_char, para no depender de la configuracion regional del servidor.",
 "nombre_mes_corto": "Abreviatura del mes, por ejemplo 'ene'. ORIGEN: construida.",
 "anio_mes": "Periodo como entero AAAAMM. ORIGEN: construida. REGLA: sirve para ordenar y para las funciones de ventana que comparan periodos.",
 "etiqueta_anio_mes": "Periodo legible, por ejemplo '2024-03'. ORIGEN: construida.",
 "dia": "Dia del mes. ORIGEN: construida.",
 "dia_del_anio": "Dia del ano, 1 a 366. ORIGEN: construida.",
 "dia_semana_iso": "Dia de la semana ISO: 1 lunes a 7 domingo. ORIGEN: construida. REGLA: se usa el estandar ISO y no el de PostgreSQL (0 domingo) para que la semana empiece en lunes, como en la planta.",
 "nombre_dia": "Nombre del dia de la semana en espanol. ORIGEN: construida.",
 "nombre_dia_corto": "Abreviatura del dia. ORIGEN: construida.",
 "semana_iso": "Numero de semana ISO. ORIGEN: construida.",
 "anio_semana_iso": "Ano de la semana ISO. ORIGEN: construida. REGLA: puede diferir de anio en la primera y la ultima semana del ano; se guarda aparte para no partir semanas al agregar.",
 "es_fin_semana": "Verdadero en sabado y domingo. ORIGEN: construida.",
 "es_festivo": "Verdadero si es festivo en Colombia. ORIGEN: construida. REGLA: festivos fijos, mas los calculados desde el Domingo de Pascua con el algoritmo de Butcher, mas los trasladables al lunes siguiente segun la Ley 51 de 1983 (Ley Emiliani).",
 "nombre_festivo": "Nombre del festivo; NULL si no es festivo. ORIGEN: construida.",
 "es_dia_habil": "Verdadero si no es fin de semana ni festivo. ORIGEN: construida. REGLA: permite separar la produccion de dia habil de la de festivo, que tiene costo de mano de obra distinto.",
 "fecha_key_anio_ant": "fecha_key del mismo dia del ano anterior. ORIGEN: construida. REGLA: precalculada para que los comparativos interanuales en SQL sean un JOIN y no un calculo de fechas en cada consulta.",
 "anio_mes_anio_ant": "anio_mes del mismo mes del ano anterior. ORIGEN: construida. REGLA: igual que la anterior, para comparativos mensuales.",
},
"dim_maquina": {
 "maquina_key": SK,
 "codigo_maquina": "Codigo de la linea tal como lo escribe la fuente: Vinilos_1 a Vinilos_4. ORIGEN: columna 'Maquina' de la hoja Base De Datos. REGLA: se conserva el codigo original para poder conciliar contra el Excel.",
 "nombre_maquina": "Nombre legible de la linea. ORIGEN: construida.",
 "numero_linea": "Numero de linea, 1 a 4. ORIGEN: construida. REGLA: extraido del codigo; ordena la presentacion.",
 "planta": "Planta donde esta la linea. ORIGEN: construida. REGLA: valor unico por ahora; la columna existe para que el modelo admita una segunda planta sin rediseno.",
 "familia_producto": "Familia de producto que envasa la linea. ORIGEN: construida.",
 "factor_produccion": "Multiplicador de capacidad de la linea respecto de la de referencia: V1 1,100, V2 1,160, V3 y V4 1,000. ORIGEN: estaba ESCONDIDO dentro de una formula de texto de la hoja 'Tiempos', no en ninguna celda de datos. REGLA: se extrajo leyendo la formula; permite inferir el estandar de una linea a partir del de otra cuando el catalogo no trae el par maquina-referencia.",
 "grupo_capacidad": "Agrupacion por capacidad relativa. ORIGEN: construida. REGLA: derivada del factor de produccion; agrupa lineas comparables entre si.",
 "es_activa": "Verdadero si la linea esta en operacion. ORIGEN: construida.",
},
"dim_operario": {
 "operario_key": SK,
 "codigo_operario": "Codigo pseudonimo estable, formato OPER-NNN. ORIGEN: construida. REGLA: se asigna por orden de aparicion; es estable entre ejecuciones del ETL.",
 "alias_operario": "Alias que se muestra en los tableros, formato 'Operario NNN'. ORIGEN: construida. REGLA: PSEUDONIMIZACION. Es el unico identificador que sale del esquema dw; el nombre real nunca llega a los tableros.",
 "rol": "Rol del trabajador. ORIGEN: construida.",
 "es_identificado": "Falso en el miembro 'Sin informar'. ORIGEN: construida. REGLA: la fuente trae 'No' y 'No aplica' como marcadores de ausencia; se consolidan en un unico miembro de relleno con llave 0.",
 "primera_aparicion": "Primera fecha en que aparece el operario. ORIGEN: derivada de la hoja Base De Datos. REGLA: min(fecha) de sus registros.",
 "ultima_aparicion": "Ultima fecha en que aparece. ORIGEN: derivada. REGLA: max(fecha) de sus registros.",
 "turnos_registrados": "Numero de turnos en que aparece. ORIGEN: derivada. REGLA: conteo de registros; sirve para distinguir al personal de planta del eventual.",
},
"dim_paro": {
 "paro_key": SK,
 "area_impacto": "NIVEL 1 de la jerarquia de paros: area responsable de la causa. ORIGEN: construida. REGLA: clasificacion de los 18 codigos de paro segun quien debe actuar (Mantenimiento, Produccion, Calidad, Logistica, Servicios generales).",
 "codigo_paro": "Codigo de paro de dos digitos, '01' a '18'. ORIGEN: cabecera de los 18 pares de columnas de la hoja Base De Datos. REGLA: el codigo se deduce de la POSICION de la columna, no de su texto, porque los encabezados tienen variantes de escritura.",
 "codigo_paro_numero": "El codigo como entero, para ordenar. ORIGEN: construida.",
 "nombre_codigo_paro": "Descripcion del codigo segun el procedimiento P-MTO-22. ORIGEN: documento P-MTO-22 V1, vigente desde el 14/05/2025. REGLA: se toma la descripcion oficial del procedimiento, no la del encabezado del Excel, que esta abreviada.",
 "etiqueta_codigo_paro": "NIVEL 2 de la jerarquia: codigo y descripcion juntos, por ejemplo '[05] Ajuste operativo'. ORIGEN: construida. REGLA: es la etiqueta que se muestra en los tableros; incluir el numero permite cruzarla con el formato en papel que usa la planta.",
 "naturaleza_paro": "'Planeado' o 'No planeado'. ORIGEN: construida. REGLA: se clasifican como planeados los codigos 04, 08, 15, 16, 17 y 18 (mantenimiento preventivo, capacitacion, cambio de insumos, aseo, pausa activa y afines). Es la separacion que distingue el tiempo perdido EVITABLE del que es parte normal de la operacion, y sin ella el OEE castiga a la planta por hacer lo correcto.",
 "es_imputable_mantenimiento": "Verdadero si el paro es responsabilidad del area de mantenimiento. ORIGEN: construida. REGLA: permite medir el desempeno de mantenimiento sin cargarle los paros de produccion o de logistica.",
 "codigo_sistema": "Codigo del sistema fisico de la maquina. ORIGEN: construida. REGLA: ATRIBUTO CONFORMADO, lo mas importante de esta dimension. Se deduce del prefijo numerico del subcodigo y unifica las ramas 1.x (falla electromecanica), 3.x (servicios) y 5.x (ajuste operativo) en el sistema al que todas se refieren.",
 "nombre_sistema": "NIVEL 3 de la jerarquia: nombre del sistema fisico, por ejemplo 'Sistema de dosificacion de pintura'. ORIGEN: construida. REGLA: el Excel NO puede responder 'que sistema me cuesta mas tiempo' porque las tres ramas viven en columnas separadas. Al unificarlas se descubrio que el sistema dosificador explica el 44,6% del tiempo perdido de los codigos 01/03/05 (992 de 2.222,8 h), el 11,8% del tiempo perdido total.",
 "codigo_subcodigo": "Codigo del subcodigo de causa raiz. ORIGEN: columnas 'Subcodigo N' de la hoja Base De Datos y hoja oculta 'Base de datos de Sub codigos'. REGLA: la fuente tiene DOS taxonomias conviviendo; la rama 4.x historica se mapea a la 5.x vigente (4.1 a 5.1, 4.2 a 5.2, 4.3 a 5.3, 4.4 a 5.5, 4.5 a 5.6, 4.6 a 5.7, 4.7 a 5.8, 4.8 a 5.9) y se corrige la errata del propio catalogo (1.4.3 debia ser 1.4.C).",
 "nombre_subcodigo": "NIVEL 4 de la jerarquia: causa raiz concreta. ORIGEN: idem. REGLA: la fuente trae 45 variantes de escritura para unos 25 subcodigos del codigo 01; se resuelven confiando en el PREFIJO NUMERICO y no en el texto, que es el dato fiable.",
 "nivel_detalle": "Profundidad real del miembro en la jerarquia, 2 a 4. ORIGEN: construida. REGLA: la jerarquia es DESBALANCEADA (ragged): solo los codigos 01, 03 y 05 tienen subcodigos. Esta columna dice hasta donde se puede bajar en cada rama.",
 "admite_subcodigo": "Verdadero en los codigos 01, 03 y 05. ORIGEN: construida. REGLA: evita medir como 'dato incompleto' la ausencia de subcodigo en los 15 codigos que no lo tienen; sin esta distincion el indicador de completitud daria un 78% de falsos positivos.",
 "es_subcodigo_especificado": "Falso en los miembros de relleno 'N/A' y 'SIN-ESP'. ORIGEN: construida. REGLA: la jerarquia desbalanceada se resuelve con miembros de relleno EXPLICITOS en lugar de NULL, de modo que el drill-down del tablero nunca aterriza en un hueco.",
 "orden_presentacion": "Orden de presentacion del miembro. ORIGEN: construida.",
},
"dim_personal_mantenimiento": {
 "personal_key": SK,
 "codigo_personal": "Codigo pseudonimo estable, formato TEC-NNN. ORIGEN: construida.",
 "alias_personal": "Alias mostrado en los tableros, formato 'Tecnico NNN'. ORIGEN: construida. REGLA: PSEUDONIMIZACION, igual que en dim_operario.",
 "area": "Area del tecnico. ORIGEN: derivada de la fuente. REGLA: normalizada.",
 "es_identificado": "Falso en el miembro 'Sin informar'. ORIGEN: construida.",
},
"dim_referencia": {
 "referencia_key": SK,
 "codigo_referencia": "Codigo normalizado de la referencia. ORIGEN: construida. REGLA: nombre sin tildes, en mayusculas y sin espacios; es la clave con que se consolidan las variantes de escritura.",
 "nombre_referencia": "Nombre de la referencia, depurado. ORIGEN: columna 'Referencia' de la hoja Base De Datos. REGLA: la fuente trae 52 valores distintos con erratas de digitacion; se corrigieron tres confusiones de nombre ('Alocdor' por 'Alocolor', 'Stilo Kids' por 'Estilo Kids', 'Klips 15cc (12col)' por su forma con espacio) y se consolidaron en 63 miembros limpios.",
 "linea_comercial": "Linea comercial del producto. ORIGEN: derivada del nombre. REGLA: se extrae con expresion regular el patron '<Linea> <volumen>cc (<n> col)'.",
 "volumen_cc": "Volumen del envase en centimetros cubicos. ORIGEN: derivada del nombre de la referencia. REGLA: idem.",
 "etiqueta_presentacion": "Presentacion legible, por ejemplo '22 cc, 6 colores'. ORIGEN: construida.",
 "numero_colores": "Numero de colores de la presentacion. ORIGEN: derivada del nombre, y confirmada con la columna '# colores' de la hoja Tablas Desplegables. REGLA: determina cuantas unidades caben en una paca, asi que es imprescindible para comparar produccion entre referencias.",
 "display_por_paca": "Displays que contiene una paca. ORIGEN: columna 'Display' de la hoja Tablas Desplegables.",
 "unidades_por_paca": "Unidades que contiene una paca. ORIGEN: columna 'Unidades * paca' de la hoja Tablas Desplegables. REGLA: es el factor que convierte las pacas del registro en unidades comparables. En la hoja de hechos este dato era inservible: las columnas 7 y 9 estan 100% vacias y la 8 se reutilizo para guardar el turno.",
 "es_no_aplica": "Verdadero en el miembro de relleno. ORIGEN: construida.",
 "tiene_estandar": "Verdadero si existe estandar de ingenieria para la referencia. ORIGEN: construida.",
 "variantes_fuente": "Lista de las variantes de escritura que la fuente usaba para esta referencia. ORIGEN: construida. REGLA: se conserva para poder auditar la consolidacion y demostrar que no se perdio ningun valor.",
},
"dim_tipo_paro_cabecera": {
 "tipo_paro_key": SK,
 "codigo_tipo": "Codigo corto del tipo de paro de cabecera. ORIGEN: construida.",
 "nombre_tipo": "Tipo de paro declarado en la cabecera del registro. ORIGEN: columna 'Tipo de paro' de la hoja Base De Datos. REGLA: la fuente trae 19 variantes de escritura de DOS taxonomias distintas para unos 13 conceptos; se consolidaron en 13 miembros.",
 "grupo_tipo": "Agrupacion de alto nivel del tipo de paro. ORIGEN: construida.",
 "taxonomia_origen": "De cual de las dos taxonomias de la fuente proviene el miembro. ORIGEN: construida. REGLA: documenta la convivencia de taxonomias; permite medir cuanto del historico usa la nomenclatura antigua.",
 "variantes_fuente": "Variantes de escritura consolidadas en este miembro. ORIGEN: construida. REGLA: trazabilidad de la consolidacion.",
},
"dim_turno": {
 "turno_key": SK,
 "codigo_turno": "Codigo corto del turno: T1, T2, T3, TE1, TE2, TE3, NA, DESC. ORIGEN: construida.",
 "nombre_turno": "Nombre del turno con su horario. ORIGEN: columna 'Turno' de la hoja Base De Datos. REGLA: la fuente escribe el turno de varias formas ('6am-2pm', '6am-2pm (Turno 1)', 'Turno 1'); se resuelven todas al mismo miembro.",
 "etiqueta_fuente": "Forma en que la fuente escribe el turno. ORIGEN: idem. REGLA: se conserva para auditar la resolucion de variantes.",
 "hora_inicio": "Hora de inicio del turno. ORIGEN: derivada del nombre.",
 "hora_fin": "Hora de fin del turno. ORIGEN: derivada del nombre.",
 "duracion_horas": "Duracion nominal del turno en horas. ORIGEN: derivada. REGLA: sirve para detectar registros cuyas horas trabajadas exceden la duracion del turno.",
 "tipo_jornada": "'Ordinario', 'Extendido' o 'No aplica'. ORIGEN: construida. REGLA: separa los turnos de 8 horas de las jornadas extendidas, que tienen un patron de paros distinto.",
 "es_nocturno": "Verdadero en el turno de noche. ORIGEN: construida. REGLA: permite comprobar si el turno nocturno rinde distinto, que es una pregunta recurrente de produccion.",
 "orden_presentacion": "Orden cronologico de presentacion. ORIGEN: construida.",
 "es_valido": "Falso en los miembros de relleno 'No aplica' y 'Descanso'. ORIGEN: construida.",
},
"hecho_produccion_turno": {
 "produccion_turno_id": "Llave primaria tecnica de la fila. ORIGEN: construida.",
 "fecha_key": "Llave a dim_fecha. ORIGEN: columna 'Dia' de la hoja Base De Datos. REGLA: se convierte a entero AAAAMMDD.",
 "maquina_key": "Llave a dim_maquina. ORIGEN: columna 'Maquina'.",
 "turno_key": "Llave a dim_turno. ORIGEN: columna 'Turno', con respaldo en la columna 8 ('Unidad por display'), que el formulario reutilizo para guardar el turno. REGLA: si la fuente no trae turno se asigna el miembro de relleno y se marca turno_imputado; ocurre en 2.409 de 5.138 turnos.",
 "operario_key": "Llave a dim_operario. ORIGEN: columna 'Operario'. REGLA: pseudonimizado.",
 "referencia_key": "Llave a dim_referencia. ORIGEN: columna 'Referencia'.",
 "estandar_key": "Llave a la version VIGENTE del estandar en dim_estandar. ORIGEN: construida. REGLA: resolucion en cascada de tres niveles: catalogo exacto del par maquina-referencia; si no existe, estandar de otra linea ajustado por el factor de produccion; si tampoco, 'sin estandar'.",
 "tipo_paro_key": "Llave a dim_tipo_paro_cabecera. ORIGEN: columna 'Tipo de paro'.",
 "consecutivo_registro": "Numero de registro del turno cuando hay varios para la misma fecha, maquina y turno. ORIGEN: construida. REGLA: forma parte del grano; la fuente permite varios registros por turno si cambia la referencia.",
 "fila_origen_excel": FILA,
 "horas_programadas": "Horas que la planta programo para producir en el turno. ORIGEN: columna 'Horas trabajadas'. REGLA: se carga tal cual; es el denominador de la Disponibilidad y la base de toda la conciliacion contra el Excel.",
 "horas_no_programadas": "Horas de calendario sin produccion declaradas por la fuente. ORIGEN: columna 'Horas no trabajadas'. REGLA: ATENCION, NO ES TIEMPO DE PARO. Su suma (41.519,85 h) supera las horas trabajadas y 1.263 filas traen un 24 fijo: es el complemento del dia, no una perdida. Se carga aparte y NO entra al OEE; incluirla seria el error de interpretacion mas facil de cometer con esta fuente.",
 "horas_paro_total": "Horas totales de paro del turno. ORIGEN: reconstruida sumando los 18 pares de columnas de paro. REGLA: NO se copia la columna 'Tiempo de paro' del Excel; se recalcula desde el detalle y despues se CONCILIA contra ella. Coincidir demuestra que el despivote no perdio ni duplico un minuto.",
 "horas_paro_planeado": "Horas de paro de naturaleza planeada. ORIGEN: derivada. REGLA: suma de los paros cuyos codigos son 04, 08, 15, 16, 17 o 18.",
 "horas_paro_no_planeado": "Horas de paro EVITABLE. ORIGEN: derivada. REGLA: horas_paro_total menos horas_paro_planeado. Es la cifra sobre la que la gerencia puede actuar.",
 "horas_operativas": "Horas en que la linea estuvo efectivamente produciendo. ORIGEN: derivada. REGLA: horas_programadas menos horas_paro_total, acotada en cero.",
 "eventos_paro": "Numero de eventos de paro del turno. ORIGEN: derivada. REGLA: conteo de pares de columnas con minutos mayores que cero.",
 "pacas_producidas": "Pacas producidas en el turno. ORIGEN: columna 'Pacas producidas'. REGLA: se carga tal cual; es la unidad en que registra el operario.",
 "unidades_producidas": "Produccion convertida a unidades comparables. ORIGEN: derivada. REGLA: pacas_producidas por unidades_por_paca de la referencia. Sin esta conversion no se pueden comparar referencias de 6 y de 12 colores, ni calcular Rendimiento.",
 "tasa_ideal_unid_min": "Tasa ideal del estandar vigente aplicado. ORIGEN: dim_estandar. REGLA: se copia al hecho para congelar el estandar que regia en ese momento; si el estandar cambia luego, el indicador historico no se altera.",
 "unidades_teoricas": "Unidades que el estandar permitiria en el tiempo PROGRAMADO. ORIGEN: derivada. REGLA: tasa por 60 por horas_programadas. Es la capacidad nominal del turno.",
 "unidades_posibles": "Unidades que el estandar permitiria en el tiempo OPERATIVO. ORIGEN: derivada. REGLA: tasa por 60 por horas_operativas. Es el denominador del Rendimiento: compara contra lo que se pudo hacer con la maquina andando, no con la capacidad nominal, para no contar dos veces la perdida por paro.",
 "unidades_perdidas_paro": "Unidades que se dejaron de producir por los paros. ORIGEN: derivada. REGLA: tasa por 60 por horas_paro_total. Traduce el tiempo perdido al lenguaje del negocio.",
 "disponibilidad": "Primer componente del OEE. ORIGEN: derivada. REGLA: horas_operativas / horas_programadas. REPRODUCE EXACTAMENTE el '% Productividad' que el Excel calcula hoy, verificado a seis decimales contra las tablas dinamicas. Al agregarla se usan TODOS los turnos, porque solo necesita horas; el factor de disponibilidad que entra en el OEE se restringe en cambio a los turnos con estandar, para medir la misma poblacion que el Rendimiento (ver la vista v_oee_mes_maquina, columna disponibilidad_oee).",
 "rendimiento": "Segundo componente del OEE. ORIGEN: derivada. REGLA: unidades_producidas / unidades_posibles. NULL si no hay estandar: nunca se inventa un valor. El Excel no lo calcula.",
 "calidad_proxy": "Tercer componente del OEE, como PROXY declarado. ORIGEN: derivada. REGLA: la fuente NO registra unidades defectuosas, asi que la perdida se estima con el tiempo de reproceso (codigo 11) convertido a unidades. Es una COTA INFERIOR: el OEE real no puede ser mejor que este. Es la principal limitacion del modelo y esta declarada, no disimulada.",
 "oee_ad": "OEE auditable del turno: disponibilidad * rendimiento. ORIGEN: derivada. REGLA: es la version que se reporta, porque sus dos componentes se miden con el dato de la fuente sin estimar nada. NO AGREGAR ESTA COLUMNA: es un ratio no aditivo y existe solo para auditar fila a fila. El OEE de un periodo se recalcula como razon de sumas sobre los turnos con tiene_estandar y sin rendimiento_implausible; promediarla, aunque sea ponderando por horas, da otro numero.",
 "oee_completo": "OEE con los tres componentes, usando el proxy de Calidad. ORIGEN: derivada. REGLA: se publica junto al auditable para que se vea cuanto pesa la parte estimada.",
 "es_registro_completo": "Verdadero si el formato se diligencio completo. ORIGEN: derivada. REGLA: exige operario, referencia y turno informados y estandar disponible.",
 "tiene_estandar": "Verdadero si existe estandar para el par maquina-referencia. ORIGEN: derivada. REGLA: si es falso, el Rendimiento y el OEE quedan en NULL.",
 "paro_excede_programado": "Verdadero si el paro declarado supera las horas trabajadas. ORIGEN: derivada. REGLA: bandera de calidad; 9 turnos lo cumplen, el peor con 15,63 h de paro en un turno de 8 h. Es imposible fisicamente, de modo que uno de los dos datos esta mal.",
 "horas_fuera_de_rango": "Verdadero si las horas trabajadas no son plausibles. ORIGEN: derivada. REGLA: bandera de calidad; una fila declara 32 h en un dia.",
 "turno_imputado": "Verdadero si el turno se asigno porque la fuente no lo traia. ORIGEN: derivada. REGLA: hace visible el dato imputado para que nadie lo confunda con dato real.",
 "operario_no_informado": "Verdadero si la fuente no registro el operario. ORIGEN: derivada.",
 "referencia_no_informada": "Verdadero si la fuente no registro la referencia. ORIGEN: derivada.",
 "rendimiento_implausible": "Verdadero si el rendimiento supera el 150% del maximo teorico. ORIGEN: derivada. REGLA: hallazgo real de la carga: el caso extremo declara un rendimiento del 1.561%, es decir 16 veces el maximo del estandar. No es una linea excepcional, es un dato erroneo. Se CONSERVA el valor para poder auditarlo, pero se excluye del indicador agregado y del indice parcial.",
 "ejecucion_id": AUD_EJ,
 "cargado_en": AUD_CG,
},
"hecho_paro": {
 "paro_id": "Llave primaria tecnica de la fila. ORIGEN: construida.",
 "fecha_key": "Llave a dim_fecha. ORIGEN: columna 'Dia'.",
 "maquina_key": "Llave a dim_maquina. ORIGEN: columna 'Maquina'.",
 "turno_key": "Llave a dim_turno. ORIGEN: columna 'Turno'.",
 "operario_key": "Llave a dim_operario. ORIGEN: columna 'Operario'. REGLA: pseudonimizado.",
 "referencia_key": "Llave a dim_referencia. ORIGEN: columna 'Referencia'.",
 "paro_key": "Llave a dim_paro, es decir la causa del paro con sus cuatro niveles. ORIGEN: posicion del par de columnas mas la columna de subcodigo correspondiente. REGLA: si el subcodigo no viene especificado se asigna el miembro de relleno y se marca subcodigo_imputado.",
 "area_key": "Llave a dim_area_involucrada. ORIGEN: columna 'Area involucrada'.",
 "personal_key": "Llave a dim_personal_mantenimiento. ORIGEN: columna 'Personal de mantenimiento'. REGLA: pseudonimizado.",
 "produccion_turno_id": "Llave al turno de produccion al que pertenece el paro; NULL si no se pudo vincular. ORIGEN: construida. REGLA: 3.028 filas de la fuente son CONTINUACIONES generadas por el boton 'Ingreso subcodigo' y no traen pacas ni horas. Se vinculan a su cabecera en cascada de tres niveles: por fecha, maquina, operario, referencia y turno; luego sin turno; luego solo por fecha y maquina. Quedan 903 filas sin vincular, que suman 1,917 h, el 0,02% del tiempo de paro.",
 "fila_origen_excel": FILA,
 "observacion_paro": "Observacion libre escrita por mantenimiento. ORIGEN: columna 'Observacion del paro'. REGLA: se carga sin modificar; es texto libre y no se usa para clasificar, solo para consultar el caso concreto.",
 "minutos_paro": "Duracion del paro en minutos, tal como la registra la fuente. ORIGEN: columna de minutos del par correspondiente al codigo. REGLA: se conserva el valor original, incluidos los decimales raros (219,6 y 160,5), para no perder trazabilidad.",
 "horas_paro": "Duracion del paro en horas. ORIGEN: derivada. REGLA: minutos / 60, con ocho decimales para que la suma de 16.482 eventos no acumule error de redondeo frente al total que calcula el Excel.",
 "unidades_no_producidas": "Unidades que se dejaron de producir por este paro. ORIGEN: derivada. REGLA: tasa ideal por los minutos del paro.",
 "es_paro_planeado": "Verdadero si el codigo es de naturaleza planeada. ORIGEN: derivada de dim_paro. REGLA: se copia al hecho para que los filtros del tablero no tengan que pasar por la dimension.",
 "proviene_de_continuacion": "Verdadero si la fila venia de una continuacion del boton 'Ingreso subcodigo'. ORIGEN: derivada. REGLA: hace visible el artefacto del formulario de captura.",
 "subcodigo_imputado": "Verdadero si la causa raiz no venia especificada. ORIGEN: derivada. REGLA: solo se evalua en los codigos 01, 03 y 05, los unicos con subcodigos; 107 de 3.691 eventos (2,9%) carecen de causa raiz utilizable.",
 "minutos_atipicos": "Verdadero si la duracion supera las 8 horas. ORIGEN: derivada. REGLA: bandera de calidad; 3 eventos, el mayor de 900 minutos en el codigo 10.",
 "ejecucion_id": AUD_EJ,
 "cargado_en": AUD_CG,
},
"hecho_produccion_hora": {
 "produccion_hora_id": "Llave primaria tecnica. ORIGEN: construida.",
 "instante": "Marca de tiempo del inicio de la hora. ORIGEN: construida por el simulador. REGLA: timestamptz nativo, para que funcionen las macros $__timeFilter y $__timeGroup de Grafana.",
 "fecha_key": "Llave a dim_fecha. ORIGEN: derivada de instante.",
 "hora_del_dia": "Hora del dia, 0 a 23. ORIGEN: derivada de instante.",
 "maquina_key": "Llave a dim_maquina. ORIGEN: construida.",
 "turno_key": "Llave a dim_turno. ORIGEN: derivada de la hora del dia.",
 "referencia_key": "Llave a dim_referencia. ORIGEN: construida. REGLA: el simulador usa la referencia que cada linea corre con mas frecuencia en el historico.",
 "operario_key": "Llave a dim_operario. ORIGEN: construida. REGLA: el simulador usa el miembro 'Sin informar': no inventa personas reales.",
 "paro_key": "Llave a dim_paro; NULL si la hora no tuvo paro. ORIGEN: construida. REGLA: la causa se muestrea de la distribucion REAL de dw.hecho_paro ponderada por horas perdidas, de modo que el Pareto del tablero operativo se parece al historico.",
 "minutos_programados": "Minutos programados de la hora, normalmente 60. ORIGEN: construida.",
 "minutos_paro": "Minutos de paro de la hora. ORIGEN: construida. REGLA: proceso de Poisson calibrado para que la disponibilidad promedio converja a la que la maquina mostro en 2024.",
 "minutos_operativos": "Minutos efectivos de produccion. ORIGEN: derivada.",
 "pacas_producidas": "Pacas producidas en la hora. ORIGEN: derivada.",
 "unidades_producidas": "Unidades producidas en la hora. ORIGEN: construida.",
 "unidades_rechazadas": "Unidades rechazadas en la hora. ORIGEN: construida. REGLA: esta columna NO tiene equivalente en el Excel, porque la fuente no mide defectos. Existe aqui porque un historiador de PLC SI puede medirlo, y con ella el componente Calidad del OEE deja de ser un proxy.",
 "tasa_ideal_unid_min": "Tasa ideal aplicada. ORIGEN: dim_estandar.",
 "unidades_posibles": "Unidades posibles en el tiempo operativo. ORIGEN: derivada.",
 "disponibilidad": "Disponibilidad de la hora. ORIGEN: derivada.",
 "rendimiento": "Rendimiento de la hora. ORIGEN: derivada.",
 "calidad": "Calidad de la hora. ORIGEN: derivada. REGLA: aqui si es Calidad MEDIDA, no proxy, porque existen unidades rechazadas.",
 "oee": "OEE de la hora, con los tres componentes. ORIGEN: derivada.",
 "registrado_en": "Marca de tiempo de la insercion. ORIGEN: construida. REGLA: distinta de instante; permite medir la latencia entre el momento productivo y su registro.",
},
}

TABLAS_DOC = {
 "dim_area_involucrada": "Dimension de areas de la empresa que intervienen en un paro.",
 "dim_estandar": "Dimension de estandares de ingenieria por par maquina-referencia, con historia SCD Tipo 2.",
 "dim_fecha": "Dimension de calendario CONSTRUIDA POR EL EQUIPO. No existe en la fuente.",
 "dim_maquina": "Dimension de las cuatro lineas de envasado.",
 "dim_operario": "Dimension de personal de envasado, PSEUDONIMIZADA.",
 "dim_paro": "Dimension de causas de paro con jerarquia desbalanceada de cuatro niveles.",
 "dim_personal_mantenimiento": "Dimension de personal de mantenimiento, PSEUDONIMIZADA.",
 "dim_referencia": "Dimension de productos envasados, depurada de erratas de digitacion.",
 "dim_tipo_paro_cabecera": "Dimension del tipo de paro declarado en la cabecera del registro.",
 "dim_turno": "Dimension de turnos de trabajo.",
 "hecho_produccion_turno": "Tabla de hechos de produccion por turno.",
 "hecho_paro": "Tabla de hechos de eventos de paro.",
 "hecho_produccion_hora": "Tabla de hechos de telemetria horaria.",
}

L = ["-- " + "=" * 73,
     "--  70_diccionario.sql   El diccionario de datos vive EN LA BASE DE DATOS",
     "-- " + "=" * 73,
     "--",
     "--  Cada columna del esquema dw lleva un comentario con tres partes:",
     "--      <descripcion>.  ORIGEN: <de donde sale>.  REGLA: <transformacion>.",
     "--",
     "--  Por que aqui y no en un documento aparte:",
     "--    * En DBeaver, `\\d+ dw.hecho_produccion_turno` o el panel de",
     "--      propiedades muestran el diccionario sin salir de la herramienta.",
     "--    * Un documento separado envejece en cuanto alguien cambia una",
     "--      columna; un comentario en el DDL se revisa en el mismo diff.",
     "--    * El documento entregable (docs/05-diccionario-de-datos.md) se",
     "--      GENERA desde estos comentarios, asi que no pueden divergir.",
     "--",
     "--  ADVERTENCIA: este script se ejecuta al final del arranque y asume que",
     "--  las tablas ya existen. Se separa del DDL a proposito para que los",
     "--  scripts de estructura se lean sin 190 comentarios intercalados.",
     "-- " + "=" * 73,
     "",
     "\\echo '>> 70: escribiendo el diccionario de datos en los comentarios'",
     ""]

def q(txt):
    return "'" + txt.replace("'", "''") + "'"

total = 0
for tabla, cols in C.items():
    L.append("-- " + "-" * 73)
    L.append(f"--  dw.{tabla}")
    L.append("-- " + "-" * 73)
    if tabla in TABLAS_DOC:
        L.append(f"COMMENT ON TABLE dw.{tabla} IS {q(TABLAS_DOC[tabla])};")
    for col, txt in cols.items():
        L.append(f"COMMENT ON COLUMN dw.{tabla}.{col} IS")
        # parte el texto en lineas de <= 72 caracteres, concatenadas
        import textwrap
        trozos = textwrap.wrap(txt, 68, break_long_words=False)
        for i, t in enumerate(trozos):
            sufijo = ";" if i == len(trozos) - 1 else ""
            sep = "" if i == len(trozos) - 1 else " "
            L.append("  " + q(t + sep) + sufijo)
        total += 1
    L.append("")

L.append("\\echo '>> 70: OK'")
destino = (pathlib.Path(__file__).resolve().parent.parent
           / "sql" / "init" / "70_diccionario.sql")
destino.write_text("\n".join(L) + "\n")
print(f"70_diccionario.sql: {total} columnas comentadas en {len(C)} tablas, "
      f"{len(L)} lineas")
