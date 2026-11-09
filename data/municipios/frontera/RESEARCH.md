# Frontera — INE 38013

Investigación y ejecución real: 9 de noviembre de 2026. Municipio de Frontera (denominado La Frontera por el Ayuntamiento), El Hierro, provincia de Santa Cruz de Tenerife, Canarias. Se revisaron primero el contrato `municipio/adapters/portal.py`, el cargador `municipio/manifest.py`, el registro de adaptadores y los ejemplos Chipiona/Hernani con sus manifiestos. No se modificaron fuentes compartidas ni dependencias.

## Fuentes oficiales actuales

El [inventario municipal de planeamiento](https://www.aytofrontera.org/ayuntamiento/planeamiento.html) contiene tres enlaces a páginas documentales:

- [Plan General de Ordenación 2003](https://www.aytofrontera.org/plan-general-de-ordenacion.html): 102 documentos de memorias, planos, normativas y fichas, agrupados en un instrumento. Las fichas de unidades no se convierten en proyectos independientes.
- En esa misma página, [Aprobación modificación menor unidad de actuación F-11](https://www.aytofrontera.org/pgo/Aprobacion%20modificacion%20menor%20unidad%20de%20actuacion%20F11.pdf): un instrumento separado, explícitamente nombrado, con su documento y enlace a la página del PGO padre. El título expresa aprobación, pero no se interpreta el PDF para atribuir fecha o fase normalizada.
- [Plan Belgara. Modificación P.G.O.](https://www.aytofrontera.org/plan-belgara-modificacion-p-g-o.html): 16 documentos de un único instrumento.
- [Plan General de Ordenación 2023 en elaboración](https://www.aytofrontera.org/plan-general-de-ordenacion-2023.html): 94 documentos, incluidas alternativas, borrador y Documento Inicial Estratégico. Los planos de infraestructuras forman parte del plan y no son obras ejecutadas independientes. «2023» se conserva como parte del título; no es una fecha de aprobación. La expresión «en elaboración» se conserva y no se afirma aprobación definitiva.

También se inspeccionó el [inventario de proyectos financiados con fondos europeos](https://www.aytofrontera.org/ayuntamiento/proyectos-financiados-con-fondos-europeos.html), capturado en `evidence/proyectos-financiados.html`. Contiene epígrafes genéricos de subvenciones, enlaces de resoluciones y noticias; algunos enlaces «PDF» de los apartados de abastecimiento y fotovoltaica repiten erróneamente la resolución de dotación de libros. No se incorporó al extractor de planeamiento ni se convirtió una subvención genérica en una obra. Este scraper no cubre todas las obras municipales.

## Extracción y semántica

Se descubren los instrumentos desde los enlaces del contenido Joomla/SP Page Builder, sin lista precargada de registros. Se visita cada página de detalle y se retienen los enlaces PDF con título y `source_url`. Los documentos se deduplican por URL dentro del instrumento; la modificación menor expresamente nombrada se separa del PGO padre. Cada registro conserva URL, inventario y procedencia municipal; las identidades se derivan de la URL, sin coordenadas ni identificadores de expediente inventados.

El inventario y sus páginas documentales observadas son páginas completas sin paginación. El parser rechaza controles de paginación, enlaces next o parámetros start/limitstart/page en vez de devolver silenciosamente solo la primera página. La desaparición del contenedor, de los instrumentos o de sus documentos provoca error. La escritura del resultado ocurre solo después de extraer todas las páginas, mediante reemplazo de fichero temporal. La actualización vuelve a leer el inventario completo: no hay cursor temporal ni historial incremental prometido.

No se extraen `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob`: no se confunden fechas del CMS, rutas de carga de adjuntos o años del título con fechas de acuerdo. No se deducen fases, vigencia legal ni aprobación de los documentos por su mera publicación. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`. No se ha verificado un registro de licencias concedidas: `licencias.enabled=false`; sus métodos escriben un resultado vacío explícitamente desactivado. También están desactivados `schedule.enabled` y `geocode.jitter_missing`.

## Validación reproducible

Runtime preinstalado utilizado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_frontera -v
```

Cinco pruebas correctas: filtrado y deduplicación del inventario; agrupación documental y separación de la modificación; ausencia de metadatos inferidos; rechazo de cambios estructurales, paginación y orígenes ajenos; carga del manifiesto por el registro, actualización completa, licencias desactivadas y conservación del resultado ante un fallo posterior.

Se ejecutó realmente `load_portal_adapter(load_manifest('frontera')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando únicamente `capture_dir=evidence` en memoria para guardar las cuatro páginas consultadas. Resultado: **4 registros y 213 enlaces documentales** (102 + 1 + 16 + 94). `evidence/validation.json` incluye recuento, URLs de fuente, pruebas, limitaciones y comprobaciones de documentos. Un PDF por registro respondió HTTP 200, `application/pdf` y firma `%PDF-`; se guardaron solo los primeros 1024 bytes en `document-sample-*.bin`. Los otros enlaces se conservan sin afirmar que todos se hayan descargado o interpretado. Las páginas completas quedan como capturas HTML locales.

La evidencia es local y no forma parte de los cuatro ficheros de código/documentación entregables. No se ejecutó publicación, despliegue, acceso a base de datos ni geocodificación.
