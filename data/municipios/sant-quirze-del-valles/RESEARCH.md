# Sant Quirze del Vallès — INE 08238

Verificado 2026-11-07. Alcance: expedientes de planeamiento/gestión en exposición pública.

## Fuente

https://www.santquirzevalles.cat/ajuntament/informacio-administrativa/exposicio-publica/planejament-i-gestio-urbanistica
HTTP200. Inventario Plone actual; se descubren fichas de planes/modificaciones/
proyectos/estudios y se descargan descripción y adjuntos oficiales. Se excluyen
solicitudes genéricas y enlaces de alegaciones. Hay soporte `listingNext`/rel-next
con límite20 páginas y rechazo de bucles; en esta prueba la lista tiene una página.

**1 expediente real, 8 documentos, 0 licencias:** Pla de Millora Urbana PMU03 Can
Ponsic, expediente10/2026/PLA. El texto oficial acredita acuerdo de Junta de Gobierno
2026-10-20 y publicación BOPB2026-11-03, que se conservan en campos distintos.
No se inventa fecha por rutas de archivos. El período de información pública no
se convierte en licencia ni en estado permanente del proyecto.

No cubre el histórico aprobado/finalizado ni todo el POUM vigente. Los PDF se
conservan como enlaces, sin descargar los45MB del documento principal durante prueba.

## Geometría / visor

geometry_status: unavailable

La página de planeamiento vigente enlaza Geoportal provincial municipal:
https://sitmun.diba.cat/idelocals/?id=08238&id=08238
https://www.santquirzevalles.cat/la-vila/geoinformacio-planols
No se verificó geometría vectorial inequívocamente asociada al PMU03 en los adjuntos
HTML ni un endpoint con su identificador. No se vectorizaron PDFs ni se inventaron
coordenadas. Queda pendiente consultar cartografía y vincular ámbito/documento.

## Validación

Dos tests pasan: inventario real frente a formulario y fallo ante estructura ausente.
Import/check estático válidos. Extracción directa timeout25s, pausa0,35s; JSONL e informe
en `/home/pablo/homes/artifacts/municipio-local-batches-20261107/sant-quirze-del-valles/`.
`schedule.enabled: false`, licencias deshabilitadas, `geocode.jitter_missing: false`.
No se ejecutaron orquestador, DB, publicación ni cola. Falta geografía para publicar.
