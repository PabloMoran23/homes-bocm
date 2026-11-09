# Agost — Alicante — INE 03002

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

Fuente extraída: [Obras y Urbanismo del Ayuntamiento de Agost](https://www.agost.es/el-ayuntamiento/obras-y-urbanismo/), HTTP 200. El apartado «PLANEAMIENTO MUNICIPAL» contiene cinco secciones de acordeón, cuyos enlaces están en el HTML sin interacción: revisión de Normas Subsidiarias, modificaciones puntuales, ordenanzas, planeamiento diferido y planeamiento en tramitación. No se observó paginación. El parser revisa todos los grupos y todos los documentos, sin límite de registros. Ante marcadores de paginación falla explícitamente para impedir una extracción parcial inadvertida; nuevas secciones o estructuras desconocidas también requieren revisión.

Se consultó además el inventario oficial [Planes, Ordenanzas y Reglamentos](https://www.agost.es/el-ayuntamiento/ordenanzas/). Contiene normativa fiscal, planes sectoriales y reglamentos; no se usa para inventar proyectos ni concesiones. No se ha verificado un registro público de licencias concedidas. Noticias, anuncios de contratación, modelos de solicitud y ordenanzas no se extraen como actuaciones.

La extracción viva produjo **21 instrumentos y 74 enlaces documentales**:

- Una revisión de las Normas Subsidiarias de Agost 1995, con 15 documentos.
- Catorce modificaciones puntuales: 1, 3, 7, 10, 11, 6, 12, 13, 15, 16, 17, 19, 20 y 22; 15 documentos en total, incluyendo el anexo de mapas de la 17 dentro del mismo registro.
- Dos planes parciales, SAU/I.1 La Escandella y SAU/I.2 Els Castellans, con 5 y 16 documentos respectivamente. «Plan parcial» se deriva del subgrupo «parcial» y de la ruta documental `/parcial/`.
- Catálogo de Protecciones (6 documentos) y modificaciones 23 (3), 24 (12) y 25 (2), bajo «Planeamiento en tramitación».

Los nombres y documentos se leen del inventario vivo; no hay una lista precargada de expedientes. Cada instrumento conserva `source_section`, `inventory_url` y `documentos` con título, URL original y procedencia. Las identidades de modificaciones usan el número, y no los nombres de anexos. Los tres enlaces fragmentados del plano de unidades de ejecución de La Escandella se deduplican por URL y reúnen sus textos.

La modificación 24 tiene cinco etiquetas sin enlace: 03_usos del Suelo, 04_Afecciones Ambientales, 06_Afecciones de Paisaje, 12_Superposicion Ámbito-fotovoltaica y 13_Clasificacion NNSS y Nuevos Ámbitos. Se conservan en `documentos_sin_enlace`, sin construir URLs supuestas.

## Semántica y limitaciones

Cobertura parcial: inventario municipal actual de instrumentos, con documentos históricos y en tramitación; no es un historial exhaustivo ni un censo de obras públicas o licencias. No se afirma vigencia, aprobación ni ejecución de cada instrumento. Solo se asigna `fase: en tramitación` cuando el grupo municipal lo declara. Los documentos de borrador, información ambiental, alegaciones, memoria y planos permanecen agrupados, sin convertirse en actuaciones distintas.

No se extraen fechas de publicación, acuerdo o aprobación: las fechas en rutas, nombres de archivos, títulos o metadatos del CMS no bastan para establecer su significado. El año 1995 permanece en el título original. No se infieren coordenadas de la dirección de las oficinas ni de planos PDF. Todos los registros llevan `geometry_status: unavailable` y `publication_ready: false`. Manifest: licencias y programación desactivadas, sin jitter geográfico.

La descarga de documentos conserva las URLs HTTP originales del catálogo. Para verificar la muestra de MP24 se solicitó la misma ruta sobre HTTPS, registrando ambas URLs en la evidencia. Se comprobaron solo tres prefijos PDF; no se garantiza la disponibilidad del resto ni se interpretan sus contenidos. El método incremental actualiza una instantánea completa, sin historial de cambios o bajas.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_agost -v`, **5 correctas**. Comprueban agrupación de modificación/anexo, aislamiento entre sectores, deduplicación de enlaces fragmentados, etiquetas sin enlace, ausencia de fechas/coordenadas inferidas, rechazo de fuentes vacías/cambiadas/paginadas/externas, preservación del archivo anterior ante fallo y restricciones del manifest.

Ejecución real: `load_manifest('agost')`, `load_portal_adapter(manifest)`, `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. Se utilizó el registro compartido sin modificarlo; su anotación de entidades informó 21 registros, cero desconocidos, estado correcto. Sin publicación, base de datos, geocodificación o despliegue.

Evidencia local, fuera de los cuatro archivos fuente:

- `evidence/proyectos.jsonl`: los 21 registros reales.
- `evidence/validation.json`: fecha UTC de ejecución, runtime, recuentos, URLs, resultado del adaptador y limitaciones.
- `evidence/urbanismo.html`: captura del inventario utilizado por la ejecución viva.
- `evidence/document-{1,2,3}.pdf.prefix`: primeros 4096 bytes de memoria NNSS, modificación 17 y plano de localización MP24. Las tres respuestas fueron HTTP 200, `application/pdf`, firma `%PDF-` verificada; detalles de procedencia y transporte en `validation.json`.
