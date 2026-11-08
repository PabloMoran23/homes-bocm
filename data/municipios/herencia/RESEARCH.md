# Herencia — Ciudad Real — INE 13047

Investigación y extracción: 8 de noviembre de 2026. Adaptador único:
`municipio.adapters.herencia:HerenciaAyuntamientoAdapter`.

## Inventario oficial y descubrimiento

La portada https://herencia.es/ identifica el portal del Ayuntamiento de Herencia
(Ciudad Real). Se revisaron las dos páginas de transparencia enlazadas:
https://herencia.es/portal-de-transparencia y
https://herencia.es/ayuntamiento/portal-de-transparencia . Contienen documentación
institucional y retribuciones, pero no proporcionan aquí un registro de licencias
concedidas ni un inventario utilizable de proyectos. La página de ordenanzas
https://herencia.es/ayuntamiento/ordenanzas-y-reglamentos-municipales publica
reglamentos, que se excluyen. La búsqueda también localizó documentos del POM en
`/wp-content/uploads/2018/03/`, pero no se ha establecido su vigencia ni una ficha
actual completa; no se convierten en proyectos separados ni se usan en el scraper.
El buscador REST `/wp-json/wp/v2/search` respondió 401 y el sitemap antiguo
`/sitemap.xml` estaba fechado en 2011; ninguno constituye cobertura actual.

La fuente implementada es el archivo municipal vivo **Obras y Urbanismo**:
https://herencia.es/seccion/noticias/obras-urbanismo . Publica informes de obras
físicas concretas, junto con otras noticias y anuncios que deben filtrarse.
No se extrae una actuación sintética a partir de la página de categoría.

## Paginación y extracción

El tema Magazinevibe sirve dos noticias destacadas y un bloque de 18 entradas,
con `data-category_id=15`, `data-offset=2` y `data-max_pages=11`. Las rutas
`/page/2` no avanzan este bloque. Se inspeccionó el JavaScript oficial
https://herencia.es/wp-content/themes/magazinevibe/assets/js/modules.min.js
para reproducir únicamente su consulta de lectura: POST a
https://herencia.es/wp-admin/admin-ajax.php con
`action=magazinevibe_edge_list_ajax`, los atributos del bloque y `paged=N`.
Se recorren todas las páginas anunciadas, sin límite oculto ni parada por fecha.
Una página vacía, repetida, respuesta negativa o estructura desconocida provoca
error antes de reemplazar el fichero de salida. Se deduplican URLs de noticias.

El alcance temático es **parcial y conservador**: titulares de intervenciones
físicas reconocibles (renovación, ejecución, reapertura, restauración, riego,
instalaciones solares e inicio de obras), con publicación desde **2026-01-01**.
Cada candidata se consulta en su ficha oficial; el título, fecha de publicación,
texto y enlaces proceden de ella. No se pretende cubrir todas las obras, todas
las noticias municipales, el histórico anterior a 2026 o todo el planeamiento.
Los patrones no constituyen una clasificación universal de noticias futuras.

Resultado de la versión final: **8 actuaciones, 11 reportes seleccionados,
200 entradas examinadas en 11 páginas**. Actuaciones documentadas:

- Instalación solar en la estación depuradora.
- Rehabilitación de la fase II de la Hospedería/Casa de los Frailes.
- Actuaciones medioambientales y patrimoniales de la Pedriza: senderos,
  mobiliario y restauración del depósito de la Copa.
- Instalación solar y climatización del Colegio Público Nº2.
- Modernización de la red de riego de parques y jardines.
- Semipeatonalización de la calle Concepción.
- Modernización hidráulica en Avenida de Alcázar.
- Renovación del Parque de Castilla-La Mancha.

Los informes de inicio y reapertura de Concepción representan una actuación.
El informe de financiación de la Pedriza explica expresamente que incluye la
restauración de la Copa; sus tres reportes se agrupan sin perder sus textos,
fechas ni enlaces. La noticia de la CM-3167 se excluye porque anuncia autorización
de inversión **para licitar las obras**, aunque el titular diga «Se renueva».
Se excluyen modelos de licencia, bolsas de empleo, balances, venta de parcelas
y anuncios de licitación/adjudicación. La financiación de la Pedriza se admite
porque documenta trabajos efectivamente realizados, no solo la ayuda.

## Semántica, límites y ejecución

`fecha_publicacion` significa publicación de la noticia municipal, extraída de
`article:published_time`; no representa acuerdo, aprobación, licencia o inicio
material. En grupos es la primera publicación y cada reporte mantiene su fecha.
No se infieren fases, fechas de acuerdo/aprobación, importes estructurados ni
coordenadas. Los textos se conservan como `descripcion` de cada reporte.
`documentos` identifica noticias municipales y posibles PDFs enlazados desde su
cuerpo; una noticia no se presenta como proyecto técnico ni resolución jurídica.
No se descargan masivamente expedientes adjuntos ni se extrae texto de PDFs.
Los IDs derivan de la URL o de la actuación agrupada y no del orden de extracción.

`publication_ready=false`, `geometry_status=unavailable`. Manifest con
`licencias.enabled=false`, `schedule.enabled=false` y
`geocode.jitter_missing=false`. No hay un registro verificado de concesiones.
El método incremental vuelve a extraer el inventario acotado sin simular un delta.

Runtime utilizado (sin instalaciones):
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_herencia -v`, **8 correctas**.
Cubren selección/exclusión, documentos, fechas, agrupación de reportes,
estructuras vacías y rechazo de paginación repetida sin destruir una salida previa.
Extracción real mediante `HerenciaAyuntamientoAdapter.backfill_proyectos`, sin
base de datos, geocodificación ni publicación. Evidencia local no destinada a
commit: `evidence/proyectos.jsonl`, `evidence/validation.json` y
`evidence/captures/` (HTML inicial, diez respuestas AJAX y fichas consultadas).
La validación incluye recuentos, URLs, limitaciones y fecha de ejecución.
