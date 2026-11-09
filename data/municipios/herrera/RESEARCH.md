# Herrera (Sevilla), INE 41050

Investigación y extracción en vivo: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- [Urbanismo municipal](https://www.herrera.es/es/temas/urbanismo/) enlaza PGOU, PBOM, registro de demandantes y noticias. El registro de demandantes no es un registro de licencias concedidas; no se ingiere. Tampoco se ingieren noticias ni anuncios de contratación.
- [Inventario PGOU municipal](https://www.herrera.es/es/temas/urbanismo/pgou/) enumera documentación de aprobación provisional, definitiva y modificaciones 1–3. La página respondió, pero el intento de acceder a la primera ficha de detalle agotó el tiempo de respuesta (40 segundos).
- [PBOM](https://www.herrera.es/es/temas/urbanismo/pbom/): el índice consultado mediante búsqueda web enumera avance, memoria, cartografía, participación, consulta previa, resumen ejecutivo y documento inicial estratégico. La petición directa desde Python agotó 20 segundos. No se extrae ni se declara aprobado.
- [Inventario municipal de transparencia del PGOU](https://transparencia.herrera.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00019/): fuente implementada. Publica tres galerías con títulos explícitos «1ª MODIFICACIÓN PGOU», «2ª MODIFICACIÓN PGOU» y «3ª MODIFICACIÓN PGOU». Conserva enlaces antiguos al PGOU base; esos enlaces no se convierten en proyectos sintéticos.

## Extracción y alcance

El adaptador descarga de nuevo el inventario de transparencia en cada ejecución. Parsea las secciones `section.gallery.link-gallery` y sus encabezados `h4.gallery-title`, agrupando todos los PDF de cada galería en un instrumento. Comprueba que el directorio documental corresponde al número de modificación, conserva títulos, URL y procedencia, y deduplica enlaces dentro de cada instrumento. No mezcla memorias homónimas entre modificaciones. Los identificadores proceden del número de modificación publicado, no del orden de los enlaces.

Resultado real: **3 instrumentos, 23 documentos** (15, 2 y 6 respectivamente). Las modificaciones 2 y 3 contienen tanto anuncio como memoria; el anuncio no se presenta como una obra ejecutada ni una licencia concedida. La ficha y sus documentos constituyen la evidencia del instrumento. No se descargan ni interpretan todos los PDF.

Cobertura **parcial**: únicamente las modificaciones presentes en este inventario municipal de transparencia. No cubre el PGOU base, PBOM, todas las modificaciones históricas o posteriores, obras físicas ni licencias. No se afirma que el inventario esté actualizado jurídicamente. No hay paginación observada: las tres galerías completas aparecen en el HTML. Si aparecen controles de paginación, el adaptador falla explícitamente; no corta un número fijo de registros. También falla si desaparecen las galerías, cambia su identificación o faltan documentos. Un error conserva el archivo de salida anterior.

## Semántica y salvaguardas

No se extraen fechas: ni la fecha del CMS, ni nombres de carpetas, ni fechas de títulos ajenos a estas galerías se reutilizan como fecha de publicación, acuerdo o aprobación. No hay fase inferida ni coordenadas. `publication_ready: false` y `geometry_status: unavailable` en todos los instrumentos. La política compartida clasifica actualmente los tres como `pendiente / insufficient_identity_evidence`; no se inventa un número de expediente para hacerlos elegibles como actividad.

El manifest identifica Herrera, Sevilla, INE 41050, desactiva licencias, programación y jitter. La actualización vuelve a descargar el inventario completo sin marca temporal ni promesa de histórico incremental.

## Validación reproducible y evidencia local

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_herrera -v` — cinco pruebas correctas. Cubren agrupación/deduplicación, separación documental, procedencia, ausencia de fechas/geometría inventadas, errores estructurales, detección de paginación, crecimiento del inventario, carga del manifest, contrato de actualización y licencias desactivadas.

Ejecución real mediante `load_manifest('herrera')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. No se ejecutan pasos de publicación, geocodificación ni bases de datos.

Evidencia local, excluida del commit:

- `evidence/proyectos.jsonl`: registros reales y anotación de la política compartida.
- `evidence/validation.json`: recuento vivo, URL fuente, limitaciones y resultado de validación.
- `evidence/inventory-live.html`: captura de la respuesta utilizada por el adaptador.
- `evidence/urbanismo.html`, `pgou.html`, `transparencia.html`: capturas de descubrimiento.
- `evidence/document-check.json` y `sample-memoria-prefix.bin`: comprobación de la memoria de la modificación 1, HTTP 200, `application/pdf`, firma `%PDF-`; solo primeros 4096 bytes. No implica comprobación de todos los documentos.
