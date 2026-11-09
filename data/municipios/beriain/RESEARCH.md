# Beriáin — Navarra — INE 31905

Verificado el 9 de noviembre de 2026 usando el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento e inventarios oficiales

- Portal municipal: https://www.beriain.es/ . Su navegación enlaza el tablón,
  la sede electrónica y las actas municipales por años.
- Transparencia / planeamiento:
  https://www.beriain.es/transparencia/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/ .
  HTTP 200; enumera materias (PGOU, modificaciones, convenios), pero no enlaza
  expedientes ni documentos concretos. No se convierten esos rótulos en proyectos.
- Tablón web: https://www.beriain.es/actualidad/tablon/ . Explica expresamente que
  los anuncios oficiales anteriores a diciembre de 2020 están en esa sección y
  que los actuales se publican en la sede. Tiene 60 páginas: no se extrae ese
  archivo histórico ni se presenta su primera página como inventario completo.
- La API pública WordPress `/wp-json/wp/v2/posts?search=plan&per_page=100`
  devuelve 25 resultados y `X-WP-TotalPages: 1`; consultada solo para investigación.
  Hay anuncios antiguos del BON y también ordenanzas y contenidos ajenos al
  planeamiento. El adaptador no usa esta búsqueda como cobertura histórica.
- Fuente de extracción elegida:
  https://sedeelectronica.beriain.es/tablondeanuncios/ . HTTP 200, acceso público,
  todas las áreas, búsqueda vacía. Diez anuncios vigentes en una tabla HTML,
  sin controles de paginación observados. No requiere sesión ni credenciales.
  La sede identifica BERIÁIN, NIF municipal P3190590D.

## Registro real y semántica

Un estudio de detalle: expediente **336783E**.
Título literal: **APROBACION INICIAL ESTUDIO DETALLE 336783E**.

- Detalle descubierto en el inventario:
  https://sedeelectronica.beriain.es/tablondeanuncios/anuncio.aspx?id=27999
- PDF oficial descubierto en ese detalle:
  https://sedeelectronica.beriain.es/tablondeanuncios/documento.aspx?id=66510&modo=guardar
- Publicación/exposición desde **29/10/2026**, hasta **27/11/2026** según tabla.
  El detalle confirma la fecha inicial y muestra sello de tiempo de ese día.
- La fase «aprobación inicial» procede del título. La fecha del acuerdo y la
  fecha de aprobación no figuran en el HTML: permanecen nulas. No se interpreta
  el sello de publicación como fecha del acuerdo ni se declara aprobación definitiva.
- El PDF descargado es real (335734 bytes en la comprobación). `pdftotext`
  recupera el sello de publicación, título, SEFYCU 401608 y datos de verificación;
  el contenido sustantivo parece estar en imagen. No se infieren parcela,
  promotor ni fecha del acuerdo de fuentes secundarias.

Se conservan enlaces y procedencia de cada anuncio y documento. Los anuncios con
el mismo expediente se agrupan en un instrumento; los documentos no generan
proyectos independientes. El identificador estable depende del expediente, no
solamente del anuncio. El título y fase superiores corresponden al anuncio de
publicación más reciente; se retienen todos los anuncios observados en la instantánea.

## Cobertura parcial y límites

El adaptador cubre **solo estudios de detalle con identificador explícito de
expediente en el tablón actualmente publicado**. No cubre otros tipos de plan,
obras públicas, expedientes retirados del tablón, actas, ni el histórico de BON.
La actualización repite una instantánea del tablón, no un archivo incremental.
Un estudio sin identificador, un inventario vacío o un cambio de estructura
provoca error para revisión. No hay recorte por número de registros.
Si aparecen controles de paginación, enlaces de página o postbacks ASP.NET,
se falla explícitamente antes de escribir una salida parcial.

Se excluyen presupuestos, empleo, notificaciones fiscales, licitaciones y otros
anuncios ajenos. El tablón contiene una concesión de licencia de actividad de
bar-cafetería, pero **licencias.enabled=false** y no se extrae. Una licencia de
actividad tampoco se presenta como obra física. Los métodos de licencias
producen salida vacía y estado disabled.

`geometry_status: unavailable`. No se ha verificado geometría vectorial vinculada
al expediente en estas páginas; no se vectoriza el PDF, no se inventan coordenadas.
`lat`, `lon` y `geometry` nulos; `publication_ready=false`.
`geocode.jitter_missing=false`, `schedule.enabled=false`.
La anotación compartida de entidades queda `pendiente` por identidad insuficiente;
esta extracción no implica aceptación ni aptitud para publicación.

## Validación y evidencia local

Comando: `python -m unittest municipio.test_beriain -v`, con el runtime indicado.
Tres pruebas pasan: selección y exclusiones, fechas, documentos deduplicados,
rechazo de paginación/cambios de esquema, agrupación de anuncios por instrumento,
carga mediante manifest/registro y licencias deshabilitadas.

Se ejecutó `load_portal_adapter(load_manifest('beriain')).backfill_proyectos(...)`
contra la sede real, configurando únicamente el directorio local de capturas.
Resultado: **1 registro real, 1 PDF**. La descarga del PDF comprueba su cabecera.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (recuento, URLs, limitaciones), `evidence/inventory.html`,
`evidence/notice-27999.html` y `evidence/document-66510.pdf`, además de capturas de
investigación y texto del PDF. No se ejecutaron publicación, geocodificación,
sincronización, bases de datos ni herramientas de despliegue.
