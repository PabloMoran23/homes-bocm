# San Clemente, Cuenca — INE 16190

Investigación y extracción real: 9 de noviembre de 2026.

## Fuente oficial y descubrimiento

Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifests y los ejemplos de Hernani, Chipiona y Manlleu antes de implementar. El inventario elegido es la página municipal:

https://www.sanclemente.es/plan-de-ordenacion-municipal/

La web identifica el Ayuntamiento en Plaza Mayor, 10, San Clemente, 16600, Cuenca. La búsqueda también devuelve San Clemente de Chile: ese municipio y su dominio `.cl` quedan excluidos. La concejalía de urbanismo de la misma web es una descripción del servicio, no un registro de licencias concedidas:

https://www.sanclemente.es/urbanismo-desarrollo-industrial-comercio-transporte-y-seguridad-ciudadana/

El inventario del POM contiene cinco secciones en un único acordeón, sin paginación observada. Dos secciones del POM original remiten mediante texto a la modificación nº 1, sin enlaces documentales propios: no se crean registros duplicados del plan original. Las otras tres secciones corresponden a dos instrumentos:

- Modificación puntual nº 1: normas urbanísticas y planos, **23 documentos**, agrupados en un único registro.
- Modificación puntual nº 2: sección titulada «Información Pública», **2 documentos**: texto refundido de las modificaciones 1 y 2 alojado en Mega y publicación de aprobación definitiva en el BOP alojada en la Diputación de Cuenca. El texto refundido compartido permanece en su sección de procedencia, sin generar un tercer instrumento.

El parser extrae nombres de sección y enlaces reales del HTML; no devuelve registros precargados. Conserva los fragmentos de enlaces Mega. Cada documento conserva título, URL, sección y página de procedencia. Los identificadores estables se basan en el número de modificación municipal. Las nuevas modificaciones con el mismo formato se incorporan; secciones desconocidas, inventarios vacíos, cambios de estructura, hosts no revisados o aparición de paginación provocan error antes de reemplazar el resultado. El incremental refresca el inventario completo.

## Comprobación documental y límites

Se descargó y capturó el PDF municipal:

https://www.sanclemente.es/wp-content/uploads/2021/08/03.-NNUU-refundido_2020-1.pdf

HTTP 200, `application/pdf`, firma `%PDF-`, 1.695.190 bytes. Sus primeras páginas confirman «PLAN DE ORDENACIÓN MUNICIPAL DE SAN CLEMENTE», «NORMAS URBANÍSTICAS», «TEXTO REFUNDIDO TRAS LA MODIFICACIÓN PUNTUAL Nº1». No es una solicitud ni un anuncio de contratación.

El enlace BOP se conserva como documento del inventario oficial:

https://www.dipucuenca.es/documents/34525/ccd96ea6-edab-c40e-f745-418db9e94269

La petición directa devolvió **HTTP 403**; se guardó la respuesta y no se atribuyen al boletín datos no leídos. El texto refundido de Mega y los restantes planos no se descargaron ni se verificó individualmente su accesibilidad. La presencia del enlace municipal no acredita por sí sola la disponibilidad del archivo o la vigencia legal del instrumento.

Cobertura **parcial del inventario documental actual del POM**, no inventario completo histórico de planeamiento, obras públicas o expedientes municipales. Las secciones de la nº 2 mezclan el título «Información Pública» con un documento rotulado como aprobación definitiva: se conservan literalmente y no se infiere una fase uniforme. No se extraen fechas de publicación, acuerdo ni aprobación: son campos nulos; los años documentales y las rutas de subida no se convierten en fechas jurídicas. No se inventan geometrías ni coordenadas. `publication_ready` es falso. El cargador compartido anota ambos registros como `unknown` en su política de entidades; no se modifica esa política ni se afirma elegibilidad para actividad/publicación.

Licencias desactivadas: no se verificó un registro de concesiones. Impresos, noticias genéricas, ordenanzas y contratación no se convierten en proyectos. Programación desactivada y jitter de geocodificación desactivado en el manifest.

## Validación reproducible

Runtime requerido utilizado:

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_san_clemente -v`

**7 pruebas correctas**: agrupación y aislamiento documental, procedencia y fragmentos de URL, ausencia de fechas/geometrías inferidas, rechazo de formularios o cambios de inventario, paginación, documentos ausentes/hosts desconocidos, preservación de salida ante fallo y contrato del manifest/adaptador.

Extracción en vivo mediante `load_manifest('san-clemente')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 registros, 25 enlaces documentales**. Se configuró `capture_dir=evidence` solo en memoria para capturar la respuesta usada en la extracción. No se ejecutó publicación, geocodificación, sincronización ni acceso a bases de datos.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/planeamiento-live.html`, captura inicial `planeamiento.html`, `normas-mp1.pdf`, `normas-mp1-first-pages.txt` y `bop-mp2-response.html`. El informe incluye fecha de comprobación, conteos, URLs, resultado de pruebas y limitaciones.
