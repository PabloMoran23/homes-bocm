# Cabezón de la Sal — Cantabria — INE 39012

Investigación y extracción en vivo: 8 de noviembre de 2026 (UTC).

## Fuentes oficiales y descubrimiento

La [página municipal del PGOU](https://www.cabezondelasal.net/informacion-municipal-2/plan-general-de-ordenacion-urbana/)
contiene enlaces al BOC y al [Archivo de Planeamiento Urbanístico AUCAN del Gobierno de Cantabria](https://aplicacionesweb.cantabria.es/aucan/public/zona/saja/cabezondelasal).
La respuesta municipal HTTP 200 se guarda en `evidence/municipal-pgou.html`.
No se convierte esa página genérica en un proyecto: sirve para acreditar la procedencia del inventario.

La página AUCAN identifica Cabezón de la Sal en su h1 y carga el árbol mediante
`GET https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=12`.
El identificador interno 12 no sustituye al INE 39012. La página y el JSON HTTP 200
se conservan en `evidence/aucan.html` y `evidence/planes.json`.
El JavaScript entrega el árbol completo en una respuesta JSON, sin parámetros de
página, cursores ni peticiones al desplegar carpetas. Se recorre íntegramente la
rama `Actual`; no se impone límite de documentos o instrumentos. Se rechazan
sobres de paginación, ramas raíz desconocidas, documentos sin instrumento y
estructuras inesperadas, evitando resultados parciales silenciosos.

También se consultó el [BOC extraordinario 76 de 23/09/2020](https://boc.cantabria.es/boces/verBoletinExtraordinario.do?id=25941),
capturado en `evidence/boc.html`. Es la primera de cuatro partes de la publicación
del PGOU; no constituye un inventario de cuatro proyectos. AUCAN enlaza las cuatro
partes del BOC dentro del mismo instrumento, además de seis tomos/apéndices.
La fecha incompleta «23 de septiembre» de la web municipal no se utiliza para
inferir el año; las fechas estructuradas proceden de los encabezados AUCAN.

## Resultado y agrupación

Cinco registros reales en `evidence/proyectos.jsonl`, con 55 enlaces documentales:

| Instrumento | Documentos | Acuerdo en encabezado | Publicación BOC en encabezado |
| --- | ---: | --- | --- |
| PGOU de Cabezón de la Sal | 10 | CROTU 23/07/2020 | 23/09/2020 |
| Plan Parcial Nº3 – Domañanes | 16 | CRU 29/01/1991 | 19/02/1991 |
| Plan Parcial Polígono Las Navas SAU I – Ud. 3 y 4 | 17 | No indicado | No indicada |
| Modificación Puntual del Plan Parcial Las Navas | 11 | No indicado | No indicada |
| Plan Parcial La Cabroja | 1 | Ayuntamiento 15/04/2011 | 10/06/2011 |

La modificación tiene `parent_id` del plan Las Navas, sin heredar su fase o fechas.
Los criterios interpretativos de 2019/2020 se mantienen como documentación de
Las Navas con su etiqueta original; esas fechas no se atribuyen al plan original.
Cada documento conserva su título, identificador AUCAN, URL de descarga y ruta
dentro del árbol. No se interpreta cada plano como una obra. Las identidades
locales son hashes de los títulos sin el sufijo de fechas, no números de expediente
inventados. Los documentos de las modificaciones no se duplican en el plan padre.

## Semántica y límites

`Actual` es la clasificación publicada por AUCAN, no una comprobación jurídica
independiente de vigencia. Se excluye expresamente toda la rama `No Vigente`
(normas subsidiarias, sus modificaciones y planeamiento de desarrollo histórico).
La cobertura municipal es parcial: no se afirma inventariar todas las obras,
expedientes o instrumentos existentes. Las categorías de noticias municipales de
urbanismo/PGOU no son un registro de concesiones y no se scrapean como proyectos.
No se incluyen formularios, licitaciones o noticias ajenas al inventario.

`fecha_acuerdo` y `fecha_publicacion` se extraen únicamente cuando el encabezado
del instrumento las distingue mediante CROTU/CRU/Ayto. y BOC. `fecha` queda nula.
`fase` sólo indica aprobación definitiva si la carpeta correspondiente aparece
para ese instrumento; la modificación de Las Navas no recibe fase inferida.
No se inventan coordenadas, geometrías, referencias de expediente o fechas.
Todos los registros tienen `publication_ready: false`, geometría ausente y
`geometry_status: unavailable`. La política compartida de entidades marca los
cinco como `pendiente / insufficient_identity_evidence` por carecer de número de
expediente o identidad de actividad reconocida por sus reglas. Se conserva este
resultado, sin inventar referencias para eludirlo; los registros son instrumentos
documentados, no actividad publicable. No se modifica la política compartida.

Licencias desactivadas por ausencia de un registro público de concesiones
verificado. Programación y jitter desactivados. El método update renueva el
snapshot completo y no mueve cursores temporales.

## Verificación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Parser: `python -m unittest municipio.test_cabezon_de_la_sal -v` — cinco pruebas
correctas. Cubren agrupación, separación padre/modificación, fechas y procedencia,
exclusión histórica, conservación de 150 documentos sin truncar, IDs estables,
rechazo de fuentes vacías/cambiadas/paginadas y actualización sin cursor.

Extracción real mediante `load_manifest('cabezon-de-la-sal')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`;
se habilitó únicamente `portal.config.evidence_dir` en memoria para conservar las
respuestas. `evidence/validation.json` registra 5 live_records, fuentes, límites,
55 enlaces, resultado de política compartida y comprobaciones de descarga.

Muestras AUCAN 29524 (memoria y normativa PGOU) y 29575 (BOC La Cabroja):
HTTP 200, cabecera de adjunto PDF y firma `%PDF-`. Se capturaron sólo los primeros
4096 bytes de cada archivo en `evidence/document-*.prefix`. Esto verifica dos
enlaces, no la integridad de todos los PDFs; no se han leído sus geometrías.
La evidencia es local y no forma parte de los cuatro archivos fuente.
