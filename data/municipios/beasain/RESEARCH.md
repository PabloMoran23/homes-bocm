# Beasain — INE 20019, Gipuzkoa

Verificado el 2026-11-07 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifests,
el registro y los ejemplos de Hernani, Manlleu y Chipiona antes de implementar.

## Descubrimiento y alcance

La página municipal de [información urbanística / documentos en vigor](https://www.beasain.eus/es/ayuntamiento-es/urbanismo/informacion-urbanistica)
enlaza los documentos del plan general, Udalgeo y las normas subsidiarias del
geoportal. Son fuentes municipales, no anuncios de contratación ni formularios.

- [Inventario documental del PGOU](https://www.beasain.eus/es/documentos-plan-general):
  fuente implementada. DOCman ofrece carpetas de información y diagnóstico,
  avance, exposición pública, primera aprobación inicial (enero 2023), segunda
  aprobación inicial (julio 2024) y aprobación provisional. Esos rótulos identifican
  versiones documentales; no se convierten en fechas exactas ni en un estado legal
  actual inferido. La web mantiene también documentos de fases anteriores.
- [Directorio Udalgeo](https://www.udalgeo.com/beasain/web/Archivos/Documentos/Documentos.aspx?Idioma=es):
  HTTP 200, texto «El directorio no contiene documentos» en la respuesta revisada.
  No se interpreta como ausencia de planeamiento municipal.
- [Geoportal — normas subsidiarias](https://www.geobeasain.net/es/urbanismo:39/normas-subsidiarias:m34):
  presenta capas cartográficas de ordenación, alineaciones, infraestructuras y
  clasificación del suelo. No se verificó una geometría vectorial asociable al PGOU.
- [Geoportal — proyectos](https://www.geobeasain.net/es/urbanismo:39/proyectos:s112):
  HTTP 200, sin registros de proyectos en el HTML examinado. No se descarta que
  funcionalidades dinámicas ofrezcan más información; no están cubiertas.

Cobertura **parcial municipal**: un único instrumento real, el PGOU de Beasain,
con todas las carpetas y páginas alcanzables del inventario documental seleccionado.
No pretende inventariar todos los planes vigentes, modificaciones, obras ni licencias.
No hay inventario verificado de licencias concedidas; `licencias.enabled: false`.

## Extracción y semántica

Recorrido de categorías DOCman y de todos los enlaces de paginación, deduplicando
páginas por URL y documentos por `data-id`. La identidad del instrumento es
`beasain-pgou`: memorias, planos, normativa, estudios ambientales y versiones
anteriores quedan como documentos de ese instrumento, nunca como proyectos nuevos.
Cada documento conserva título, ID municipal, URL de descarga, categoría y páginas
de procedencia. El enlace de descarga es el publicado por el ayuntamiento.

`fecha_publicacion` en cada documento procede de `time[itemprop=datePublished]`;
se conserva además el valor original en `source_datePublished`. Son metadatos de
publicación DOCman, no fechas de firma, acuerdo, concesión o aprobación. Las fechas
del instrumento permanecen nulas: no se traslada la fecha de un adjunto al plan.
No se interpreta el contenido de los PDF ni se afirma vigencia jurídica a partir
de la mera presencia en el inventario. Los enlaces y las versiones se retienen.

La extracción falla ante HTTP erróneo, redirección, estructura DOCman ausente,
identidad documental contradictoria, destino externo, paginación no interpretable,
inventario vacío o más de 250 páginas. Ese límite genera error, no truncamiento.
Solo se reemplaza el JSONL después de terminar el recorrido. `update_proyectos`
refresca esta misma instantánea completa; no utiliza una fecha incremental que
pudiera perder cambios en documentos antiguos.

## Resultado y evidencia local

Ejecución real del adapter: **1 instrumento, 278 documentos únicos y 45 páginas**.
La normativa particular de la fase provisional tiene dos páginas; se recorrieron
`limitstart=0` y `limitstart=50`, además de su URL inicial, sin duplicar adjuntos.
Los metadatos documentales publicados abarcan 2019-04-24 a 2026-09-08. Estas fechas
no representan el periodo de acuerdos o aprobaciones.

Se verificó además una descarga real: documento «01 SITUACION», HTTP 200,
`application/pdf` y cabecera `%PDF-`. El inventario conserva todos los enlaces;
no se descargaron íntegramente los 278 PDF.

Evidencia no destinada a commit, en `evidence/`:

- `proyectos.jsonl`: registro real y sus documentos agrupados.
- `validation.json`: recuentos, URLs, limitaciones, comprobación PDF, fecha UTC,
  resultado de pruebas, SHA-256 del JSONL y correspondencia URL/captura.
- `source-captures/*.html.gz`: las 45 respuestas HTML de la extracción en vivo.
- `probe-0.html` y `inventory-0.html` a `inventory-3.html`: descubrimiento municipal,
  geoportal e inventarios consultados.

Seis pruebas offline pasan con `python -m unittest municipio.test_beasain -v`:
metadatos y categorías, paginación completa/rechazo de controles desconocidos,
cambios de estructura y enlaces externos, agrupación/deduplicación en recorrido,
conservación de la instantánea ante fallo y manifest/licencias deshabilitadas.
Los datos sintéticos de esas pruebas no se usan como evidencia de registros reales.

## Geometría y operación

`geometry_status: unavailable`, `publication_ready: false`. No se extraen puntos
ni polígonos del visor y no se inventan coordenadas o CRS. Los planos PDF no son
geometría verificable para ingestión. `geocode.jitter_missing: false` y
`schedule.enabled: false`. Sin dependencias nuevas, cambios compartidos, bases de
datos ni publicación; solo los cuatro ficheros fuente de Beasain.
