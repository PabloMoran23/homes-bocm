# Tudela de Duero — Valladolid — INE 47175

Investigación y extracción en vivo: 8 de noviembre de 2026.

## Descubrimiento y procedencia

La web oficial https://tudeladeduero.ayuntamientosdevalladolid.es/ enlaza «Normativa Urbanística» al archivo oficial de la Junta de Castilla y León:

https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion&pager.sortindex=-3&provincia=47&municipio=175

Se comprobó el encabezado TUDELA DE DUERO, Código INE 47175; el archivo indicaba actualización 06-nov-2026. Provincia 47, municipio 175. No confundir con Tudela (Navarra), cuyos portales tudela.es se excluyen. La sede municipal https://tudeladeduero.sedelectronica.es/info.0 también identifica el Ayuntamiento y muestra el anuncio del estudio de detalle de Callejón de la Iglesia/Pablo VI. Se usa el inventario regional enlazado por el Ayuntamiento como fuente documental estructurada, no noticias ni anuncios de contratación.

## Cobertura y unidades

La vista actual, sin marcar «Mostrar históricos», contiene 25 entradas. Se recorren las páginas 1–15 y 16–25 mediante pager.offset=0 y 15. Se comprueban inicio/final/total, duplicados y estabilidad del total; cualquier discrepancia aborta antes de escribir. No se limita a la primera página. La paginación nueva en listados de ficheros causa error para revisión, nunca truncamiento silencioso.

Resultado real: **20 instrumentos/proyectos** municipales de planeamiento y gestión urbanística. Incluye el estudio de detalle Callejón de la Iglesia nº 5 y finca segregada en calle Pablo VI (publicación 22/10/2026, acuerdo 24/09/2026), revisión del PGOU, modificación del plan parcial del sector 13, normalizaciones de fincas NF26 y NF10, planes parciales y un PERI. Modificaciones son instrumentos diferenciados, con identificadores propios. Los planos, memorias, normativa y anexos de un mismo paquete no se convierten en proyectos separados: el PGOU tiene **85 ficheros agrupados**.

Se excluyen dos entradas OT de directrices de Valladolid y entorno, de ámbito supramunicipal, y un convenio urbanístico. Las otras dos entradas son una sentencia sobre nulidad de apartados del PGOU y una corrección de errores no admitida: se conservan como `eventos_relacionados` del único PGOU, con sus fechas, identificadores, listados, boletines y ficheros, sin contabilizarlas como nuevos proyectos ni atribuirles aprobación. La asociación exige un único PGOU; si resulta ambigua se aborta.

## Semántica y límites

`fecha_publicacion` y `fecha_acuerdo` corresponden estrictamente a las columnas del inventario; se conservan también los textos originales. No se deducen `fecha_aprob`, fase, vigencia, ejecución, presupuesto o concesión. Los antiguos valores 01/01/1970, 01/01/1974 y 01/01/1975 se retienen sólo como texto original porque su precisión no está acreditada. Los campos normalizados quedan nulos. Algunos registros carecen de descarga y se conservan con su referencia de inventario/boletín y lista de documentos vacía.

Cada ficha conserva la procedencia municipal y regional, identificador documental cuando existe, enlaces al listado de ficheros y boletín cuando están anunciados, y todos los enlaces de ficheros de ese paquete. Se eliminan identificadores efímeros de sesión de las URLs. Los identificadores de registros sin cDocId derivan del tipo y título, nunca de su posición en la página. Los eventos legales posteriores impiden interpretar presencia en el inventario como garantía de vigencia jurídica.

Cobertura parcial: no se activa la vista histórica ni se extrae un registro integral de obras públicas o expedientes municipales. No se ha verificado registro público de licencias concedidas: los formularios y procedimientos no son concesiones. Licencias y programación desactivadas. Sin geometría verificada ni coordenadas; `publication_ready=false`, `geocode.jitter_missing=false`. La anotación compartida trata las fichas como documentos, sin afirmar elegibilidad como actividad sólo por su presencia en el inventario. No se analizan contenidos completos ni geometrías de los PDFs.

## Validación reproducible

Runtime preinstalado utilizado:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_tudela_de_duero -v
```

Nueve pruebas offline: identidad municipal, columnas y totales, separación de fechas, valores antiguos, exclusión de formularios/convenios/directrices, asociación de eventos PGOU, agrupación y aislamiento documental, URLs sin sesión, paginación completa y rechazo de páginas repetidas sin salida parcial, manifest y licencias desactivadas.

Se cargó el manifest con `load_manifest('tudela-de-duero')`, se resolvió `load_portal_adapter`, se configuró `capture_dir='evidence'` sólo en memoria y se ejecutó `backfill_proyectos(Path('evidence/proyectos.jsonl'))` contra las fuentes reales, incluida la anotación compartida. `update_proyectos` repite el snapshot completo, sin afirmar incrementalidad temporal ni usar fechas como cursores.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (recuento, URLs, límites, fecha de comprobación y resumen de pruebas), capturas `inventory-0.html`, `inventory-15.html`, `files-*.html`, `home.html`, `sede.html`, `parser-tests.txt`. Se verificó una descarga del estudio de detalle (`openFichero.do?cFicheroId=170239`): HTTP 200, application/pdf, firma `%PDF`; el servidor redirige a http://www.jcyl.es/plaupdf/47/47175/301974/DOCUMENTO%20COMPLETO.pdf. Sólo se conservaron 2048 bytes en `sample-document-prefix.bin`, con metadatos en `document-check.json`; no se afirma haber revisado todo el PDF.
