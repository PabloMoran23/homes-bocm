# Hernani — INE 20040

Verificado 2026-11-07. Inventario municipal de anuncios urbanísticos **en vigor**.

## Fuente y alcance

https://www.hernani.eus/es/urbanismo-medioambiente-vigor — HTTP 200.
Descubierto desde Urbanismo y medioambiente, enlace «Ver todos» de anuncios vigentes.
Se leen títulos/fechas de cada fila Liferay, se siguen los detalles descubiertos y
se incorporan los documentos oficiales. No se fija una noticia individual como seed.
Se acota a reparcelaciones, planes especiales, estudios de detalle y modificaciones.
No incluye anuncios medioambientales de actividad clasificada ni histórico finalizado.

Extracción directa: **1 expediente real**, proyecto de reparcelación (HM) KA.03.3,
publicado 2026-11-02, con **5 documentos** oficiales de anuncio/proyecto/publicaciones.
La fecha es la de publicación municipal, no de concesión. Los documentos no generan
proyectos adicionales. IDs de contenido Liferay, sin query de redirección variable.
0 licencias: no se ha verificado concesión y los métodos devuelven vacío.

No existe paginación activa en la página revisada. Si aparece un enlace «Siguiente»
el extractor falla explícitamente hasta implementar su recorrido, evitando aceptar
una instantánea truncada. También falla ante pérdida de registros o documentos.
El estado vacío futuro del tablón requiere revisión; no equivale automáticamente a
una pérdida de todos los expedientes previamente recogidos.

## Geometría / visor

geometry_status: unavailable

La navegación municipal enlaza callejero/cartografía:
http://herrigis.gis-cdn.net/hernani/
Los detalles urbanísticos examinados ofrecen documentos PDF, sin geometría asociada
por identificador de expediente. No se ha verificado una capa vectorial enlazable a
KA.03.3, ni se han vectorizado PDFs. No se inventan coordenadas ni CRS.

## Validación

2 pruebas pasan: deduplicación de ID, fecha publicada, URL canónica y rechazo de
paginación no cubierta/contenido ausente. Extracción directa con timeout25s y pausa
0,35s. Evidencias en `/home/pablo/homes/artifacts/municipio-local-batches-20261107/hernani/`.
`schedule.enabled: false`, licencias deshabilitadas y `geocode.jitter_missing: false`.
Sin orquestador, DB, cola o publicación. Falta geometría para validar publicación.
