# Vilaboa — INE 36058, Pontevedra, Galicia

Verificado en vivo el 2026-11-09. Adaptador de alcance parcial: inventario municipal
de planeamiento aprobado publicado por la Xunta de Galicia en SIOTUGA. No es un
registro de licencias ni un inventario de obras. `publication_ready: false`.

## Descubrimiento y fuentes oficiales

- https://vilaboa.gal/ y https://vilaboa.gal/urbanismo-_g/ — HTTP 200.
  La navegación municipal lleva a impresos/autoliquidaciones. No se convierten
  formularios ni trámites genéricos en proyectos o licencias concedidas.
- https://siotuga.xunta.gal/siotuga/urb?lang=es_ES — tabla oficial: fila INE
  **36058**, **Vilaboa**, PXOM, aprobación 2019-02-25. Enlaza el inventario municipal:
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36058
- https://siotuga.xunta.gal/siotuga/axuda?lang=es_ES — explica el inventario de
  instrumentos con aprobación definitiva y el enlace WMS. No certifica que todos
  los antecedentes de un municipio continúen vigentes.
- El JavaScript público del inventario, obtenido de
  https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0,
  identifica los endpoints y cómo construir los enlaces documentales:
  `assets/inventario/query_document.php` (POST: `id=36058`, `idclase`) y
  `assets/inventario/getIOTPU.php` (POST: `iddoc`, `idp=0`, `lang=es_ES`).
  El formulario proporciona un nonce anónimo público. Se usa únicamente en la
  sesión HTTP y no se guarda en registros ni capturas.
- La referencia antigua https://pxomvilaboa.com/ falla la verificación TLS por
  discordancia del certificado. No se desactiva TLS ni se usa como fuente.

## Cobertura y resultado real

Se recorren **todos** los elementos de las respuestas de las clases 14
(planeamiento general, 4 paquetes), 13 (desarrollo, 3 paquetes) y 18
(delimitación de núcleos rurales, respuesta `null`, 0 paquetes).
El frontend usa DataTables para paginar localmente los arrays completos. No hay
límite artificial de registros ni petición de primera página. Un objeto paginado
nuevo se rechaza explícitamente; errores HTTP, detalles sin documentos o cambios
de identidad/municipio/fechas abortan antes de reemplazar la salida.

**6 instrumentos, 7 paquetes, 336 enlaces documentales**, obtenidos mediante el
adaptador cargado por el manifest y el registro compartido:

| Instrumento | IDs oficiales de documento SIOTUGA | Aprobación definitiva declarada |
| --- | --- | --- |
| PXOM de Vilaboa y aprobación definitiva parcial posterior | 28190, 28421 | 2019-02-25; 2021-10-04 |
| Modificación NSP en Bértola y Figueirido | 23044 | 1998-06-25 |
| Modificación NSP nº 2 | 27868 | 2014-01-09 |
| Plan parcial Parque Empresarial de Bértola | 24614 | 1998-06-25 |
| Estudio de detalle parcela dotacional E-018, Casa do Concello | 28408 | 2021-07-30 |
| PEID Base General Morillo | 28664 | 2024-06-21 |

Los dos paquetes PXOM se agrupan en un instrumento, conservando todas sus
versiones, documentos y fechas. Las modificaciones no se fusionan con el plan
que modifican. Los IDs son de SIOTUGA: no se presentan como números de expediente
municipal. Los documentos tienen sección, título, ID de componente y enlace
oficial; no generan proyectos independientes. Cada versión retiene endpoint,
método y parámetros públicos de procedencia.

`fechaaddef` se conserva como `fecha_aprob`; `fechadog`, `fechabop` y
`fechanormativabop` se conservan como publicaciones distintas. No se deriva una
fecha de acuerdo o concesión de una publicación. En el PXOM agrupado las fechas
se mantienen por versión, sin sustituirlas por una fecha global arbitraria.
No se infiere vigencia jurídica actual de las modificaciones antiguas ni
aprobación completa a partir de aprobaciones parciales.

Se excluyen expresamente clase 16 histórica (consulta de descubrimiento: NSP de
1988, ID 23043), instrumentos territoriales supramunicipales del inventario IOT,
planeamiento en tramitación, noticias, contratación y formularios. La clase 14
contiene antecedentes antiguos aunque no estén en clase 16: su presencia no se
interpreta como vigencia independiente certificada. No se afirma cobertura
histórica completa. `update_proyectos` refresca el mismo inventario completo;
no promete detectar borrados legales o mantener un histórico incremental.

## Geometría y límites de integración

`geometry_status: unavailable`. SIOTUGA anuncia un WMS municipal y visor, pero no
se ha extraído geometría vectorial vinculada a estos instrumentos. Los planos PDF
y JPG se conservan como documentos. No se digitalizan ni se sustituyen por un
centroide, dirección o coordenadas inventadas. La publicación sigue pendiente.

La política compartida de entidades clasifica los seis registros como
`pendiente`: hay identidad documental oficial, pero no número de expediente
municipal verificado. No se rellena ese campo para forzar elegibilidad. No se
modifica esa política. El manifest usa `proyectos.source: ayuntamiento` como ruta
compatible con el contrato existente; la fuente efectiva de cada registro es
`siotuga_xunta`, organismo `Xunta de Galicia`, y así se declara en el manifest.
Licencias y programación deshabilitadas; `geocode.jitter_missing: false`.

## Pruebas y evidencias locales

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_vilaboa -v`: **7 pruebas pasan**. Fechas separadas,
  procedencia, agrupación PXOM, modificaciones distintas, arrays de 125 elementos
  sin truncar, duplicados conflictivos, esquema paginado inesperado, fechas
  inválidas, identidad municipal, rutas documentales, licencias deshabilitadas y
  configuración del manifest.
- Extracción real con `load_manifest('vilaboa')`, `load_portal_adapter(manifest)` y
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **6 registros**.
- `evidence/validation.json`: fecha UTC de ejecución, recuentos, URLs y límites.
- `evidence/sources/`: todas las respuestas JSON de inventario y detalle de la
  ejecución; `evidence/siotuga-controls.js`, ayuda e impresos municipales capturados.
- Dos muestras documentales descargadas con HTTP 200 y tipo PDF: anuncio DOG del
  PEID Morillo (`28664nu001.pdf`) y orden PXOM de 2021 (`28421no001.pdf`). No se
  asegura descarga/verificación individual de los otros 334 enlaces.

Evidencia local bajo `evidence/`, excluida de los cuatro archivos fuente entregados.
Sin cambios compartidos, dependencias, base de datos, despliegues ni publicación.
