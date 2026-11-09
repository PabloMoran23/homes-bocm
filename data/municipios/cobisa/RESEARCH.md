# Cobisa — Toledo — INE 45052

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

- Web municipal: https://cobisa.es/ . Identifica Ayuntamiento de Cobisa y dirección Plaza de la Concordia, 1, 45111 Cobisa, Toledo; enlaza su sede electrónica.
- Inventario de noticias: https://cobisa.es/noticias/ y API pública https://cobisa.es/wp-json/wp/v2/posts . La API devuelve contenido íntegro, identificador, enlace y fecha de publicación de cada noticia.
- Inventario de páginas: https://cobisa.es/wp-json/wp/v2/pages?per_page=100 . En la consulta exploratoria devuelve 23 páginas, sin sección específica de planeamiento; no se usa como inventario de proyectos.
- Transparencia: https://cobisa.sedelectronica.es/transparency . La categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» muestra un elemento. Su enlace depende de una llamada Wicket con sesión; el intento de expansión HTTP devolvió cuerpo vacío. No se ha inspeccionado ese documento y no se declara cubierto. No se confunde el catálogo de trámites con licencias otorgadas.

La extracción implementada usa exclusivamente el inventario actual de noticias municipales. Es cobertura **parcial de obras físicas realizadas**, no un inventario exhaustivo de planeamiento, obras, contratación o licencias. No garantiza noticias anteriores a la web actual. Las referencias de buscadores a otros expedientes históricos no se incorporan sin inventario y documentación verificados.

## Resultado real

Consulta del adaptador: https://cobisa.es/wp-json/wp/v2/posts?per_page=100&page=1&orderby=id&order=asc . HTTP 200; `X-WP-Total: 13`, `X-WP-TotalPages: 1`. Trece noticias examinadas, **una obra extraída**:

https://cobisa.es/cobisa-amplio-las-gradas-del-polideportivo-municipal/

«Cobisa amplió las gradas del polideportivo municipal», ID WordPress 1476. El cuerpo describe expresamente la ampliación del graderío realizada por el Ayuntamiento y financiación LEADER. La ficha HTML se comprobó también directamente. Se conserva el cuerpo como `descripcion` con su procedencia, sin convertir la subvención en licencia ni inventar presupuesto.

Las otras noticias actuales son eventos culturales, horarios y una licitación de parcelas, entre otras. La licitación y sus pliegos no son una obra ejecutada y se excluyen.

## Extracción y semántica

`parse_post` interpreta título y cuerpo HTML devueltos por REST. Exige una intervención física en el título (ampliación, reforma, rehabilitación, renovación o pavimentación), un elemento material (gradas, graderío, polideportivo, pabellón, calle, acera, parque, alumbrado o saneamiento) y declaración explícita en el cuerpo de ejecución por el Ayuntamiento de Cobisa. Es una selección conservadora: otras expresiones y clases de obra pueden quedar fuera y requieren ampliar el parser con verificación. Se excluyen títulos de contratación, licitación, formularios/licencias y teatro. No hay lista precargada de expedientes ni registro sintético cuando falla la fuente.

Se recorren todas las páginas anunciadas por REST en orden estable de ID. Se exige que totales no cambien, que no se repitan IDs y que el número de entradas leídas coincida con el total. Un inventario vacío, sin obras compatibles, incompleto o inconsistente genera error antes de reemplazar la salida. Las actualizaciones repiten la instantánea completa; no usan fechas del estado para recortar resultados.

Cada obra seleccionada conserva su enlace y enlace API; la noticia y sus adjuntos PDF se agrupan en `documentos`, deduplicados por URL. En el registro observado hay una noticia sin proyecto técnico adjunto; no se han encontrado varios documentos de un mismo instrumento en esta cobertura. No se extraen instrumentos urbanísticos desde este origen.

`fecha_publicacion: 2026-08-25` procede de `date` de WordPress y coincide con la ficha visible. `modified` es una actualización del CMS y no se usa como aprobación. No constan fechas de acuerdo, aprobación ni ejecución exacta: se omiten. No se infiere una fase administrativa. No se aportan coordenadas. `publication_ready: false`, `geometry_status: unavailable`. Licencias, programación y jitter desactivados en el manifiesto. El cargador compartido añade `_entity_policy` con identidad pendiente; no se fuerza su aceptación ni elegibilidad.

## Validación y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_cobisa -v`: **6 pruebas correctas**. Cubren procedencia de fecha, obra física, exclusiones, agrupación documental, recorrido multipágina, totales cambiantes/incompletos, duplicados, salida atómica y manifiesto/licencias desactivadas.

Extracción real mediante `load_manifest("cobisa")`, `load_portal_adapter(...)` y `backfill_proyectos(Path("evidence/proyectos.jsonl"))`, sin publicación ni base de datos. Resultado: una fila sobre 13 noticias y una página. La ejecución conserva:

- `evidence/proyectos.jsonl`: registro real y anotación compartida de entidad.
- `evidence/validation.json`: `live_records`, URLs, hora UTC, límites, estadísticas, pruebas y SHA-256 de la captura REST.
- `evidence/live-posts-1.json`: respuesta exacta de la ejecución del adaptador.
- `evidence/gradas.html`, `home.html`, `posts-1.json`, `pages.json`, `transparency.html` y `transparency-urbanismo.xml`: capturas de investigación.

La evidencia queda local, fuera de los cuatro archivos fuente entregables. El estado ready indica implementación y extracción verificadas para este alcance parcial; la aceptación corresponde a revisión independiente.
