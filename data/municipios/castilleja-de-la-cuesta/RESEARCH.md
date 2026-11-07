# Castilleja de la Cuesta — Sevilla — INE 41029

Investigación y extracción real: 7 de noviembre de 2026. Un único adaptador municipal, sin fuentes compartidas ni dependencias nuevas.

## Fuentes oficiales descubiertas

- [Inventario IND-53: modificaciones del PGOU y planes parciales](https://transparencia.castillejadelacuesta.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00036): fuente implementada. HTML público de transparencia del Ayuntamiento, con galerías de documentos por ámbito e instrumento.
- [PGOU municipal](https://www.castillejadelacuesta.es/es/ayuntamiento/pgou/): contiene documentación de modificaciones institucionales y del Sector El Valle, pero también una bonificación tributaria. No se incorporan automáticamente todos sus adjuntos ni se mezclan con los instrumentos del inventario.
- [PGOM municipal](https://www.castillejadelacuesta.es/es/ayuntamiento/pgom/): enlaza el sitio del nuevo plan, https://castillejadelacuesta.nuevoplan.es/. El PGOM en elaboración queda fuera de esta extracción.
- [Inventario IND-50 del PGOU](https://transparencia.castillejadelacuesta.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-planos-que-lo-detallan/): otra fuente oficial localizada; no se mezcla el plan general base con las modificaciones IND-53.

Las páginas PGOU, PGOM e IND-53 se conservaron bajo `evidence/`. No se extraen noticias, anuncios de contratación, solicitudes ni formularios como actuaciones o licencias concedidas.

## Cobertura y unidad de registro

Resultado real: **26 grupos documentales, 245 enlaces PDF, 12 respuestas HTML válidas**. Incluye Sector 1, La Albina, El Solís, La Alberquilla y La Cerca, El Valero, El Valle, Valdovina, el estudio de detalle de Miguel Ángel Asturias y la modificación de Diego de los Reyes 171. Son instrumentos/proyectos de planeamiento y gestión, no 26 obras físicas ni licencias concedidas.

Cada registro conserva el encabezado de ámbito y el de su galería; agrupa memoria, planos, certificados y demás documentos en `documentos`, con título, URL original y páginas donde se observó cada enlace. Los identificadores se derivan de esos encabezados, no de una fecha supuesta. Las galerías con exactamente el mismo conjunto de URLs se consolidan reteniendo los encabezados alternativos. El portal distingue documentos anteriores y modificaciones en carpetas diferentes; se conserva esa separación y no se afirma que todos estén vigentes. No se deducen expedientes a partir de la numeración editorial de las galerías.

Se omiten galerías sin PDF, incluidos proyectos de urbanización vacíos, el encabezado intermedio del sector 3-A y el enlace general al PGOM. Los enlaces de referencia a carpetas, sin PDF, tampoco generan registros. El inventario es documental e histórico tal como está publicado actualmente; no acredita exhaustividad histórica, vigencia jurídica, aprobación de cada documento ni ejecución material. Los 245 enlaces se conservaron, pero no se descargaron ni verificaron individualmente todos los PDF.

## Paginación comprobada

OpenCMS reutiliza nombres de parámetros entre galerías distintas. Se detectaron estos máximos globales: `pagegalleryfiles-1-1` hasta 3, `pagegalleryfiles-3-1` hasta 4, `pagegalleryfiles-4-1` hasta 2 y `pagegalleryfiles-5-1` hasta 2. Se solicitaron la portada y cada página 1..última por parámetro (12 URLs en total), fusionando documentos por sus encabezados y URL.

El servidor genera controles siguiente/anterior fuera de rango cuando una galería corta recibe un número válido para otra galería más larga. El extractor usa el control explícito `lastpagelink` de cada galería para enumerar todas sus páginas reales, incluidas las ocultas por los controles deslizantes. En la última página ese control está deshabilitado con un fragmento y el número se obtiene del control activo. Los enlaces fuera de ese límite no son páginas del inventario. Se comprueba el número activo y que las páginas adicionales válidas no estén vacías ni repitan la primera. Un error de red, cambio de estructura o paginación inesperada aborta antes de escribir un resultado parcial. El límite defensivo de 100 respuestas también provoca error, nunca truncamiento silencioso.

## Semántica y comprobación documental

`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas: no se convierten fechas de CMS, nombres de archivo o años de carpeta en acuerdos. No se asigna fase por el título del inventario. Sin coordenadas ni geometría verificadas; `publication_ready=false`. `source_entity_type=documento` identifica honestamente la naturaleza documental y la política compartida devuelve 26 documentos, cero entidades desconocidas y ninguna actividad elegible para publicación automática.

Se descargó como muestra `00-DOC.-ESCRITA.pdf` de Diego de los Reyes: HTTP 200, `application/pdf`, firma PDF válida, 382490 bytes. Es un escaneo sin texto extraíble; se renderizó e inspeccionó la primera página. Su portada identifica una propuesta de modificación puntual del plan general para la parcela en calle Diego de los Reyes 171, Castilleja de la Cuesta (Sevilla). Se conservan PDF, imagen y metadatos de descarga en `evidence/`; no se incorporan las fechas de portada o sellos como fechas de acuerdo del registro.

Licencias desactivadas por falta de registro verificado de concesiones. `schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_castilleja_de_la_cuesta -v` — **11 correctas**. Cubren agrupación y aislamiento documental, vacíos, duplicados, paginación completa y rechazada, controles fuera de rango/deshabilitados, conservación del resultado anterior ante fallos, estabilidad de IDs, manifiesto, licencias desactivadas y clasificación documental.

Extracción real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `adapter.config['capture_dir']='evidence/live-captures'`. La evidencia final está en `evidence/proyectos.jsonl`, `evidence/validation.json` y las 12 capturas de `evidence/live-captures/`. Cada captura usa `inventory-<primeros 16 caracteres SHA256 de URL>.html`; `source_urls` enumera las URLs exactas. La evidencia es local y no forma parte de los cuatro archivos fuente entregados. No se ejecutó publicación, sincronización, geocodificación ni acceso a base de datos.
