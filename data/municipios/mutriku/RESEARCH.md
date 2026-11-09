# Mutriku — INE 20056, Gipuzkoa, País Vasco

Verificación y extracción real: 2026-11-09. Adaptador único:
`municipio.adapters.mutriku:MutrikuAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

La página municipal [Urbanismo](https://www.mutriku.eus/es/servicios/urbanismo)
enlaza [Normativa](https://www.mutriku.eus/es/servicios/urbanismo/normativa).
Esta última publica las NNSS y enlaza en la navegación los inventarios siguientes:

- [Planos generales](https://www.mutriku.eus/es/servicios/urbanismo/normativa/planos-generales-1).
- [Catálogo](https://www.mutriku.eus/es/servicios/urbanismo/normativa/catalogo).
- [Fichas urbanísticas](https://www.mutriku.eus/es/servicios/urbanismo/normativa/fichas-urbanisticas).
- [Modificación puntual](https://www.mutriku.eus/es/servicios/urbanismo/normativa/copy2_of_mutrikuko-hirigintzako-arau-subsidiarioak).

La versión [en euskera](https://www.mutriku.eus/eu/zerbitzuak/hirigintza/araudia)
confirma estas categorías. Se utiliza una sola versión lingüística para evitar
contar dos veces un mismo instrumento. No se usa una noticia individual como seed.
El adaptador descubre las categorías desde la página normativa y todos los detalles
desde el inventario de modificaciones; los detalles no están fijados en el código.

## Registros y semántica

Extracción: **2 instrumentos reales**, con **39 enlaces documentales únicos**:

1. **Normas Subsidiarias de Planeamiento de Mutriku**, con 38 documentos:
   normas, memoria, sistemas generales, 17 planos generales, catálogo y 17
   documentos de fichas (16 ámbitos y apéndice de fichas). El plano general
   repetido en dos páginas se deduplica por URL. Los ámbitos AR/SI/SR no se
   convierten en 16 proyectos: son partes de un único instrumento.
2. **Modificación puntual de las NNSS relativa a AR-9 Motric y SR-1 San
   Nikolas-Burumendi**, con un documento GAO/BOG que contiene el acuerdo de inicio
   y el programa de participación. El título procede del inventario y la fase
   original en euskera del campo `Egoera` del detalle. No se presenta como plan
   aprobado definitivamente ni como obra ejecutada.

Cada documento conserva título, URL y `source_url` de la página que lo enlaza.
Los IDs usan identidad del instrumento: `nnss` y UID Plone del detalle, sin depender
del título editable. Las ordenanzas de ruidos y chabolas se excluyen.

La etiqueta municipal «Normas Subsidiarias de Mutriku (BOG 23-07-2007)» permite
extraer `fecha_publicacion: 2007-07-23`. `fecha_publicacion_fuente` aclara que es la
publicación en BOG indicada por la página, no la publicación de la página ni una
fecha de aprobación. El PDF enlazado es el Documento B, texto refundido de diciembre
de 2006; no se confunde esa fecha de redacción con la publicación. `fecha`,
`fecha_acuerdo` y `fecha_aprob` permanecen nulas.

El PDF de la modificación se descargó y revisó mediante `pdftotext` durante la
investigación: publicación BOG 129 del **2025-07-08**, acuerdo plenario de inicio
**2025-06-26**, firma de alcaldía **2025-07-01**. El extractor no analiza texto PDF;
por ello las fechas de este registro quedan nulas, sin constantes copiadas de una
observación ni fechas inferidas del título o del CMS. Estas fechas sólo documentan
el contenido de la evidencia revisada.

## Cobertura y límites

Inventario municipal actualmente accesible, con documentos históricos; no equivale
a un registro completo y actualizado de todas las modificaciones o de todas las
obras de Mutriku. Tampoco acredita vigencia consolidada de las NNSS. No se extraen
noticias, contratos o licencias a partir de palabras clave.

[Licencias y obras](https://www.mutriku.eus/es/servicios/urbanismo/licencias-y-obras)
ofrece instancias y solicitudes L1–L13, comunicaciones y fianzas; no concesiones.
Los métodos de licencias generan vacío con estado `disabled`.

No hay paginación activa en las páginas recorridas. El parser examina también la
navegación fuera del cuerpo y falla ante enlaces siguientes, `rel=next`, controles
Plone o parámetros `b_start`/`page`; no limita el número de filas ni documentos.
Falla si desaparecen categorías, adjuntos o estructura reconocida. La salida se
reemplaza sólo después de completar todas las peticiones y análisis; una descarga
fallida conserva el archivo anterior. Update refresca la instantánea completa y no
escribe un cursor incremental. Un inventario de modificaciones vacío exige revisión.

`geometry_status: unavailable`: los mapas y fichas son documentos, no geometrías
vectoriales asociadas de forma verificable al identificador del instrumento. No se
han vectorizado ni asignado CRS o coordenadas. `publication_ready: false`.
`schedule.enabled: false`, `licencias.enabled: false`, `geocode.jitter_missing: false`.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_mutriku -v` — **5 pruebas pasan**.
Cubren agrupación y deduplicación, documentos sin extensión, separación de fechas,
exclusión de ordenanzas, fase de formulación, paginación/estructura inesperada,
identidad estable, conservación de salida ante fallo, licencias y contrato manifest/registry.

Extracción real ejecutada mediante `load_manifest('mutriku')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
El registro compartido aplicó su anotación de categorías sin modificar los registros
fuente; la clasificación de entidad queda `unknown` (2/2), sin rechazo de la política.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: los dos registros reales.
- `evidence/validation.json`: recuentos, URLs recorridas, limitaciones y pruebas.
- `evidence/captures/`: HTML capturado por el adaptador en la extracción.
- `evidence/urbanismo.html`, `normativa.html`, `araudia.html`, `licencias-y-obras.html`,
  `planos.html`, `catalogo.html`, `fichas.html`, `modificacion.html` y
  `modificacion-detalle.html`: investigación de navegación y fuentes.
- `evidence/normas.pdf`, `modificacion.pdf` y sus `.txt`: originales y lectura de apoyo.
- `evidence/document_checks.json`: respuesta HTTP, destino, tipo y firma de los
  documentos enlazados; ver recuento final en `validation.json`.

No se ejecutó ningún flujo de publicación, base de datos o despliegue.
