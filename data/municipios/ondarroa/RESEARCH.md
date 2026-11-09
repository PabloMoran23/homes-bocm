# Ondarroa — INE 48073, Bizkaia

Verificación directa: 2026-11-08. Adaptador con cobertura parcial de planeamiento
portuario. No es un registro de licencias ni un inventario completo de obras.

## Fuentes oficiales descubiertas

- Ayuntamiento: https://www.ondarroa.eus/es-ES/Paginas/default.aspx
  Responde HTTP 200 con una carcasa SharePoint casi sin contenido ni navegación
  urbanística en el HTML recibido. Captura `evidence/home.html`. No se extraen
  proyectos de esa respuesta ni se interpreta como ausencia de expedientes.
- Inventario del Gobierno Vasco, **Planes urbanísticos**:
  https://www.euskadi.eus/gobierno-vasco/-/planes-urbanisticos/
  HTTP 200. Lista territorial con secciones GIPUZKOA y BIZKAIA; dentro de BIZKAIA,
  Ondarroa tiene dos enlaces PDF. Esta es la fuente implementada. Se descubre la
  sección por municipio y provincia y se recogen todos sus enlaces, sin fijar
  los nombres de archivo ni un número máximo de documentos.
- Catálogo de la Diputación Foral:
  https://www.opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-ondarroa
  HTTP 200, captura `evidence/bizkaia.html`. Ofrece datos globales de planeamiento
  2023–2026 y 2019–2022 y calificación pormenorizada 2019–2022; advierte de su
  carácter orientativo. No se convierten entradas del catálogo en proyectos.
  El hostname sin `www` presentó un error de certificado; la URL con `www`
  funcionó manteniendo la verificación TLS.
- Expediente ambiental del PGOU EAED-135INET:
  https://www.euskadi.eus/eaed-135inet-evaluacion-ambiental-estrategica-ordinaria-del-plan-general-de-ordenacion-urbana-de-ondarroa/web01-sedeopec/es/
  HTTP 200, captura `evidence/environment.html`. Enlaza borrador y documentación
  inicial; su última modificación editorial indica 11/03/2021. Se descubrió como
  fuente adicional, pero no forma parte de la cobertura implementada. Esa fecha
  no se asigna como aprobación del PGOU.

## Extracción y semántica

La ejecución real produce **1 instrumento**, «Plan especial del puerto de
Ondarroa», con **2 documentos** agrupados según la sección municipal del índice:

- «PE original de 1990 (PDF, 241 MB)»:
  https://www.euskadi.eus/contenidos/informacion/puertos_planes_urbanisticos/es_def/adjuntos/Plan_Especial_Ondarroa-1990-Julio.pdf
- «Modificación nº1 de 2009 (PDF, 44 MB)»:
  https://www.euskadi.eus/contenidos/informacion/puertos_planes_urbanisticos/es_def/adjuntos/Plan_Especial_Ondarroa-2009-Marzo.pdf

No se generan dos proyectos por ser dos PDFs. Cada documento conserva etiqueta,
URL, publicador y URL de inventario de procedencia. El identificador del plan es
estable aunque se añadan versiones. Se deduplican enlaces idénticos y fragmentos.
La provincia se comprueba antes de extraer y los otros municipios se excluyen.

El índice está accesible actualmente, pero no acredita por sí solo la vigencia
jurídica de cada versión. Los años se conservan en las etiquetas documentales;
no se transforman en fechas completas. `fecha`, `fecha_publicacion`,
`fecha_acuerdo` y `fecha_aprob` son nulas. No se infiere fase administrativa ni
concesión de licencia. La procedencia del registro es `gobierno_vasco`; el valor
`proyectos.source: ayuntamiento` del manifest selecciona la vía del adaptador
de portal conforme al esquema compartido, no atribuye autoría al ayuntamiento.

El índice revisado no tiene paginación. Si aparece navegación «siguiente» o
`rel=next`, el adaptador falla antes de escribir la instantánea. También falla
si faltan título, sección, provincia, documento original o enlaces válidos.
No hay límite de documentos ni corte silencioso de la lista municipal.
Las actualizaciones vuelven a leer el inventario completo; no usan un cursor ni
afirman recuperar versiones retiradas del índice.

Se verifican en cada extracción las cabeceras `%PDF-` mediante peticiones Range
de 2048 bytes; ambas devolvieron HTTP 206. No se descargaron ni analizaron los
PDFs completos (aproximadamente 241 y 44 MB). Las capturas `.prefix` son solamente
prefijos, no PDFs completos. `document_checks.json` conserva URL, estado HTTP,
Content-Range, longitud capturada y hash del prefijo.

## Geometría y límites

`geometry_status: unavailable`. El índice usado enlaza documentos, sin geometría
vectorial por identificador de plan. No se han vectorizado planos ni verificado
capas GIS enlazables al expediente. `lat`, `lon` y `geometry` son nulas,
`publication_ready: false`, y `geocode.jitter_missing: false`.

No cubre NNSS, todo el PGOU, otras modificaciones municipales, proyectos de
urbanización ni obras públicas ajenas al plan portuario. No se han extraído
noticias, formularios o anuncios de contratación como proyectos o licencias.
`licencias.enabled: false`; los métodos de licencias escriben salida vacía con
estado `disabled`. `schedule.enabled: false`.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_ondarroa -v` — **5 pasan**. Comprueban
agrupación, exclusión territorial, procedencia, fechas y geometría nulas,
identidad estable, nuevas versiones, deduplicación, rechazo de paginación,
contenido ausente o enlaces externos, conservación de salida ante un fallo de
red, licencias deshabilitadas y manifest.

Extracción real: `OndarroaAyuntamientoAdapter('ondarroa', config={'evidence_dir':
'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **1 registro, 2 documentos**. Evidencia local en
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/ports.html`,
`evidence/document_checks.json` y prefijos de documentos. La evidencia no se
incluye entre los cuatro archivos fuente y no se añade a Git.
