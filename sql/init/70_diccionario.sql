-- =========================================================================
--  70_diccionario.sql   El diccionario de datos vive EN LA BASE DE DATOS
-- =========================================================================
--
--  Cada columna del esquema dw lleva un comentario con tres partes:
--      <descripcion>.  ORIGEN: <de donde sale>.  REGLA: <transformacion>.
--
--  Por que aqui y no en un documento aparte:
--    * En DBeaver, `\d+ dw.hecho_produccion_turno` o el panel de
--      propiedades muestran el diccionario sin salir de la herramienta.
--    * Un documento separado envejece en cuanto alguien cambia una
--      columna; un comentario en el DDL se revisa en el mismo diff.
--    * El documento entregable (docs/05-diccionario-de-datos.md) se
--      GENERA desde estos comentarios, asi que no pueden divergir.
--
--  ADVERTENCIA: este script se ejecuta al final del arranque y asume que
--  las tablas ya existen. Se separa del DDL a proposito para que los
--  scripts de estructura se lean sin 190 comentarios intercalados.
-- =========================================================================

\echo '>> 70: escribiendo el diccionario de datos en los comentarios'

-- -------------------------------------------------------------------------
--  dw.dim_area_involucrada
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_area_involucrada IS 'Dimension de areas de la empresa que intervienen en un paro.';
COMMENT ON COLUMN dw.dim_area_involucrada.area_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_area_involucrada.codigo_area IS
  'Codigo corto del area. ORIGEN: construida. REGLA: derivado del '
  'nombre, sin tildes ni espacios.';
COMMENT ON COLUMN dw.dim_area_involucrada.nombre_area IS
  'Area de la empresa que atendio el paro. ORIGEN: columna ''Area '
  'involucrada'' de la hoja Base De Datos. REGLA: se normalizo '
  'capitalizacion y se consolidaron variantes de escritura en 7 '
  'miembros.';
COMMENT ON COLUMN dw.dim_area_involucrada.es_area_soporte IS
  'Verdadero si el area es de soporte (mantenimiento, calidad, '
  'laboratorio) y no de produccion. ORIGEN: construida. REGLA: '
  'clasificacion manual del equipo, usada para separar la '
  'responsabilidad del paro.';

-- -------------------------------------------------------------------------
--  dw.dim_estandar
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_estandar IS 'Dimension de estandares de ingenieria por par maquina-referencia, con historia SCD Tipo 2.';
COMMENT ON COLUMN dw.dim_estandar.estandar_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_estandar.maquina_key IS
  'Llave a dim_maquina. ORIGEN: construida. REGLA: el estandar es '
  'especifico del par maquina-referencia, porque la misma referencia '
  'corre a distinta velocidad en cada linea.';
COMMENT ON COLUMN dw.dim_estandar.referencia_key IS
  'Llave a dim_referencia. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_estandar.unidades_por_minuto IS
  'Tasa ideal de produccion: unidades que la linea debe envasar por '
  'minuto. ORIGEN: columna ''unidades *minuto'' del bloque maquina x '
  'referencia de la hoja ''Tablas Desplegables''. REGLA: es el estandar '
  'de ingenieria y el denominador del Rendimiento del OEE. Es el dato '
  'que hacia falta para poder calcular OEE y que estaba en una hoja '
  'auxiliar, no en la hoja de hechos.';
COMMENT ON COLUMN dw.dim_estandar.unidades_por_paca IS
  'Unidades que contiene una paca de esta referencia. ORIGEN: columna '
  '''Unidades * paca'' de la hoja ''Tablas Desplegables''. REGLA: convierte '
  'las pacas que registra el operario en unidades comparables entre '
  'referencias de 6 y de 12 colores.';
COMMENT ON COLUMN dw.dim_estandar.pacas_meta_hora IS
  'Meta de pacas por hora derivada del estandar. ORIGEN: construida. '
  'REGLA: unidades_por_minuto * 60 / unidades_por_paca. Se expresa en '
  'pacas porque es la unidad en que piensa el operario.';
COMMENT ON COLUMN dw.dim_estandar.version IS
  'Numero de version del estandar para el par maquina-referencia. '
  'ORIGEN: construida. REGLA: SCD Tipo 2; empieza en 1 y se incrementa '
  'en cada cambio del estandar.';
COMMENT ON COLUMN dw.dim_estandar.valido_desde IS
  'Fecha desde la que rige esta version del estandar. ORIGEN: '
  'construida. REGLA: SCD Tipo 2.';
COMMENT ON COLUMN dw.dim_estandar.valido_hasta IS
  'Fecha hasta la que rigio esta version; NULL si es la vigente. '
  'ORIGEN: construida. REGLA: SCD Tipo 2.';
COMMENT ON COLUMN dw.dim_estandar.es_vigente IS
  'Verdadero en la version actual del estandar. ORIGEN: construida. '
  'REGLA: SCD Tipo 2; un indice unico parcial garantiza que solo exista '
  'una version vigente por par maquina-referencia.';
COMMENT ON COLUMN dw.dim_estandar.origen_estandar IS
  'Como se obtuvo el estandar: ''Catalogo'' si venia en Tablas '
  'Desplegables, ''Inferido'' si se dedujo de otra linea ajustando por el '
  'factor de produccion, ''Sin estandar'' si no fue posible. ORIGEN: '
  'construida. REGLA: hace explicito el nivel de confianza del dato; '
  'los turnos con ''Sin estandar'' quedan fuera del calculo del '
  'Rendimiento.';
COMMENT ON COLUMN dw.dim_estandar.motivo_cambio IS
  'Razon del cambio de version del estandar. ORIGEN: construida. REGLA: '
  'texto libre para auditar el historial del SCD2.';

-- -------------------------------------------------------------------------
--  dw.dim_fecha
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_fecha IS 'Dimension de calendario CONSTRUIDA POR EL EQUIPO. No existe en la fuente.';
COMMENT ON COLUMN dw.dim_fecha.fecha_key IS
  'Llave surrogada con formato AAAAMMDD, legible a simple vista. '
  'ORIGEN: construida. REGLA: entero en lugar de fecha para que los '
  'indices y los JOIN sean mas compactos, y para poder leer la llave '
  'sin consultar la dimension.';
COMMENT ON COLUMN dw.dim_fecha.fecha IS
  'Fecha del calendario. ORIGEN: construida. REGLA: columna marcada '
  'como fecha del modelo en Power BI; es la que usan las funciones de '
  'inteligencia de tiempo de DAX.';
COMMENT ON COLUMN dw.dim_fecha.anio IS
  'Ano del calendario. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.trimestre IS
  'Numero de trimestre, 1 a 4. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.nombre_trimestre IS
  'Trimestre como texto, por ejemplo ''T1''. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.mes IS
  'Numero de mes, 1 a 12. ORIGEN: construida. REGLA: ordena a '
  'nombre_mes, para que los meses no salgan en orden alfabetico.';
COMMENT ON COLUMN dw.dim_fecha.nombre_mes IS
  'Nombre del mes en espanol. ORIGEN: construida. REGLA: generado en el '
  'ETL y no con to_char, para no depender de la configuracion regional '
  'del servidor.';
COMMENT ON COLUMN dw.dim_fecha.nombre_mes_corto IS
  'Abreviatura del mes, por ejemplo ''ene''. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.anio_mes IS
  'Periodo como entero AAAAMM. ORIGEN: construida. REGLA: sirve para '
  'ordenar y para las funciones de ventana que comparan periodos.';
COMMENT ON COLUMN dw.dim_fecha.etiqueta_anio_mes IS
  'Periodo legible, por ejemplo ''2024-03''. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.dia IS
  'Dia del mes. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.dia_del_anio IS
  'Dia del ano, 1 a 366. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.dia_semana_iso IS
  'Dia de la semana ISO: 1 lunes a 7 domingo. ORIGEN: construida. '
  'REGLA: se usa el estandar ISO y no el de PostgreSQL (0 domingo) para '
  'que la semana empiece en lunes, como en la planta.';
COMMENT ON COLUMN dw.dim_fecha.nombre_dia IS
  'Nombre del dia de la semana en espanol. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.nombre_dia_corto IS
  'Abreviatura del dia. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.semana_iso IS
  'Numero de semana ISO. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.anio_semana_iso IS
  'Ano de la semana ISO. ORIGEN: construida. REGLA: puede diferir de '
  'anio en la primera y la ultima semana del ano; se guarda aparte para '
  'no partir semanas al agregar.';
COMMENT ON COLUMN dw.dim_fecha.es_fin_semana IS
  'Verdadero en sabado y domingo. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.es_festivo IS
  'Verdadero si es festivo en Colombia. ORIGEN: construida. REGLA: '
  'festivos fijos, mas los calculados desde el Domingo de Pascua con el '
  'algoritmo de Butcher, mas los trasladables al lunes siguiente segun '
  'la Ley 51 de 1983 (Ley Emiliani).';
COMMENT ON COLUMN dw.dim_fecha.nombre_festivo IS
  'Nombre del festivo; NULL si no es festivo. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_fecha.es_dia_habil IS
  'Verdadero si no es fin de semana ni festivo. ORIGEN: construida. '
  'REGLA: permite separar la produccion de dia habil de la de festivo, '
  'que tiene costo de mano de obra distinto.';
COMMENT ON COLUMN dw.dim_fecha.fecha_key_anio_ant IS
  'fecha_key del mismo dia del ano anterior. ORIGEN: construida. REGLA: '
  'precalculada para que los comparativos interanuales en SQL sean un '
  'JOIN y no un calculo de fechas en cada consulta.';
COMMENT ON COLUMN dw.dim_fecha.anio_mes_anio_ant IS
  'anio_mes del mismo mes del ano anterior. ORIGEN: construida. REGLA: '
  'igual que la anterior, para comparativos mensuales.';

-- -------------------------------------------------------------------------
--  dw.dim_maquina
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_maquina IS 'Dimension de las cuatro lineas de envasado.';
COMMENT ON COLUMN dw.dim_maquina.maquina_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_maquina.codigo_maquina IS
  'Codigo de la linea tal como lo escribe la fuente: Vinilos_1 a '
  'Vinilos_4. ORIGEN: columna ''Maquina'' de la hoja Base De Datos. '
  'REGLA: se conserva el codigo original para poder conciliar contra el '
  'Excel.';
COMMENT ON COLUMN dw.dim_maquina.nombre_maquina IS
  'Nombre legible de la linea. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_maquina.numero_linea IS
  'Numero de linea, 1 a 4. ORIGEN: construida. REGLA: extraido del '
  'codigo; ordena la presentacion.';
COMMENT ON COLUMN dw.dim_maquina.planta IS
  'Planta donde esta la linea. ORIGEN: construida. REGLA: valor unico '
  'por ahora; la columna existe para que el modelo admita una segunda '
  'planta sin rediseno.';
COMMENT ON COLUMN dw.dim_maquina.familia_producto IS
  'Familia de producto que envasa la linea. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_maquina.factor_produccion IS
  'Multiplicador de capacidad de la linea respecto de la de referencia: '
  'V1 1,100, V2 1,160, V3 y V4 1,000. ORIGEN: estaba ESCONDIDO dentro '
  'de una formula de texto de la hoja ''Tiempos'', no en ninguna celda de '
  'datos. REGLA: se extrajo leyendo la formula; permite inferir el '
  'estandar de una linea a partir del de otra cuando el catalogo no '
  'trae el par maquina-referencia.';
COMMENT ON COLUMN dw.dim_maquina.grupo_capacidad IS
  'Agrupacion por capacidad relativa. ORIGEN: construida. REGLA: '
  'derivada del factor de produccion; agrupa lineas comparables entre '
  'si.';
COMMENT ON COLUMN dw.dim_maquina.es_activa IS
  'Verdadero si la linea esta en operacion. ORIGEN: construida.';

-- -------------------------------------------------------------------------
--  dw.dim_operario
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_operario IS 'Dimension de personal de envasado, PSEUDONIMIZADA.';
COMMENT ON COLUMN dw.dim_operario.operario_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_operario.codigo_operario IS
  'Codigo pseudonimo estable, formato OPER-NNN. ORIGEN: construida. '
  'REGLA: se asigna por orden de aparicion; es estable entre '
  'ejecuciones del ETL.';
COMMENT ON COLUMN dw.dim_operario.alias_operario IS
  'Alias que se muestra en los tableros, formato ''Operario NNN''. '
  'ORIGEN: construida. REGLA: PSEUDONIMIZACION. Es el unico '
  'identificador que sale del esquema dw; el nombre real nunca llega a '
  'los tableros.';
COMMENT ON COLUMN dw.dim_operario.rol IS
  'Rol del trabajador. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_operario.es_identificado IS
  'Falso en el miembro ''Sin informar''. ORIGEN: construida. REGLA: la '
  'fuente trae ''No'' y ''No aplica'' como marcadores de ausencia; se '
  'consolidan en un unico miembro de relleno con llave 0.';
COMMENT ON COLUMN dw.dim_operario.primera_aparicion IS
  'Primera fecha en que aparece el operario. ORIGEN: derivada de la '
  'hoja Base De Datos. REGLA: min(fecha) de sus registros.';
COMMENT ON COLUMN dw.dim_operario.ultima_aparicion IS
  'Ultima fecha en que aparece. ORIGEN: derivada. REGLA: max(fecha) de '
  'sus registros.';
COMMENT ON COLUMN dw.dim_operario.turnos_registrados IS
  'Numero de turnos en que aparece. ORIGEN: derivada. REGLA: conteo de '
  'registros; sirve para distinguir al personal de planta del eventual.';

-- -------------------------------------------------------------------------
--  dw.dim_paro
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_paro IS 'Dimension de causas de paro con jerarquia desbalanceada de cuatro niveles.';
COMMENT ON COLUMN dw.dim_paro.paro_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_paro.area_impacto IS
  'NIVEL 1 de la jerarquia de paros: area responsable de la causa. '
  'ORIGEN: construida. REGLA: clasificacion de los 18 codigos de paro '
  'segun quien debe actuar (Mantenimiento, Produccion, Calidad, '
  'Logistica, Servicios generales).';
COMMENT ON COLUMN dw.dim_paro.codigo_paro IS
  'Codigo de paro de dos digitos, ''01'' a ''18''. ORIGEN: cabecera de los '
  '18 pares de columnas de la hoja Base De Datos. REGLA: el codigo se '
  'deduce de la POSICION de la columna, no de su texto, porque los '
  'encabezados tienen variantes de escritura.';
COMMENT ON COLUMN dw.dim_paro.codigo_paro_numero IS
  'El codigo como entero, para ordenar. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_paro.nombre_codigo_paro IS
  'Descripcion del codigo segun el procedimiento P-MTO-22. ORIGEN: '
  'documento P-MTO-22 V1, vigente desde el 14/05/2025. REGLA: se toma '
  'la descripcion oficial del procedimiento, no la del encabezado del '
  'Excel, que esta abreviada.';
COMMENT ON COLUMN dw.dim_paro.etiqueta_codigo_paro IS
  'NIVEL 2 de la jerarquia: codigo y descripcion juntos, por ejemplo '
  '''[05] Ajuste operativo''. ORIGEN: construida. REGLA: es la etiqueta '
  'que se muestra en los tableros; incluir el numero permite cruzarla '
  'con el formato en papel que usa la planta.';
COMMENT ON COLUMN dw.dim_paro.naturaleza_paro IS
  '''Planeado'' o ''No planeado''. ORIGEN: construida. REGLA: se clasifican '
  'como planeados los codigos 04, 08, 15, 16, 17 y 18 (mantenimiento '
  'preventivo, capacitacion, cambio de insumos, aseo, pausa activa y '
  'afines). Es la separacion que distingue el tiempo perdido EVITABLE '
  'del que es parte normal de la operacion, y sin ella el OEE castiga a '
  'la planta por hacer lo correcto.';
COMMENT ON COLUMN dw.dim_paro.es_imputable_mantenimiento IS
  'Verdadero si el paro es responsabilidad del area de mantenimiento. '
  'ORIGEN: construida. REGLA: permite medir el desempeno de '
  'mantenimiento sin cargarle los paros de produccion o de logistica.';
COMMENT ON COLUMN dw.dim_paro.codigo_sistema IS
  'Codigo del sistema fisico de la maquina. ORIGEN: construida. REGLA: '
  'ATRIBUTO CONFORMADO, lo mas importante de esta dimension. Se deduce '
  'del prefijo numerico del subcodigo y unifica las ramas 1.x (falla '
  'electromecanica), 3.x (servicios) y 5.x (ajuste operativo) en el '
  'sistema al que todas se refieren.';
COMMENT ON COLUMN dw.dim_paro.nombre_sistema IS
  'NIVEL 3 de la jerarquia: nombre del sistema fisico, por ejemplo '
  '''Sistema de dosificacion de pintura''. ORIGEN: construida. REGLA: el '
  'Excel NO puede responder ''que sistema me cuesta mas tiempo'' porque '
  'las tres ramas viven en columnas separadas. Al unificarlas se '
  'descubrio que el sistema dosificador explica el 44,6% del tiempo '
  'perdido de los codigos 01/03/05 (992 de 2.222,8 h), el 11,8% del '
  'tiempo perdido total.';
COMMENT ON COLUMN dw.dim_paro.codigo_subcodigo IS
  'Codigo del subcodigo de causa raiz. ORIGEN: columnas ''Subcodigo N'' '
  'de la hoja Base De Datos y hoja oculta ''Base de datos de Sub '
  'codigos''. REGLA: la fuente tiene DOS taxonomias conviviendo; la rama '
  '4.x historica se mapea a la 5.x vigente (4.1 a 5.1, 4.2 a 5.2, 4.3 a '
  '5.3, 4.4 a 5.5, 4.5 a 5.6, 4.6 a 5.7, 4.7 a 5.8, 4.8 a 5.9) y se '
  'corrige la errata del propio catalogo (1.4.3 debia ser 1.4.C).';
COMMENT ON COLUMN dw.dim_paro.nombre_subcodigo IS
  'NIVEL 4 de la jerarquia: causa raiz concreta. ORIGEN: idem. REGLA: '
  'la fuente trae 45 variantes de escritura para unos 25 subcodigos del '
  'codigo 01; se resuelven confiando en el PREFIJO NUMERICO y no en el '
  'texto, que es el dato fiable.';
COMMENT ON COLUMN dw.dim_paro.nivel_detalle IS
  'Profundidad real del miembro en la jerarquia, 2 a 4. ORIGEN: '
  'construida. REGLA: la jerarquia es DESBALANCEADA (ragged): solo los '
  'codigos 01, 03 y 05 tienen subcodigos. Esta columna dice hasta donde '
  'se puede bajar en cada rama.';
COMMENT ON COLUMN dw.dim_paro.admite_subcodigo IS
  'Verdadero en los codigos 01, 03 y 05. ORIGEN: construida. REGLA: '
  'evita medir como ''dato incompleto'' la ausencia de subcodigo en los '
  '15 codigos que no lo tienen; sin esta distincion el indicador de '
  'completitud daria un 78% de falsos positivos.';
COMMENT ON COLUMN dw.dim_paro.es_subcodigo_especificado IS
  'Falso en los miembros de relleno ''N/A'' y ''SIN-ESP''. ORIGEN: '
  'construida. REGLA: la jerarquia desbalanceada se resuelve con '
  'miembros de relleno EXPLICITOS en lugar de NULL, de modo que el '
  'drill-down del tablero nunca aterriza en un hueco.';
COMMENT ON COLUMN dw.dim_paro.orden_presentacion IS
  'Orden de presentacion del miembro. ORIGEN: construida.';

-- -------------------------------------------------------------------------
--  dw.dim_personal_mantenimiento
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_personal_mantenimiento IS 'Dimension de personal de mantenimiento, PSEUDONIMIZADA.';
COMMENT ON COLUMN dw.dim_personal_mantenimiento.personal_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_personal_mantenimiento.codigo_personal IS
  'Codigo pseudonimo estable, formato TEC-NNN. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_personal_mantenimiento.alias_personal IS
  'Alias mostrado en los tableros, formato ''Tecnico NNN''. ORIGEN: '
  'construida. REGLA: PSEUDONIMIZACION, igual que en dim_operario.';
COMMENT ON COLUMN dw.dim_personal_mantenimiento.area IS
  'Area del tecnico. ORIGEN: derivada de la fuente. REGLA: normalizada.';
COMMENT ON COLUMN dw.dim_personal_mantenimiento.es_identificado IS
  'Falso en el miembro ''Sin informar''. ORIGEN: construida.';

-- -------------------------------------------------------------------------
--  dw.dim_referencia
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_referencia IS 'Dimension de productos envasados, depurada de erratas de digitacion.';
COMMENT ON COLUMN dw.dim_referencia.referencia_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_referencia.codigo_referencia IS
  'Codigo normalizado de la referencia. ORIGEN: construida. REGLA: '
  'nombre sin tildes, en mayusculas y sin espacios; es la clave con que '
  'se consolidan las variantes de escritura.';
COMMENT ON COLUMN dw.dim_referencia.nombre_referencia IS
  'Nombre de la referencia, depurado. ORIGEN: columna ''Referencia'' de '
  'la hoja Base De Datos. REGLA: la fuente trae 52 valores distintos '
  'con erratas de digitacion; se corrigieron tres confusiones de nombre '
  '(''Alocdor'' por ''Alocolor'', ''Stilo Kids'' por ''Estilo Kids'', ''Klips '
  '15cc (12col)'' por su forma con espacio) y se consolidaron en 63 '
  'miembros limpios.';
COMMENT ON COLUMN dw.dim_referencia.linea_comercial IS
  'Linea comercial del producto. ORIGEN: derivada del nombre. REGLA: se '
  'extrae con expresion regular el patron ''<Linea> <volumen>cc (<n> '
  'col)''.';
COMMENT ON COLUMN dw.dim_referencia.volumen_cc IS
  'Volumen del envase en centimetros cubicos. ORIGEN: derivada del '
  'nombre de la referencia. REGLA: idem.';
COMMENT ON COLUMN dw.dim_referencia.etiqueta_presentacion IS
  'Presentacion legible, por ejemplo ''22 cc, 6 colores''. ORIGEN: '
  'construida.';
COMMENT ON COLUMN dw.dim_referencia.numero_colores IS
  'Numero de colores de la presentacion. ORIGEN: derivada del nombre, y '
  'confirmada con la columna ''# colores'' de la hoja Tablas '
  'Desplegables. REGLA: determina cuantas unidades caben en una paca, '
  'asi que es imprescindible para comparar produccion entre '
  'referencias.';
COMMENT ON COLUMN dw.dim_referencia.display_por_paca IS
  'Displays que contiene una paca. ORIGEN: columna ''Display'' de la hoja '
  'Tablas Desplegables.';
COMMENT ON COLUMN dw.dim_referencia.unidades_por_paca IS
  'Unidades que contiene una paca. ORIGEN: columna ''Unidades * paca'' de '
  'la hoja Tablas Desplegables. REGLA: es el factor que convierte las '
  'pacas del registro en unidades comparables. En la hoja de hechos '
  'este dato era inservible: las columnas 7 y 9 estan 100% vacias y la '
  '8 se reutilizo para guardar el turno.';
COMMENT ON COLUMN dw.dim_referencia.es_no_aplica IS
  'Verdadero en el miembro de relleno. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_referencia.tiene_estandar IS
  'Verdadero si existe estandar de ingenieria para la referencia. '
  'ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_referencia.variantes_fuente IS
  'Lista de las variantes de escritura que la fuente usaba para esta '
  'referencia. ORIGEN: construida. REGLA: se conserva para poder '
  'auditar la consolidacion y demostrar que no se perdio ningun valor.';

-- -------------------------------------------------------------------------
--  dw.dim_tipo_paro_cabecera
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_tipo_paro_cabecera IS 'Dimension del tipo de paro declarado en la cabecera del registro.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.tipo_paro_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.codigo_tipo IS
  'Codigo corto del tipo de paro de cabecera. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.nombre_tipo IS
  'Tipo de paro declarado en la cabecera del registro. ORIGEN: columna '
  '''Tipo de paro'' de la hoja Base De Datos. REGLA: la fuente trae 19 '
  'variantes de escritura de DOS taxonomias distintas para unos 13 '
  'conceptos; se consolidaron en 13 miembros.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.grupo_tipo IS
  'Agrupacion de alto nivel del tipo de paro. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.taxonomia_origen IS
  'De cual de las dos taxonomias de la fuente proviene el miembro. '
  'ORIGEN: construida. REGLA: documenta la convivencia de taxonomias; '
  'permite medir cuanto del historico usa la nomenclatura antigua.';
COMMENT ON COLUMN dw.dim_tipo_paro_cabecera.variantes_fuente IS
  'Variantes de escritura consolidadas en este miembro. ORIGEN: '
  'construida. REGLA: trazabilidad de la consolidacion.';

-- -------------------------------------------------------------------------
--  dw.dim_turno
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.dim_turno IS 'Dimension de turnos de trabajo.';
COMMENT ON COLUMN dw.dim_turno.turno_key IS
  'Llave surrogada entera, generada por el ETL. ORIGEN: construida. '
  'REGLA: numeracion secuencial; el valor 0 se reserva al miembro ''no '
  'informado'' para no usar NULL en las tablas de hechos.';
COMMENT ON COLUMN dw.dim_turno.codigo_turno IS
  'Codigo corto del turno: T1, T2, T3, TE1, TE2, TE3, NA, DESC. ORIGEN: '
  'construida.';
COMMENT ON COLUMN dw.dim_turno.nombre_turno IS
  'Nombre del turno con su horario. ORIGEN: columna ''Turno'' de la hoja '
  'Base De Datos. REGLA: la fuente escribe el turno de varias formas '
  '(''6am-2pm'', ''6am-2pm (Turno 1)'', ''Turno 1''); se resuelven todas al '
  'mismo miembro.';
COMMENT ON COLUMN dw.dim_turno.etiqueta_fuente IS
  'Forma en que la fuente escribe el turno. ORIGEN: idem. REGLA: se '
  'conserva para auditar la resolucion de variantes.';
COMMENT ON COLUMN dw.dim_turno.hora_inicio IS
  'Hora de inicio del turno. ORIGEN: derivada del nombre.';
COMMENT ON COLUMN dw.dim_turno.hora_fin IS
  'Hora de fin del turno. ORIGEN: derivada del nombre.';
COMMENT ON COLUMN dw.dim_turno.duracion_horas IS
  'Duracion nominal del turno en horas. ORIGEN: derivada. REGLA: sirve '
  'para detectar registros cuyas horas trabajadas exceden la duracion '
  'del turno.';
COMMENT ON COLUMN dw.dim_turno.tipo_jornada IS
  '''Ordinario'', ''Extendido'' o ''No aplica''. ORIGEN: construida. REGLA: '
  'separa los turnos de 8 horas de las jornadas extendidas, que tienen '
  'un patron de paros distinto.';
COMMENT ON COLUMN dw.dim_turno.es_nocturno IS
  'Verdadero en el turno de noche. ORIGEN: construida. REGLA: permite '
  'comprobar si el turno nocturno rinde distinto, que es una pregunta '
  'recurrente de produccion.';
COMMENT ON COLUMN dw.dim_turno.orden_presentacion IS
  'Orden cronologico de presentacion. ORIGEN: construida.';
COMMENT ON COLUMN dw.dim_turno.es_valido IS
  'Falso en los miembros de relleno ''No aplica'' y ''Descanso''. ORIGEN: '
  'construida.';

-- -------------------------------------------------------------------------
--  dw.hecho_produccion_turno
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.hecho_produccion_turno IS 'Tabla de hechos de produccion por turno.';
COMMENT ON COLUMN dw.hecho_produccion_turno.produccion_turno_id IS
  'Llave primaria tecnica de la fila. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_produccion_turno.fecha_key IS
  'Llave a dim_fecha. ORIGEN: columna ''Dia'' de la hoja Base De Datos. '
  'REGLA: se convierte a entero AAAAMMDD.';
COMMENT ON COLUMN dw.hecho_produccion_turno.maquina_key IS
  'Llave a dim_maquina. ORIGEN: columna ''Maquina''.';
COMMENT ON COLUMN dw.hecho_produccion_turno.turno_key IS
  'Llave a dim_turno. ORIGEN: columna ''Turno'', con respaldo en la '
  'columna 8 (''Unidad por display''), que el formulario reutilizo para '
  'guardar el turno. REGLA: si la fuente no trae turno se asigna el '
  'miembro de relleno y se marca turno_imputado; ocurre en 2.409 de '
  '5.138 turnos.';
COMMENT ON COLUMN dw.hecho_produccion_turno.operario_key IS
  'Llave a dim_operario. ORIGEN: columna ''Operario''. REGLA: '
  'pseudonimizado.';
COMMENT ON COLUMN dw.hecho_produccion_turno.referencia_key IS
  'Llave a dim_referencia. ORIGEN: columna ''Referencia''.';
COMMENT ON COLUMN dw.hecho_produccion_turno.estandar_key IS
  'Llave a la version VIGENTE del estandar en dim_estandar. ORIGEN: '
  'construida. REGLA: resolucion en cascada de tres niveles: catalogo '
  'exacto del par maquina-referencia; si no existe, estandar de otra '
  'linea ajustado por el factor de produccion; si tampoco, ''sin '
  'estandar''.';
COMMENT ON COLUMN dw.hecho_produccion_turno.tipo_paro_key IS
  'Llave a dim_tipo_paro_cabecera. ORIGEN: columna ''Tipo de paro''.';
COMMENT ON COLUMN dw.hecho_produccion_turno.consecutivo_registro IS
  'Numero de registro del turno cuando hay varios para la misma fecha, '
  'maquina y turno. ORIGEN: construida. REGLA: forma parte del grano; '
  'la fuente permite varios registros por turno si cambia la '
  'referencia.';
COMMENT ON COLUMN dw.hecho_produccion_turno.fila_origen_excel IS
  'Numero de fila en la hoja ''Base De Datos'' del Excel (la fila 10 es '
  'la primera con datos). ORIGEN: construida. REGLA: trazabilidad: '
  'permite volver a la celda exacta del Excel ante cualquier duda.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_programadas IS
  'Horas que la planta programo para producir en el turno. ORIGEN: '
  'columna ''Horas trabajadas''. REGLA: se carga tal cual; es el '
  'denominador de la Disponibilidad y la base de toda la conciliacion '
  'contra el Excel.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_no_programadas IS
  'Horas de calendario sin produccion declaradas por la fuente. ORIGEN: '
  'columna ''Horas no trabajadas''. REGLA: ATENCION, NO ES TIEMPO DE '
  'PARO. Su suma (41.519,85 h) supera las horas trabajadas y 1.263 '
  'filas traen un 24 fijo: es el complemento del dia, no una perdida. '
  'Se carga aparte y NO entra al OEE; incluirla seria el error de '
  'interpretacion mas facil de cometer con esta fuente.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_paro_total IS
  'Horas totales de paro del turno. ORIGEN: reconstruida sumando los 18 '
  'pares de columnas de paro. REGLA: NO se copia la columna ''Tiempo de '
  'paro'' del Excel; se recalcula desde el detalle y despues se CONCILIA '
  'contra ella. Coincidir demuestra que el despivote no perdio ni '
  'duplico un minuto.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_paro_planeado IS
  'Horas de paro de naturaleza planeada. ORIGEN: derivada. REGLA: suma '
  'de los paros cuyos codigos son 04, 08, 15, 16, 17 o 18.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_paro_no_planeado IS
  'Horas de paro EVITABLE. ORIGEN: derivada. REGLA: horas_paro_total '
  'menos horas_paro_planeado. Es la cifra sobre la que la gerencia '
  'puede actuar.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_operativas IS
  'Horas en que la linea estuvo efectivamente produciendo. ORIGEN: '
  'derivada. REGLA: horas_programadas menos horas_paro_total, acotada '
  'en cero.';
COMMENT ON COLUMN dw.hecho_produccion_turno.eventos_paro IS
  'Numero de eventos de paro del turno. ORIGEN: derivada. REGLA: conteo '
  'de pares de columnas con minutos mayores que cero.';
COMMENT ON COLUMN dw.hecho_produccion_turno.pacas_producidas IS
  'Pacas producidas en el turno. ORIGEN: columna ''Pacas producidas''. '
  'REGLA: se carga tal cual; es la unidad en que registra el operario.';
COMMENT ON COLUMN dw.hecho_produccion_turno.unidades_producidas IS
  'Produccion convertida a unidades comparables. ORIGEN: derivada. '
  'REGLA: pacas_producidas por unidades_por_paca de la referencia. Sin '
  'esta conversion no se pueden comparar referencias de 6 y de 12 '
  'colores, ni calcular Rendimiento.';
COMMENT ON COLUMN dw.hecho_produccion_turno.tasa_ideal_unid_min IS
  'Tasa ideal del estandar vigente aplicado. ORIGEN: dim_estandar. '
  'REGLA: se copia al hecho para congelar el estandar que regia en ese '
  'momento; si el estandar cambia luego, el indicador historico no se '
  'altera.';
COMMENT ON COLUMN dw.hecho_produccion_turno.unidades_teoricas IS
  'Unidades que el estandar permitiria en el tiempo PROGRAMADO. ORIGEN: '
  'derivada. REGLA: tasa por 60 por horas_programadas. Es la capacidad '
  'nominal del turno.';
COMMENT ON COLUMN dw.hecho_produccion_turno.unidades_posibles IS
  'Unidades que el estandar permitiria en el tiempo OPERATIVO. ORIGEN: '
  'derivada. REGLA: tasa por 60 por horas_operativas. Es el denominador '
  'del Rendimiento: compara contra lo que se pudo hacer con la maquina '
  'andando, no con la capacidad nominal, para no contar dos veces la '
  'perdida por paro.';
COMMENT ON COLUMN dw.hecho_produccion_turno.unidades_perdidas_paro IS
  'Unidades que se dejaron de producir por los paros. ORIGEN: derivada. '
  'REGLA: tasa por 60 por horas_paro_total. Traduce el tiempo perdido '
  'al lenguaje del negocio.';
COMMENT ON COLUMN dw.hecho_produccion_turno.disponibilidad IS
  'Primer componente del OEE. ORIGEN: derivada. REGLA: horas_operativas '
  '/ horas_programadas. REPRODUCE EXACTAMENTE el ''% Productividad'' que '
  'el Excel calcula hoy, verificado a seis decimales contra las tablas '
  'dinamicas. Al agregarla se usan TODOS los turnos, porque solo '
  'necesita horas; el factor de disponibilidad que entra en el OEE se '
  'restringe en cambio a los turnos con estandar, para medir la misma '
  'poblacion que el Rendimiento (ver la vista v_oee_mes_maquina, '
  'columna disponibilidad_oee).';
COMMENT ON COLUMN dw.hecho_produccion_turno.rendimiento IS
  'Segundo componente del OEE. ORIGEN: derivada. REGLA: '
  'unidades_producidas / unidades_posibles. NULL si no hay estandar: '
  'nunca se inventa un valor. El Excel no lo calcula.';
COMMENT ON COLUMN dw.hecho_produccion_turno.calidad_proxy IS
  'Tercer componente del OEE, como PROXY declarado. ORIGEN: derivada. '
  'REGLA: la fuente NO registra unidades defectuosas, asi que la '
  'perdida se estima con el tiempo de reproceso (codigo 11) convertido '
  'a unidades. Es una COTA INFERIOR: el OEE real no puede ser mejor que '
  'este. Es la principal limitacion del modelo y esta declarada, no '
  'disimulada.';
COMMENT ON COLUMN dw.hecho_produccion_turno.oee_ad IS
  'OEE auditable del turno: disponibilidad * rendimiento. ORIGEN: '
  'derivada. REGLA: es la version que se reporta, porque sus dos '
  'componentes se miden con el dato de la fuente sin estimar nada. NO '
  'AGREGAR ESTA COLUMNA: es un ratio no aditivo y existe solo para '
  'auditar fila a fila. El OEE de un periodo se recalcula como razon de '
  'sumas sobre los turnos con tiene_estandar y sin '
  'rendimiento_implausible; promediarla, aunque sea ponderando por '
  'horas, da otro numero.';
COMMENT ON COLUMN dw.hecho_produccion_turno.oee_completo IS
  'OEE con los tres componentes, usando el proxy de Calidad. ORIGEN: '
  'derivada. REGLA: se publica junto al auditable para que se vea '
  'cuanto pesa la parte estimada.';
COMMENT ON COLUMN dw.hecho_produccion_turno.es_registro_completo IS
  'Verdadero si el formato se diligencio completo. ORIGEN: derivada. '
  'REGLA: exige operario, referencia y turno informados y estandar '
  'disponible.';
COMMENT ON COLUMN dw.hecho_produccion_turno.tiene_estandar IS
  'Verdadero si existe estandar para el par maquina-referencia. ORIGEN: '
  'derivada. REGLA: si es falso, el Rendimiento y el OEE quedan en '
  'NULL.';
COMMENT ON COLUMN dw.hecho_produccion_turno.paro_excede_programado IS
  'Verdadero si el paro declarado supera las horas trabajadas. ORIGEN: '
  'derivada. REGLA: bandera de calidad; 9 turnos lo cumplen, el peor '
  'con 15,63 h de paro en un turno de 8 h. Es imposible fisicamente, de '
  'modo que uno de los dos datos esta mal.';
COMMENT ON COLUMN dw.hecho_produccion_turno.horas_fuera_de_rango IS
  'Verdadero si las horas trabajadas no son plausibles. ORIGEN: '
  'derivada. REGLA: bandera de calidad; una fila declara 32 h en un '
  'dia.';
COMMENT ON COLUMN dw.hecho_produccion_turno.turno_imputado IS
  'Verdadero si el turno se asigno porque la fuente no lo traia. '
  'ORIGEN: derivada. REGLA: hace visible el dato imputado para que '
  'nadie lo confunda con dato real.';
COMMENT ON COLUMN dw.hecho_produccion_turno.operario_no_informado IS
  'Verdadero si la fuente no registro el operario. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_turno.referencia_no_informada IS
  'Verdadero si la fuente no registro la referencia. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_turno.rendimiento_implausible IS
  'Verdadero si el rendimiento supera el 150% del maximo teorico. '
  'ORIGEN: derivada. REGLA: hallazgo real de la carga: el caso extremo '
  'declara un rendimiento del 1.561%, es decir 16 veces el maximo del '
  'estandar. No es una linea excepcional, es un dato erroneo. Se '
  'CONSERVA el valor para poder auditarlo, pero se excluye del '
  'indicador agregado y del indice parcial.';
COMMENT ON COLUMN dw.hecho_produccion_turno.ejecucion_id IS
  'Identificador de la ejecucion del ETL que cargo la fila. ORIGEN: '
  'construida. REGLA: permite auditar y revertir una carga concreta.';
COMMENT ON COLUMN dw.hecho_produccion_turno.cargado_en IS
  'Marca de tiempo de la carga. ORIGEN: construida. REGLA: default '
  'now().';

-- -------------------------------------------------------------------------
--  dw.hecho_paro
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.hecho_paro IS 'Tabla de hechos de eventos de paro.';
COMMENT ON COLUMN dw.hecho_paro.paro_id IS
  'Llave primaria tecnica de la fila. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_paro.fecha_key IS
  'Llave a dim_fecha. ORIGEN: columna ''Dia''.';
COMMENT ON COLUMN dw.hecho_paro.maquina_key IS
  'Llave a dim_maquina. ORIGEN: columna ''Maquina''.';
COMMENT ON COLUMN dw.hecho_paro.turno_key IS
  'Llave a dim_turno. ORIGEN: columna ''Turno''.';
COMMENT ON COLUMN dw.hecho_paro.operario_key IS
  'Llave a dim_operario. ORIGEN: columna ''Operario''. REGLA: '
  'pseudonimizado.';
COMMENT ON COLUMN dw.hecho_paro.referencia_key IS
  'Llave a dim_referencia. ORIGEN: columna ''Referencia''.';
COMMENT ON COLUMN dw.hecho_paro.paro_key IS
  'Llave a dim_paro, es decir la causa del paro con sus cuatro niveles. '
  'ORIGEN: posicion del par de columnas mas la columna de subcodigo '
  'correspondiente. REGLA: si el subcodigo no viene especificado se '
  'asigna el miembro de relleno y se marca subcodigo_imputado.';
COMMENT ON COLUMN dw.hecho_paro.area_key IS
  'Llave a dim_area_involucrada. ORIGEN: columna ''Area involucrada''.';
COMMENT ON COLUMN dw.hecho_paro.personal_key IS
  'Llave a dim_personal_mantenimiento. ORIGEN: columna ''Personal de '
  'mantenimiento''. REGLA: pseudonimizado.';
COMMENT ON COLUMN dw.hecho_paro.produccion_turno_id IS
  'Llave al turno de produccion al que pertenece el paro; NULL si no se '
  'pudo vincular. ORIGEN: construida. REGLA: 3.028 filas de la fuente '
  'son CONTINUACIONES generadas por el boton ''Ingreso subcodigo'' y no '
  'traen pacas ni horas. Se vinculan a su cabecera en cascada de tres '
  'niveles: por fecha, maquina, operario, referencia y turno; luego sin '
  'turno; luego solo por fecha y maquina. Quedan 903 filas sin '
  'vincular, que suman 1,917 h, el 0,02% del tiempo de paro.';
COMMENT ON COLUMN dw.hecho_paro.fila_origen_excel IS
  'Numero de fila en la hoja ''Base De Datos'' del Excel (la fila 10 es '
  'la primera con datos). ORIGEN: construida. REGLA: trazabilidad: '
  'permite volver a la celda exacta del Excel ante cualquier duda.';
COMMENT ON COLUMN dw.hecho_paro.observacion_paro IS
  'Observacion libre escrita por mantenimiento. ORIGEN: columna '
  '''Observacion del paro''. REGLA: se carga sin modificar; es texto '
  'libre y no se usa para clasificar, solo para consultar el caso '
  'concreto.';
COMMENT ON COLUMN dw.hecho_paro.minutos_paro IS
  'Duracion del paro en minutos, tal como la registra la fuente. '
  'ORIGEN: columna de minutos del par correspondiente al codigo. REGLA: '
  'se conserva el valor original, incluidos los decimales raros (219,6 '
  'y 160,5), para no perder trazabilidad.';
COMMENT ON COLUMN dw.hecho_paro.horas_paro IS
  'Duracion del paro en horas. ORIGEN: derivada. REGLA: minutos / 60, '
  'con ocho decimales para que la suma de 16.482 eventos no acumule '
  'error de redondeo frente al total que calcula el Excel.';
COMMENT ON COLUMN dw.hecho_paro.unidades_no_producidas IS
  'Unidades que se dejaron de producir por este paro. ORIGEN: derivada. '
  'REGLA: tasa ideal por los minutos del paro.';
COMMENT ON COLUMN dw.hecho_paro.es_paro_planeado IS
  'Verdadero si el codigo es de naturaleza planeada. ORIGEN: derivada '
  'de dim_paro. REGLA: se copia al hecho para que los filtros del '
  'tablero no tengan que pasar por la dimension.';
COMMENT ON COLUMN dw.hecho_paro.proviene_de_continuacion IS
  'Verdadero si la fila venia de una continuacion del boton ''Ingreso '
  'subcodigo''. ORIGEN: derivada. REGLA: hace visible el artefacto del '
  'formulario de captura.';
COMMENT ON COLUMN dw.hecho_paro.subcodigo_imputado IS
  'Verdadero si la causa raiz no venia especificada. ORIGEN: derivada. '
  'REGLA: solo se evalua en los codigos 01, 03 y 05, los unicos con '
  'subcodigos; 107 de 3.691 eventos (2,9%) carecen de causa raiz '
  'utilizable.';
COMMENT ON COLUMN dw.hecho_paro.minutos_atipicos IS
  'Verdadero si la duracion supera las 8 horas. ORIGEN: derivada. '
  'REGLA: bandera de calidad; 3 eventos, el mayor de 900 minutos en el '
  'codigo 10.';
COMMENT ON COLUMN dw.hecho_paro.ejecucion_id IS
  'Identificador de la ejecucion del ETL que cargo la fila. ORIGEN: '
  'construida. REGLA: permite auditar y revertir una carga concreta.';
COMMENT ON COLUMN dw.hecho_paro.cargado_en IS
  'Marca de tiempo de la carga. ORIGEN: construida. REGLA: default '
  'now().';

-- -------------------------------------------------------------------------
--  dw.hecho_produccion_hora
-- -------------------------------------------------------------------------
COMMENT ON TABLE dw.hecho_produccion_hora IS 'Tabla de hechos de telemetria horaria.';
COMMENT ON COLUMN dw.hecho_produccion_hora.produccion_hora_id IS
  'Llave primaria tecnica. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_produccion_hora.instante IS
  'Marca de tiempo del inicio de la hora. ORIGEN: construida por el '
  'simulador. REGLA: timestamptz nativo, para que funcionen las macros '
  '$__timeFilter y $__timeGroup de Grafana.';
COMMENT ON COLUMN dw.hecho_produccion_hora.fecha_key IS
  'Llave a dim_fecha. ORIGEN: derivada de instante.';
COMMENT ON COLUMN dw.hecho_produccion_hora.hora_del_dia IS
  'Hora del dia, 0 a 23. ORIGEN: derivada de instante.';
COMMENT ON COLUMN dw.hecho_produccion_hora.maquina_key IS
  'Llave a dim_maquina. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_produccion_hora.turno_key IS
  'Llave a dim_turno. ORIGEN: derivada de la hora del dia.';
COMMENT ON COLUMN dw.hecho_produccion_hora.referencia_key IS
  'Llave a dim_referencia. ORIGEN: construida. REGLA: el simulador usa '
  'la referencia que cada linea corre con mas frecuencia en el '
  'historico.';
COMMENT ON COLUMN dw.hecho_produccion_hora.operario_key IS
  'Llave a dim_operario. ORIGEN: construida. REGLA: el simulador usa el '
  'miembro ''Sin informar'': no inventa personas reales.';
COMMENT ON COLUMN dw.hecho_produccion_hora.paro_key IS
  'Llave a dim_paro; NULL si la hora no tuvo paro. ORIGEN: construida. '
  'REGLA: la causa se muestrea de la distribucion REAL de dw.hecho_paro '
  'ponderada por horas perdidas, de modo que el Pareto del tablero '
  'operativo se parece al historico.';
COMMENT ON COLUMN dw.hecho_produccion_hora.minutos_programados IS
  'Minutos programados de la hora, normalmente 60. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_produccion_hora.minutos_paro IS
  'Minutos de paro de la hora. ORIGEN: construida. REGLA: proceso de '
  'Poisson calibrado para que la disponibilidad promedio converja a la '
  'que la maquina mostro en 2024.';
COMMENT ON COLUMN dw.hecho_produccion_hora.minutos_operativos IS
  'Minutos efectivos de produccion. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.pacas_producidas IS
  'Pacas producidas en la hora. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.unidades_producidas IS
  'Unidades producidas en la hora. ORIGEN: construida.';
COMMENT ON COLUMN dw.hecho_produccion_hora.unidades_rechazadas IS
  'Unidades rechazadas en la hora. ORIGEN: construida. REGLA: esta '
  'columna NO tiene equivalente en el Excel, porque la fuente no mide '
  'defectos. Existe aqui porque un historiador de PLC SI puede medirlo, '
  'y con ella el componente Calidad del OEE deja de ser un proxy.';
COMMENT ON COLUMN dw.hecho_produccion_hora.tasa_ideal_unid_min IS
  'Tasa ideal aplicada. ORIGEN: dim_estandar.';
COMMENT ON COLUMN dw.hecho_produccion_hora.unidades_posibles IS
  'Unidades posibles en el tiempo operativo. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.disponibilidad IS
  'Disponibilidad de la hora. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.rendimiento IS
  'Rendimiento de la hora. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.calidad IS
  'Calidad de la hora. ORIGEN: derivada. REGLA: aqui si es Calidad '
  'MEDIDA, no proxy, porque existen unidades rechazadas.';
COMMENT ON COLUMN dw.hecho_produccion_hora.oee IS
  'OEE de la hora, con los tres componentes. ORIGEN: derivada.';
COMMENT ON COLUMN dw.hecho_produccion_hora.registrado_en IS
  'Marca de tiempo de la insercion. ORIGEN: construida. REGLA: distinta '
  'de instante; permite medir la latencia entre el momento productivo y '
  'su registro.';

\echo '>> 70: OK'
