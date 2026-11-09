# Villanueva de los Infantes — Ciudad Real — INE 13093

Investigación y extracción real: 9 de noviembre de 2026. Portal oficial: https://infantes.org/ (Ayuntamiento de Villanueva de los Infantes, Ciudad Real; no el municipio homónimo de Valladolid).

## Fuentes descubiertas y alcance

La sección https://infantes.org/urbanismo/ enlaza cuatro inventarios:

- https://infantes.org/planes-de-ordenacion-urbanistica-instrumentos-de-apoyo-y-ordenanzas-de-edificacion/ — tabla de once filas con instrumentos, referencias de publicación y enlaces documentales. Es la fuente implementada.
- https://infantes.org/tramites-de-informacion-publica/ — cinco filas sobre Paseo Cooperativas, UE-24b y Montón de Tierra, con proyectos de urbanización/reparcelación y un convenio. Inventario localizado y capturado, fuera del alcance de este adaptador.
- https://infantes.org/convenios-urbanisticos/ — tres convenios sobre UE-24b, Paseo de las Cooperativas y prolongación de Ramón Giraldo. Localizado y capturado, fuera del alcance.
- https://infantes.org/planes-y-proyectos-sujetos-a-impacto-ambiental/ — declara que actualmente no hay proyectos o planes publicados. Capturado; no genera un registro sintético.

El adaptador extrae **8 instrumentos/versiones y 14 enlaces documentales** de la primera tabla: revisión NNSS de 1996 expresamente derogada, catálogo de bienes protegidos, modificaciones puntuales números 1, 2, 3 y 4, texto refundido de las NNSS y Plan Parcial de Mejora SAUI-11 «QUIÑON INDUSTRIAL». Excluye declaración de conjunto histórico artístico y las dos ordenanzas independientes. No extrae formularios, anuncios de contratación o noticias como proyectos o licencias.

Cada fila seleccionada representa un instrumento o versión documental, agrupando normativa, planos y anuncio cuando existen. Los enlaces repetidos dentro de una fila se deduplican conservando sus referencias y columnas. Las dos versiones de las NNSS conservan filas distintas: la antigua está expresamente marcada como derogada. Las modificaciones numeradas son instrumentos separados, aunque compartan ámbito industrial. No se afirma que cada registro equivalga a una obra ejecutada ni que todos estén vigentes.

## Procedencia y semántica

`inventory_url` identifica la tabla; `url` es su primer documento y `documentos` conserva todos los enlaces publicados con texto y columna. `celdas_fuente` retiene la transcripción de cada celda. En la fila del texto refundido el CMS coloca la referencia DOCM en «Planos» y el enlace al texto en «Fecha de publicación»; se recogen los documentos de todas las celdas y se buscan las referencias bibliográficas en las tres celdas posteriores al título.

`fecha_publicacion` sólo se emite cuando existe una única fecha bibliográfica. `fechas_publicacion` conserva las dos publicaciones de la modificación 3; no se escoge una arbitrariamente. La mención de derogación en el título no se convierte en fecha de publicación. No se deducen fechas de aprobación, acuerdo, fase, coordenadas o geometría de las rutas de carga, fechas del CMS o títulos. Las referencias de la tabla se transcriben sin validar su exactitud jurídica contra todos los boletines originales. Los documentos no se analizan íntegramente.

Cobertura parcial: inventario actualmente publicado de planeamiento, incluyendo una versión histórica. No es un registro exhaustivo de obras, expediente histórico completo o registro de licencias concedidas. `licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`, registros con `publication_ready=false` y `geometry_status=unavailable`.

## Paginación y fallos

La tabla observada está íntegramente en el HTML, sin paginación ni controles de carga dinámica; se recorren todas sus filas sin límite artificial. El adaptador falla ante paginación conocida, controles dinámicos, cambio de esquema, instrumentos sin documentos, redirección inesperada o ausencia de instrumentos reconocidos. La actualización vuelve a obtener la tabla completa, sin cortes por fecha ni estado incremental ficticio.

Se comprobaron los prefijos de los 14 documentos enlazados. Trece devolvieron HTTP 200/206 y firma `%PDF-`. El enlace de normativa de la modificación 3 termina literalmente en `.pd` y devuelve 404:
https://infantes.org/wp-content/uploads/2021/09/06-normativa-04-MP3-NNSS-UE-24-normativa.pd

Se conserva sin inventar una URL corregida. El documento de planos de ese instrumento sí respondió como PDF. El fallo queda registrado en `evidence/validation.json`; no impide recuperar el instrumento del inventario oficial. La comprobación lee sólo 1024 bytes por documento y no certifica su contenido completo.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_villanueva_de_los_infantes -v` — cinco pruebas correctas: agrupación y exclusiones, columnas desplazadas, deduplicación documental, versiones históricas, fechas múltiples/ausentes, identidad estable, fallos ante cambios o paginación y contrato de backfill/actualización/licencias desactivadas.

Extracción en vivo mediante `VillanuevaDeLosInfantesAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `config={'capture_dir': 'evidence'}`. Resultado real: **8 registros**. Evidencia local no destinada a commit: `proyectos.jsonl`, `validation.json`, captura HTML de planeamiento, índice de urbanismo y tres inventarios adicionales, prefijos documentales y salida de pruebas, todos bajo `evidence/`. Sin base de datos, publicación, geocodificación ni ejecución programada.
