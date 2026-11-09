# Ribadavia — INE 32069, Ourense, Galicia

Verificación en vivo: 2026-11-09. Adaptador exclusivo de Ribadavia; cobertura
parcial de planeamiento, sin licencias concedidas ni extracción de contratación.

## Descubrimiento y fuentes oficiales

- https://ribadavia.gal/urbanismo/ — página municipal de Urbanismo, HTTP 200
  con User-Agent Mozilla/5.0. Ofrece normativa, instrumentos históricos y acceso
  al PXOM; también incluye rehabilitación e impresos, que no son proyectos ni
  licencias concedidas. Captura: `evidence/urbanismo.html`.
- https://ribadavia.gal/pxom/ — acceso desde la navegación municipal «PXOM».
  Inventario documental completo de esa página, HTTP 200: **99 PDF únicos**
  y un enlace al paquete del registro autonómico. Se agrupan como **un único
  instrumento**, conservando título y URL de cada documento. No se generan
  proyectos separados por tomo, ficha, núcleo rural o plano.
- https://siotuga.xunta.gal/siotuga/urb — inventario oficial autonómico,
  HTTP 200. La fila exacta del INE 32069 identifica Ribadavia, el PXOM y su
  aprobación definitiva **2019-11-29**. Se consulta de nuevo en cada extracción;
  no se deduce la fecha del nombre del ZIP ni del directorio de carga municipal.

La extracción se limita deliberadamente al PXOM expuesto en esa página. No
pretende inventariar las modificaciones posteriores, todo el planeamiento de
SIOTUGA, la lista histórica de Urbanismo ni las obras municipales. La vigencia
individual de cada versión documental no se ha contrastado. No se ha verificado
un registro público de licencias otorgadas; solicitudes e impresos excluidos.

## Semántica y controles

ID estable `ribadavia-pxom`. `fecha_aprob` procede de la tabla SIOTUGA y conserva
su URL de procedencia; publicación y acuerdo quedan nulos por falta de evidencia.
El día mostrado en la cabecera del sitio no se usa como fecha del instrumento.
Los enlaces documentales se extraen exclusivamente de `article .entry`, evitando
el PDF de empadronamiento de la navegación. Se normalizan URLs Unicode/escapadas,
se eliminan duplicados y se conserva la procedencia municipal de cada enlace.

No hay paginación en el inventario revisado. La aparición de controles next,
pagination o page-links produce un error explícito, sin aceptar una página
truncada. El extractor también rechaza una página sin documentos/título/paquete
PXOM inequívoco o una fila SIOTUGA ambigua o con identidad distinta. Los fallos
ocurren antes de reemplazar el JSONL. Update vuelve a consultar el inventario
completo; no mantiene un histórico de versiones eliminadas.

## Disponibilidad y geometría

Los enlaces se conservan como publicados, con `availability: listed_not_verified`.
La comprobación de muestra obtuvo HTTP 200 y cabecera PDF para la memoria
informativa (`evidence/sample-memoria.pdf`), y HTTP 404 para el enlace de normativa
TOMO III. No se han comprobado exhaustivamente todos los adjuntos. El paquete
histórico enlazado usa HTTP en planeamentourbanistico.xunta.es; su disponibilidad
no se ha verificado. No se sustituye por una URL inventada.

geometry_status: unavailable. Los planos PDF no se convierten en coordenadas.
SIOTUGA ofrece acceso WMS, pero no se ha verificado una geometría vectorial
específica del instrumento. Latitud, longitud y geometría permanecen nulas;
`publication_ready: false`. Schedule desactivado y jitter desactivado.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_ribadavia -v`: **3 pruebas correctas** sobre
agrupación, exclusión de navegación, normalización/deduplicación, paginación,
identidad municipal, fechas inválidas, refresco e inhabilitación de licencias.

Extracción real mediante `load_manifest('ribadavia')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando
`capture_dir: evidence` en memoria. Resultado: **1 registro, 100 enlaces**.
Capturas HTML del PXOM y SIOTUGA, PDF de muestra y `evidence/validation.json`
con conteo, URLs, limitaciones y comprobaciones HTTP. Evidencias locales,
no destinadas a commit. Sólo se añaden los cuatro archivos fuente solicitados.
