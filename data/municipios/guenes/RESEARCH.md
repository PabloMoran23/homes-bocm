# Güeñes — Bizkaia — INE 48045

Comprobación en vivo: 2026-11-09. Adaptador exclusivo para Güeñes.

## Descubrimiento y fuentes

- Ayuntamiento: https://www.guenes.eus/ redirige a
  https://www.guenes.eus/es-ES/Paginas/default.aspx (HTTP 200). El HTML obtenido
  no aporta un inventario de urbanismo utilizable. Captura: `evidence/home.html`.
- Catálogo oficial: https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-guenes
  ofrece datos globales 2023–2026, históricos 2019–2022 y calificación pormenorizada.
  Se comprobó el JSON global: son magnitudes estadísticas por trimestre, no
  instrumentos identificados. Se excluye de la extracción. Capturas:
  `evidence/catalog.html`, `evidence/global.json`.
- La página temática oficial https://www.bizkaia.eus/es/urbanismo enlaza
  «Registro de Planeamiento Urbanístico», descrito como planes vigentes de los
  municipios y su documentación:
  https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador .
  El formulario identifica `45` como `GUEÑES`; corresponde a INE 48045, Bizkaia.
  El adaptador descubre el namespace del formulario y consulta ese municipio,
  todos los tipos (`-1`), sin filtro de texto. No depende de una noticia elegida.

## Cobertura y semántica

La consulta devuelve **14 instrumentos**, todos con estado registral «Vigente».
Las fechas de resolución abarcan 1997–2016: es una consulta actual de un registro
con documentación histórica, no una relación de obras nuevas en 2026.
Incluye las NNSS (1ª revisión), modificaciones, planes parciales y especiales.
Ejemplos: plan especial Arangoiti (`B-HI-136/2016-P08-N`), NNSS
(`B-HI-129/2006-P05-EIA`), plan parcial San Miguel (`HI-175/2008-P06-N`).

Un ID registral produce un único registro. Sus **286 documentos de instrumento**
(memoria, normativa, planos, etc.) se agrupan dentro de `documentos`, con título y
URL originales limpiadas únicamente de espacios exteriores. Se conservan también
las publicaciones BOB enlazadas en la resolución: **307 enlaces documentales**
en total después de deduplicar por URL dentro de cada instrumento. No son 307
proyectos. Se conserva la procedencia documental y el enlace de ficha e inventario.

`fecha_acuerdo` reproduce «Fecha de Resolución»; `fecha_publicacion` corresponde
exclusivamente a «Fecha de publicación resolución en BOB»;
`fecha_publicacion_normativa` retiene su fecha independiente cuando existe.
La fase procede del epígrafe de resolución («Aprobación definitiva»). Por ejemplo,
Arangoiti: resolución 2016-05-30, publicación 2016-06-15. El año mostrado en el
listado no se convierte en una fecha. No se añaden fechas ausentes ni se infiere
una concesión de licencia. `estado_registro` conserva la vigencia declarada.

El publicador es Diputación Foral de Bizkaia, indicado en cada registro mediante
`source=diputacion_bizkaia` y `organismo_fuente`. `proyectos.source=ayuntamiento`
es la ruta municipal admitida por el manifiesto, no una atribución del publicador.
La cobertura es parcial: únicamente instrumentos presentes en este registro,
sin garantizar todas las modificaciones municipales, planes en trámite, obras
públicas o licencias. Se excluyen formularios, estadísticas y contratación.

## Integridad y geometría

Se contrasta el número de IDs únicos con el total anunciado (14 en esta ejecución).
Si la web introduce paginación que impide obtenerlos todos, el adaptador falla
explícitamente; no entrega una primera página truncada. Cada ficha debe pertenecer
exclusivamente a Güeñes. También se contrasta el número de documentos únicos del
instrumento con el número anunciado por el listado. No se impone un máximo de
registros ni se recortan documentos. Se escribe el JSONL sólo tras completar todo
el inventario. Las actualizaciones vuelven a consultar el inventario completo.

`geometry_status: unavailable`. Se revisó el acceso GIS de planeamiento municipal
https://www.bizkaia.eus/es/tema-detalle/-/edukia/dt/1813 (captura `evidence/gis.html`).
Las fichas utilizadas ofrecen planos PDF, sin geometría vectorial asociada a cada
ID en el HTML. No se verificó un servicio vectorial enlazable a los instrumentos;
no se vectorizan planos ni se inventan coordenadas o CRS. Los registros mantienen
`publication_ready=false`. No se afirma ausencia de cartografía en otros servicios.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_guenes -v`: **5 pasan**. Cubren
formulario/municipio, deduplicación, total incompleto (paginación), fechas con
semántica independiente y ausentes, agrupación documental, conteos y rechazo de
fichas ajenas o enlaces no oficiales, y licencias deshabilitadas.

Extracción real ejecutada directamente mediante
`GuenesAyuntamientoAdapter('guenes', {'capture_dir': 'evidence/captures'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: 14 registros. `evidence/validation.json` contiene `live_records`, URLs
realmente consultadas, limitaciones, runtime y resultado de pruebas. Las capturas
HTML del formulario, inventario y las 14 fichas quedan en `evidence/captures/`.
Además se descargó la memoria de Arangoiti: HTTP 200, `application/pdf`, firma
`%PDF-`, 378682 bytes (`evidence/arangoiti-memoria.pdf`). No se descargaron ni
validaron individualmente los restantes PDFs ni se interpretó su contenido.

Evidencia exclusivamente local, no destinada a commit. No se ejecutaron pipelines,
publicación ni servicios de datos. `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.
