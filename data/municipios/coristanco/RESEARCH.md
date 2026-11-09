# Coristanco — INE 15029, A Coruña

Verificado en vivo el 2026-11-09. Implementación limitada a un instrumento real:
el PXOM publicado en la página municipal de Urbanismo. Sus seis documentos
(índice y tomos I–V) forman un solo registro, no seis proyectos. No pretende
cubrir todo el planeamiento histórico, las obras públicas ni las licencias.

## Fuentes oficiales investigadas

- https://coristanco.gal/ — HTTP 200; enlaza Urbanismo y el portal de transparencia.
- https://coristanco.gal/urbanismo/ — HTTP 200. Inventario usado por el adaptador:
  encabezado `PXOM`, dentro de `URBANISMO E OBRAS`, seguido del índice y cinco
  tomos. Los visores EmbedPress exponen sus PDF en atributos `data-pdf-url`,
  no en enlaces HTML convencionales. La página no muestra fechas del instrumento
  ni una fase administrativa explícita. No tiene paginación de este inventario.
- https://sede.coristanco.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
  — HTTP 200. Publica un enlace PXOM al antiguo dominio
  `www.planeamentourbanistico.xunta.es/siotuga/inventario?inv=1&idconcello=15029`.
  También enlaza un plan municipal de prevención y defensa contra incendios:
  queda fuera del alcance de este adaptador urbanístico.
- https://siotuga.xunta.gal/siotuga/urb — HTTP 200. La fila de Coristanco identifica
  exactamente el código 15029 y un Plan xeral de ordenación municipal; muestra
  `2015-12-03` y enlaza el inventario municipal. Es corroboración de la identidad,
  no una fecha incorporada a partir de una columna sin interpretar.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15029
  — HTTP 200; la respuesta capturada contiene el formulario de búsqueda y scripts,
  sin filas de expedientes. No se ha completado la investigación de esa interfaz
  dinámica; no se afirma cobertura completa del inventario autonómico.
- Los resultados oficiales de procedimientos de la sede contienen solicitudes
  de información urbanística y comunicación previa de obra. Son trámites, no
  licencias concedidas. No se ha verificado un registro de concesiones.

## Procedencia documental y semántica

Los seis PDF proceden exclusivamente de los atributos del inventario municipal:

- https://coristanco.gal/wp-content/uploads/2026/05/INDICEXERAL.pdf
- https://coristanco.gal/wp-content/uploads/2026/05/TOMOI.pdf
- https://coristanco.gal/wp-content/uploads/2026/05/TOMOII.pdf
- https://coristanco.gal/wp-content/uploads/2026/05/TOMOIII.pdf
- https://coristanco.gal/wp-content/uploads/2026/05/TOMOIV.pdf
- https://coristanco.gal/wp-content/uploads/2026/05/TOMOV.pdf

Los seis devolvieron HTTP 206 a solicitudes Range de los primeros 1024 bytes,
`Content-Type: application/pdf` y cabecera `%PDF-`. Estas comprobaciones no
validan el contenido íntegro ni la versión jurídica de los PDF. Las capturas
`.sample` son fragmentos, no documentos completos. No se extrae texto de PDF.
Cada documento conserva título, URL y página de procedencia en `documentos`.
`url_documento` apunta al índice. La identidad estable `coristanco-pxom` describe
el instrumento, sin depender de la carpeta de subida.

El segmento `2026/05` es una ruta de subida, no una aprobación o publicación.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos.
No se atribuye vigencia jurídica basándose solamente en la publicación municipal.
No se deducen coordenadas del municipio, parcelas ni geometría de planos:
`lat`, `lon`, `geometry` son nulos y `publication_ready` es false.

## Comportamiento y validación

El adaptador descarga exclusivamente la página de Urbanismo, con timeout de
30 segundos y límite de respuesta de 3 MB. Requiere un único encabezado PXOM,
los seis rótulos documentales esperados y seis URL distintas de PDF del dominio
municipal. Deduplica repeticiones exactas y rechaza conflictos, documentos
inesperados, inventarios incompletos y marcadores de paginación. Un cambio de
estructura exige revisión; no produce registros de relleno. La actualización
refresca la página completa y no filtra por fechas. Licencias desactivadas.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_coristanco`: 6 pruebas correctas; agrupación,
  deduplicación, fechas/geometría desconocidas, rechazo de formularios e
  inventarios incompletos, conflictos, dominios ajenos, paginación y resolución
  del manifest.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos`: 1 registro, 6 documentos, respuesta `ok`.
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/urbanismo-live.html`, capturas de las
  páginas investigadas y `evidence/document-checks.json` con fragmentos PDF.
- `schedule.enabled=false`, `geocode.jitter_missing=false`,
  `licencias.enabled=false`. Sin cambios en fuentes compartidas o dependencias.
