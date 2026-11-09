# Montalbán de Córdoba — INE 14040, Córdoba

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y descubrimiento

Inventario utilizado: https://montalbandecordoba.es/ayuntamiento/ayuntamiento-informacion_municipal/ayuntamiento-informacion_municipal-urbanismo/

La página municipal de Urbanismo publica carpetas documentales Divi (`.carpetas_doc`). La portada y el portal de transparencia respondieron HTTP 403 en esta sesión. La API pública de WordPress permitió descubrir la página (id 8157): https://montalbandecordoba.es/wp-json/wp/v2/pages?search=urbanismo y https://montalbandecordoba.es/wp-json/wp/v2/pages?search=planeamiento . Ambas consultas devolvieron `X-WP-TotalPages: 1`; no se recortaron resultados de descubrimiento. La página individual https://montalbandecordoba.es/wp-json/wp/v2/pages/8157 también respondió 200. Finalmente la URL completa de Urbanismo respondió HTTP 200 con User-Agent Mozilla/5.0 y es la única fuente utilizada por el adaptador, sin depender de resultados de buscadores ni de una colección precargada.

La página de Normativa y Solicitudes, descubierta en la misma API, contiene declaraciones responsables, solicitudes y autoliquidaciones: https://montalbandecordoba.es/ayuntamiento/ayuntamiento-documentos/ . Estos documentos no son concesiones de licencias ni proyectos. No se ha comprobado un registro público de licencias concedidas; `licencias.enabled=false`.

## Cobertura y agrupación

Extracción real: **8 registros y 17 enlaces PDF únicos**, pertenecientes a cinco instrumentos/dosieres urbanísticos y tres obras públicas documentadas:

- Normas subsidiarias de planeamiento: ordenanzas y tres planos, agrupados.
- Innovación-modificación puntual del PGOU: documento separado de las normas subsidiarias.
- Plan parcial Huerta de Dios: modificación puntual, ordenanzas y plano.
- Plan parcial Huertos del Infante: modificación puntual, ordenanzas y plano.
- Plan parcial Los Lucas: ordenanzas y plano.
- PFEA 2018, Urbanización Calle Empedrada, segunda fase: primera parte y segunda parte (planos) en un único proyecto.
- PFEA 2018, Camino Senda Gitanos, tercera fase.
- PFEA 2018, Acerado Llano del Sótano Pub Catedral.

Las modificaciones y documentos del mismo plan parcial se conservan en su dosier municipal, sin afirmar que sean un único acuerdo administrativo. Las etiquetas fragmentadas de enlaces con URL idéntica se retienen en `etiquetas`, deduplicando el documento. Cada documento conserva URL y página de procedencia. Se excluyen mapas generales de catastro, casco urbano e infraestructuras: su mera publicación no demuestra una obra concreta.

La página sirve el inventario entero sin paginación observada. El parser rechaza paginación detectada, secciones desconocidas, proyectos con etiquetas no revisadas, enlaces externos o contenido vacío. No hay límite de registros ni corte por fecha. Las actualizaciones vuelven a extraer el inventario completo. Los identificadores derivan del título del instrumento, no de la posición o del orden de los documentos.

## Semántica y límites

Es cobertura parcial del inventario documental publicado actualmente, con documentos históricos; no representa todas las obras, licencias o expedientes municipales ni garantiza vigencia. No se usan los años de carpetas de subida o fechas del CMS como fechas de publicación, acuerdo o aprobación. No se afirma aprobación ni ejecución por aparecer un documento en esta página. No se generan coordenadas, geometrías, fases ni fechas. `publication_ready=false`, `geometry_status=unavailable`, `schedule.enabled=false` y `geocode.jitter_missing=false`.

El envoltorio del registro de adaptadores aplicó la política compartida de entidades: ocho categorías desconocidas, informe `status=ok`. Esta implementación conserva tipos documentales amplios y no inventa categorías más precisas para superar esa clasificación.

## Verificación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_montalban_de_cordoba -v`, cinco pruebas correctas. Cubren agrupación de partes, aislamiento de instrumentos, deduplicación, exclusión de mapas/formularios, ausencia de fechas/geometría inventadas, rechazo de paginación y escritura mediante los métodos del contrato.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: ocho registros. Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/live-urbanismo.html` y capturas de descubrimiento/API. Se solicitaron los primeros 1024 bytes de dos documentos (innovación del PGOU y planos de Calle Empedrada): ambos HTTP 206, `application/pdf` y firma `%PDF-` válida. Las capturas parciales están en `evidence/document-0-prefix.bin` y `evidence/document-1-prefix.bin`. No se han descargado ni verificado íntegramente los 17 documentos.

Sin base de datos, geocodificación, publicación ni ejecución programada.
