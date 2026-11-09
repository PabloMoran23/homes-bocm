# Viator — Almería — INE 04101

Investigación y ejecución real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

El sitio del Ayuntamiento ofrece la categoría [Normativa urbanística](https://ayuntamientoviator.es/category/normativa/), consultada por HTTP durante la investigación y de nuevo por el adaptador. La página actual contiene dos instrumentos y no presenta paginación:

- [Adaptación parcial a la L.O.U.A.](https://ayuntamientoviator.es/adaptacion-parcial-a-la-loua/): 33 documentos enlazados, incluyendo memoria y anexos, planos de información y planos de ordenación. El encabezado identifica el planeamiento general y menciona junio de 2009; esa referencia mensual no se convierte en fecha de aprobación.
- [NN.SS. de Viator](https://ayuntamientoviator.es/nnss-de-viator/): 14 documentos enlazados, incluyendo índice, capítulos, fichas reguladoras y catálogo municipal. Se conserva todo como un instrumento, incluido el catálogo, sin generar proyectos independientes para cada capítulo o plano.

La cobertura es **parcial e histórica**: documentación actualmente publicada, no un registro completo de instrumentos vigentes, modificaciones posteriores, proyectos de obras o concesiones de licencia. La categoría es el inventario recorrido; no se pretende cubrir todo el blog municipal. El adaptador descubre las fichas desde los títulos del inventario, no devuelve registros precargados. Los documentos PDF se extraen solamente del contenido de su ficha, conservando título, enlace y URL de procedencia.

También se identificaron [Administración electrónica](https://ayuntamientoviator.es/admon/) (formularios de solicitud) y [Ordenanzas Municipales](https://ayuntamientoviator.es/ordenanzas-municipales/) (normativa y tasas). No constituyen registros de licencias concedidas. La portada enlaza el portal de transparencia de la sede; no se integra ni se afirma haber recorrido su contenido. El [BOJA 141 de 2018](https://www.juntadeandalucia.es/boja/2018/141/91) contiene una modificación del PGOU del Sector 3, SSGG-EQ-05: demuestra que estos dos instrumentos municipales no representan todas las modificaciones históricas. No se incorpora esa publicación aislada como inventario municipal ni se mezcla su acuerdo con las fechas de las fichas extraídas.

## Semántica y límites

Las dos fichas muestran publicación CMS del 15 de abril de 2011: se guarda exclusivamente `fecha_publicacion: 2011-04-15`. No se deducen fecha de acuerdo, aprobación, fase, vigencia, parcelas ni coordenadas. `publication_ready: false` y `geometry_status: unavailable`. Las licencias, la programación y el desplazamiento aleatorio de coordenadas están desactivados en el manifiesto.

El recorrido sigue todos los enlaces de paginación del inventario con un conjunto de páginas visitadas, sin límite que trunque resultados. La ficha multipágina, un cambio de estructura, un instrumento sin documentos, una redirección inesperada o un error HTTP detienen la extracción antes de sustituir la salida anterior. Las actualizaciones hacen un refresco completo y no usan la fecha de publicación como marca incremental.

Los enlaces se conservan sin afirmar que se han leído todos los PDF. La verificación documental puntual descargó los primeros 1024 bytes de `memoriayanexos.pdf` e `indice.pdf`: HTTP 200, `application/pdf` y firma `%PDF-` en ambos casos. No verifica la disponibilidad de los otros 45 documentos, ni la vigencia jurídica del conjunto.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `python -m unittest municipio.test_viator -v`: cinco correctos. Comprueban agrupación y aislamiento de documentos, semántica de fechas, exclusión de formularios/licitaciones/noticias, paginación de dos páginas, fallos de estructura y conservación de la salida anterior, y restricciones del manifiesto.

Extracción real mediante `load_manifest('viator')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['evidence_dir']` apuntando al directorio local de evidencia. Resultado: **2 registros, 47 enlaces documentales, 1 página de inventario y 2 fichas**. La anotación compartida de entidades devolvió estado `ok`, con ambas categorías desconocidas; no se fuerza una categoría de obra física a instrumentos de planeamiento.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de las tres URLs recorridas (nombres derivados de SHA-256), capturas legibles de investigación y muestras binarias de los dos PDF. `validation.json` contiene recuentos, URLs consultadas, limitaciones, resultado de tests y comprobaciones HTTP documentales. No se accedió a bases de datos ni se publicó contenido.
