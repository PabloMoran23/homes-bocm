# Peñarroya-Pueblonuevo — Córdoba — INE 14052

Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuente oficial y descubrimiento

La portada https://penarroyapueblonuevo.es/ enlaza «Ayuntamiento → Documentos»:
https://penarroyapueblonuevo.es/ayuntamiento/ayuntamiento-documentos/

Es un inventario documental municipal actual, servido íntegramente en HTML,
sin paginación observada. Dentro de `.entry-content`, el bloque
`.et_pb_text_inner` con h2 «Plan de movilidad urbana sostenible» contiene:

- Metodología y Trabajo de Campo:
  https://penarroyapueblonuevo.es/wp-content/uploads/2022/11/001_METODOLOGIA-TRABAJO_CAMPO_PMUS_Penarroya-Pueblonuevo__febrero-21_.pdf
- Diagnosis:
  https://penarroyapueblonuevo.es/wp-content/uploads/2022/11/002_DIAGNOSIS_PMUS_Penarroya-Pueblonuevo__febrero_21_.pdf
- Propuesta de actuación:
  https://penarroyapueblonuevo.es/wp-content/uploads/2022/11/003_PROPUESTAS_PMUS_Penarroya-Pueblonuevo__febrero-21_.pdf

Los tres volúmenes pertenecen a **un único PMUS**, instrumento de planificación
de movilidad urbana. No se generan tres proyectos ni se presentan sus propuestas
individuales como obras aprobadas. El título se toma del encabezado, y los
documentos y sus nombres de los enlaces del mismo bloque. La identidad estable
depende del inventario y título, no del orden de los documentos. Se deduplican
enlaces y se retienen todos los volúmenes presentes, sin límite arbitrario.

También se inspeccionó el portal oficial de transparencia enlazado desde la
portada: https://transparencia.penarroyapueblonuevo.es/publicidad-activa/ y
https://transparencia.penarroyapueblonuevo.es/seccion-portada/ii-informacion-sobre-planificacion-y-evaluacion/
Sus fichas «Planes y Programas…» e «Información precisa sobre los usos y destinos
del suelo» no mostraron documentos utilizables en el HTML consultado. No se
convierten esas fichas vacías en registros. Capturas locales conservadas.

## Cobertura y semántica

Cobertura deliberadamente parcial: exclusivamente el PMUS publicado en
«Documentos», no todo el planeamiento, todas las actuaciones ni un histórico de
obras municipales. El parser selecciona ese bloque exacto; excluye ordenanzas,
formularios, licitaciones de puestos del mercado y concesiones de explotación de
quioscos presentes en otros bloques. No se ha identificado un registro público
verificado de licencias concedidas: `licencias.enabled: false`.

No hay fecha explícita de publicación ni de acuerdo en este bloque. No se usan
las carpetas `2022/11`, los nombres `febrero-21` ni metadatos del CMS para
inventar fechas. No se afirma aprobación, vigencia legal ni ejecución. No se
asignan fases ni coordenadas. `publication_ready: false`,
`geometry_status: unavailable`, `schedule.enabled: false`,
`geocode.jitter_missing: false`.

La anotación compartida de entidades deja el instrumento en `pendiente` por
falta de referencia de expediente/acto acreditado; se conserva esa limitación,
sin inventar una referencia para superar la clasificación.

La ausencia del contenedor, del bloque o de documentos produce error. Si el
inventario incorpora paginación WordPress o enlaces de continuación reconocidos,
el adaptador falla expresamente para revisar la cobertura, en vez de entregar
una primera página silenciosamente. Actualizar vuelve a leer todo el inventario
acotado, sin filtros por fecha.

## Validación reproducible

Runtime usado en todas las comprobaciones:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_penarroya_pueblonuevo -v`: **6 tests correctos**.
Verifican agrupación, aislamiento frente a licitaciones/formularios, duplicados,
identidad estable, ausencia de fechas/coordenadas inferidas, fallos por inventario
vacío o paginado, restricción de enlaces oficiales y manifest/licencias.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`portal.config.evidence_dir = 'evidence'`: **1 registro real, 3 documentos**.
El adaptador verifica en vivo todos los enlaces: respuestas HTTP satisfactorias,
destino en dominio municipal y firma `%PDF-`. Solo se leen los primeros 1024
bytes por documento; no se ha interpretado el contenido íntegro de los PDFs.

Evidencias locales, ajenas a los cuatro archivos fuente:
`evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/inventory.html`, `evidence/pmus-1.pdf.prefix` a
`evidence/pmus-3.pdf.prefix`, además de capturas del descubrimiento.
La validación registra cantidad, URLs, limitaciones y resultado de la política
compartida. No se ejecutaron publicación, geocodificación, base de datos ni
herramientas de despliegue.
