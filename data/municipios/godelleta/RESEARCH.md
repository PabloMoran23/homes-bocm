# Godelleta — INE 46136, Valencia

Investigación y extracción real: 9 de noviembre de 2026 (UTC). Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de
adaptadores y los ejemplos de Chipiona y Manlleu antes de implementar.

## Inventarios oficiales y descubrimiento

La web `https://www.godelleta.es` y su variante sin www cerraron la conexión sin
respuesta durante la investigación. La sede electrónica pública de Godelleta sí
respondió, sin identificación. Desde su portal de transparencia se abrió la sección
7 de Urbanismo mediante su enlace Wicket y se descubrieron las URL permanentes:

- Urbanismo: https://godelleta.sedelectronica.es/transparency/91b974bb-49e4-4d13-9c0b-6d47031b3e25/
- 7.1 Planeamiento urbanístico: https://godelleta.sedelectronica.es/transparency/9938a00f-d636-4ad2-b379-b82959755654/
- 7.3 Normativa urbanística: https://godelleta.sedelectronica.es/transparency/1345e6e0-114f-4b8e-9726-122966d57941/

El padre anuncia cuatro documentos en cada una de estas dos carpetas, y la
extracción obtiene exactamente cuatro en cada una. La sección 7 también muestra
carpetas de medio ambiente, obras públicas e indicadores con contador cero y un
anuncio de suspensión de licencias. Ese anuncio no constituye una licencia
concedida ni se convierte en un proyecto. El catálogo de trámites ofrece solicitudes,
no un registro comprobado de concesiones; `licencias.enabled=false`.

La búsqueda oficial también localizó el DOGV:
https://dogv.gva.es/datos/2025/07/03/pdf/2025_24508_es.pdf
(anuncio de información pública y consultas de la misma modificación). Se conservó
la descarga de descubrimiento en evidencia, pero no se incorpora como otro proyecto
ni se afirma que el DOGV esté cubierto exhaustivamente por el scraper.

## Registro y documentos

Resultado en vivo: **un instrumento real y ocho documentos**, la modificación
puntual nº 18 del PGOU, sobre usos de energía eólica y solar fotovoltaica en suelo
no urbanizable. La carpeta 7.1 contiene certificado de acuerdo, documento técnico
de inicio, anuncio y resolución de corrección de numeración. La carpeta 7.3
contiene acuerdo, memoria de versión final, planos y resolución de segunda
exposición pública.

El `title` municipal identifica la modificación nº 18. Una etiqueta visible del
certificado todavía dice nº 5; se conserva literalmente junto con su `title`,
sin crear un instrumento nº 5. La propia carpeta contiene una resolución de
corrección de numeración. Los documentos sin descripción propia (por ejemplo
«Acuerdo mod. punt. 18») se agrupan únicamente cuando la carpeta identifica un
solo instrumento; si apareciesen varios, el parser falla para exigir revisión.
Cada documento conserva etiqueta, descripción municipal, URL permanente de vista
previa y URL del inventario de procedencia. La deduplicación usa la URL documental;
la identidad del instrumento usa el número de modificación, independiente de la
sesión y de los tokens Wicket.

Se verificó directamente el documento:
https://godelleta.sedelectronica.es/preview-document/dd55fcac-1dd8-40b4-ba48-29e34bc35471
La vista previa respondió HTTP 200 y su iframe PDF, descargado con la misma sesión
anónima, respondió HTTP 200 `application/pdf`, 2.940.294 bytes, firma `%PDF-`.
La portada identifica expresamente modificación nº 18, PGOU de Godelleta,
exclusión de plantas solares y eólicas en suelo no urbanizable, promotor municipal
y octubre de 2023. Capturas: `evidence/memoria-mod18.pdf` y su texto extraído con
`pdftotext`. Los enlaces temporales al PDF no se fijan en los registros: se retiene
la vista previa permanente. La comprobación del PDF es evidencia de investigación;
el adaptador extrae los inventarios HTML, no interpreta automáticamente los PDF.

## Semántica, cobertura y límites

Es una instantánea parcial de dos carpetas documentales públicas actuales, no un
histórico completo de expedientes, obras o licencias ni una declaración de vigencia.
No se deducen fases, aprobación definitiva ni ejecución a partir de «versión final»
o del nombre de un acuerdo. Fechas de creación de la sede, fechas en etiquetas,
fecha de consulta, fecha de redacción de la memoria y fecha de publicación del DOGV
no se reutilizan como fechas de aprobación. `fecha_publicacion`, `fecha_acuerdo`
y `fecha_aprob` quedan nulas en esta extracción de inventario. Tampoco se extrae
geometría de los planos: coordenadas y geometría nulas, `publication_ready=false`.
`schedule.enabled=false` y `geocode.jitter_missing=false`.

No se observó paginación en las carpetas capturadas. Se comprueban los recuentos
anunciados por el padre; ante paginación visible, subcarpetas nuevas, instrumentos
ambiguos, redirección inesperada, ausencia de inventario o diferencia de recuentos,
el adaptador falla antes de sobrescribir el JSONL. No hay un límite de resultados
que trunque silenciosamente el inventario. Los cambios de esquema que no activen
estas comprobaciones siguen siendo una limitación de cualquier parser HTML.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_godelleta -v`

Cinco pruebas correctas: agrupación y numeración corregida, rechazo de páginas
vacías/trámites, rechazo de paginación/subcarpetas/ambigüedad, protección del
snapshot frente a recuentos incompletos, manifest y licencias desactivadas.

Se ejecutó realmente `GodelletaAyuntamientoAdapter.backfill_proyectos` con
`config={'capture_dir': 'evidence'}` y destino `evidence/proyectos.jsonl`.
`evidence/validation.json` recoge `live_records: 1`, ocho documentos, URLs fuente,
limitaciones, runtime y verificación documental. Las tres capturas de la ejecución
son `urbanismo.html`, `inventory-0.html` e `inventory-1.html`. La evidencia es local
y no forma parte de los cuatro archivos fuente. Sin publicación, base de datos,
geocodificación, instalación de dependencias ni cambios compartidos.
