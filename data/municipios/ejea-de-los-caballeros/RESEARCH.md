# Ejea de los Caballeros — Zaragoza — INE 50095

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente oficial y selección

Fuente implementada: https://www.ejea.es/areas/urbanismo/ del Ayuntamiento de
Ejea de los Caballeros. Su sección «Planeamiento» publica un inventario documental
estructurado: Plan general, Modificaciones PGOU, Planes parciales y Planes especiales.
Los archivos se alojan en `https://st1.ejea.es/media/`, enlazados directamente por
el Ayuntamiento. El inventario incluye una modificación identificada como 2022
con archivo en una ruta de junio de 2026; se descubre el enlace actual en cada
ejecución, sin fijar una antigua copia del catálogo.

Se localizó también https://www.ejea.es/noticias-sobre/urbanismo/ durante la
búsqueda. No se utiliza: es un archivo de noticias, no un registro de instrumentos.
La fuente implementada contiene además «Solicitudes» con impresos de licencia y
declaraciones responsables, que no acreditan concesiones. No se ha verificado un
registro público de licencias concedidas; `licencias.enabled` es false.

## Unidad de registro y cobertura

Extracción actual: **19 instrumentos, con 41 enlaces PDF**:

- Un PGOU con 21 documentos: memoria, prescripciones, estudio económico,
  ordenanzas, normas, planos generales y de los pueblos, y catálogo.
- Once modificaciones del PGOU identificadas en el inventario entre 2004 y 2022;
  las dos partes de la modificación 1/2007 se agrupan en un solo registro, igual
  que las dos partes de la modificación 2/2010. Son 13 documentos de modificaciones.
- Cuatro planes parciales: sectores 1 Luchan, 3 Aquagraria, 6 Valdeferrín y
  8 Valdeferrin Oeste.
- Tres planes especiales: Casco Histórico, Boalares El Gancho y SU 1 Heinz.

Cada documento conserva título literal, URL, página de procedencia y sección.
El PGOU tiene un título descriptivo construido a partir de la cabecera «Plan
general» y del municipio. `url` señala el primer documento del instrumento;
`inventory_url` y los `source_url` documentales señalan el catálogo municipal.
Los IDs dependen del nombre normalizado del instrumento, no de la ruta de subida.
Se conservan todos los enlaces distintos; los enlaces repetidos se deduplican
dentro de cada instrumento. Los planos de cada pueblo son partes del PGOU del
municipio 50095, no municipios nuevos.

La sección se sirve completa en una sola página, sin paginación observada.
El parser recorre desde «Planeamiento» hasta la siguiente cabecera h2; no aplica
un límite de registros. Rechaza paginación explícita, controles de cargar más,
secciones nuevas no revisadas, enlaces no documentales o externos inesperados y
la desaparición del inventario. La actualización vuelve a extraer el inventario
completo; no supone disponer de un historial incremental.

## Semántica y límites

Cobertura parcial: inventario documental municipal visible actualmente. No
acredita la integridad histórica del planeamiento, la vigencia jurídica de los
instrumentos, ni su fase de tramitación. No incluye obras difundidas en noticias,
licitaciones, ni expedientes que no aparezcan en esta sección. El contenido
completo de los PDFs no se interpreta.

Los años incluidos en los títulos identifican modificaciones; no se convierten
en fechas de acuerdo, aprobación o publicación. Tampoco se utilizan las rutas
de subida del CMS como fechas. Se omiten `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` por falta de datos explícitos verificados.
No se inventan coordenadas ni se utilizan los vértices de la sección Topografía
para localizar instrumentos. Los registros declaran `geometry_status: unavailable`
y `publication_ready: false`; `schedule.enabled` y `geocode.jitter_missing` son false.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ejea_de_los_caballeros -v`
— cuatro pruebas correctas. Verifican agrupación, separación de instrumentos,
procedencia, exclusión de solicitudes y topografía, ausencia de fechas y
coordenadas inferidas, IDs estables, deduplicación, errores ante cambios y
paginación, carga del manifest y contrato de actualización. Un error de parser
conserva el resultado previo.

Se ejecutó `load_portal_adapter(load_manifest('ejea-de-los-caballeros'))` seguido
de `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura HTML
activada mediante la configuración local `evidence_dir`. Resultado: 19 registros;
la anotación compartida de entidades clasificó los 19 sin desconocidos.

También se comprobaron los 41 enlaces PDF con peticiones HTTP en streaming:
todos respondieron HTTP 200 con firma `%PDF-`. Se leyeron únicamente los primeros
1024 bytes de cada archivo; esto comprueba disponibilidad y formato, no el
contenido completo ni sus fechas jurídicas.

Evidencia local, excluida de los archivos fuente:

- `evidence/proyectos.jsonl`: registros de la ejecución real.
- `evidence/validation.json`: recuentos, fuentes, limitaciones y validación.
- `evidence/urbanismo.html`: captura del inventario usado por el adaptador.
- `evidence/document_checks.json`: resultado de las 41 comprobaciones documentales.
- `evidence/pdf-prefix-0.bin`, `pdf-prefix-33.bin`, `pdf-prefix-38.bin`: muestras
  de los primeros bytes de Memoria, modificación 1/2022 y Plan Especial del Casco
  Histórico respectivamente; no son PDFs completos.
- `evidence/proyectos.entities.json`: informe local de la política compartida.

No se ha ejecutado ninguna publicación, sincronización, geocodificación ni tarea
programada. La aceptación queda pendiente de revisión independiente.
