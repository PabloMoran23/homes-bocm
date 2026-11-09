# La Lastrilla — investigación y alcance

Verificación: 9 de noviembre de 2026. Municipio **La Lastrilla**, provincia de
**Segovia**, Castilla y León, **INE 40112**. El archivo oficial identifica la
selección como `LASTRILLA (LA) Código INE: 40112`; la lista provincial identifica
el municipio 112 de la provincia 40 como `Lastrilla, La`.

## Inventarios oficiales descubiertos

- Web municipal: https://www.lalastrilla.es/ y su ruta `/urbanismo` devolvieron
  HTTP 403 desde este entorno. No se atribuyen contenidos a esas páginas.
- Sede municipal: https://lalastrilla.sedelectronica.es/info.0 responde por HTTP
  con contenido municipal (el navegador de investigación encontró un bucle de
  redirección; requests pudo leerla). Las solicitudes de licencia y declaraciones
  responsables son trámites reutilizables, no concesiones. No se extraen.
- https://lalastrilla.sedelectronica.es/board muestra anuncios y un botón
  «Mostrar más». Sus primeras diez entradas no constituyen un inventario
  completo: se observaron asuntos fiscales, empleo, convocatoria de pleno y
  modificación presupuestaria para una cubierta deportiva. No se convierten en
  proyectos ni se presenta esa primera página como cobertura histórica.
- https://lalastrilla.sedelectronica.es/transparency muestra carpetas y
  «Mostrar más», entre ellas un convenio SOMACYL de renovación de abastecimiento
  de agua de 2026. No se ha recorrido ese árbol AJAX ni extraído ese convenio.
- Fuente implementada: [archivo oficial PLAU de la Junta de Castilla y León](https://servicios.jcyl.es/PlanPublica/).
  Su portada distingue archivo vigente e información pública (PLAI).
  [Selección provincial de Segovia](https://servicios.jcyl.es/PlanPublica/lmuni_plau.do?provincia=40).
  [Inventario municipal utilizado](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=112).
  El manifiesto usa `proyectos.source: ayuntamiento` como categoría admitida por
  el esquema común; la procedencia real se explicita en portal y en cada fila
  como `source: junta_castilla_y_leon`, `origen: PLAU`.

## Extracción implementada

Se recorren las páginas mediante el enlace real `Siguiente` codificado en
`doResults(...unescape(...))`, sin activar «Mostrar históricos» ni el filtro de
sólo planeamiento general. La respuesta inicial identifica el INE; se comprueban
los encabezados, el rango de cada página, el total constante, los identificadores
sin repeticiones y la provincia/municipio del siguiente enlace. Se exige que la
suma de las filas coincida con el total. Un cambio o una página incompleta
interrumpe la extracción antes de reemplazar la salida.

Resultado observado: **47 entradas en cuatro páginas** (1–15, 16–30, 31–45 y
46–47). Se extraen **40 instrumentos municipales PU/GU**: planes parciales,
estudios de detalle, normas subsidiarias y modificaciones, plan especial,
proyectos de reparcelación, urbanización y normalización. Se excluyen siete
entradas: dos convenios CU, tres sentencias PU y dos entradas OT de directrices
supramunicipales (una de ellas es otra sentencia). La exclusión se registra en
el resultado de ejecución. Los códigos regionales `40000-OT-...` aparecen en el
inventario municipal, pero no se atribuyen como instrumentos de La Lastrilla.

Se conserva una fila por identificador documental PLAU, con sus **70 enlaces a
ficheros** agrupados en `documentos`, nombres originales y listado de procedencia
`ldoc_files.do?cDocId=...`. No se crean proyectos independientes por plano,
memoria o portada. Diferentes instrumentos publicados por el archivo conservan
sus identidades, aunque compartan ámbito o nombre de fichero (por ejemplo,
normalización y urbanización AA-U.1 de 2026). Los enlaces eliminan el parámetro
de sesión efímero. Si el listado de ficheros incorporase paginación, el parser
fallaría para evitar una descarga parcial inadvertida.

**13 entradas no tienen ficheros técnicos** según el propio archivo. Se
conservan como instrumentos identificados por su fila oficial, con
`documentos_status: sin_ficheros_en_inventario` y el enlace al resolvedor de
boletín del archivo. Ese enlace no acredita que el PDF siga disponible.

## Semántica y límites

- `fecha_publicacion` y `fecha_acuerdo` transcriben las columnas separadas del
  PLAU. `fecha`, `fecha_aprob` y `fase` permanecen nulas: no se deduce una fase o
  fecha de aprobación de la mera presencia en el archivo. No se leen ni
  interpretan acuerdos dentro de los PDF. Ejemplo de cautela: el inventario
  publica para la modificación 11 (`300758`) la fecha **20/01/2024**, mientras
  la búsqueda del BOCYL apunta a una publicación el 02/01/2024. Se conserva el
  dato del PLAU con su procedencia; no se armoniza silenciosamente.
- La pertenencia al archivo denominado vigente no prueba por sí sola la vigencia
  jurídica de cada determinación: el inventario también incluye sentencias.
  No se afirma que los instrumentos estén actualmente aprobados o ejecutándose.
- Los identificadores `archivo_id` y `archivo_codigo` son referencias documentales
  del archivo, no números administrativos de expediente inventados. Se declara
  `source_entity_type: documento`; la política compartida los trata como
  documentos, sin afirmar elegibilidad como actividad o licencia concedida.
- No hay coordenadas ni geometrías verificadas: `lat`, `lon`, `geometry` son
  nulas y `publication_ready` es falso. No se usan centroides o desplazamientos.
- Cobertura parcial del archivo consultado: no abarca el PLAI, históricos
  ocultos, convenios, resoluciones judiciales, todo el tablón municipal ni todas
  las obras físicas y licencias del municipio. No se usa prensa ni anuncios de
  contratación como sustitutos de instrumentos o proyectos.
- Las actualizaciones vuelven a leer la selección completa. No se usa un corte
  temporal que omita documentos añadidos con fechas antiguas.

## Validación reproducible y evidencia local

Intérprete utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `python -m unittest municipio.test_la_lastrilla -v` (seis pruebas).
Cubren identidad, fechas, enlaces sin sesión, agrupación de PDF, paginación y
rechazo de ámbitos ajenos, exclusión de sentencias, documentos ausentes, carga
del manifiesto, licencias desactivadas y conservación de la salida ante fallo.

La ejecución real usa `load_portal_adapter(load_manifest('la-lastrilla'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con la opción local
`capture_dir='evidence/captures'`. No hay salida de ejemplo precargada ni lista
de proyectos codificada en el adaptador. Se guardan las respuestas HTML de todas
las páginas y listados consultados. `evidence/validation.json` incluye el recuento,
URLs realmente consultadas, exclusiones, limitaciones, evaluación de entidades
y comprobaciones HTTP de muestra de documentos. Evidencia local sin publicar.

Comprobación adicional: los dos resolvedores PDF de las actuaciones de 2026
(`cFicheroId=168212` y `168213`) producen cabeceras de redirección con caracteres
no UTF-8 que requests no puede decodificar. El inventario y sus listados de
ficheros sí se extraen correctamente; esos enlaces se retienen como publicados,
pero no se afirma haber validado el contenido binario de los PDF. Los errores
de esta comprobación de muestra constan en `validation.json`.
