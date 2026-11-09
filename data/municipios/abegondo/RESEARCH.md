# Abegondo — INE 15001, A Coruña, Galicia

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y autoridad

Se inspeccionaron primero `municipio/adapters/portal.py`, el cargador de manifests,
el registro de adaptadores y los ejemplos Chipiona/Hernani.

- [Urbanismo municipal](https://abegondo.gal/urbanismo/): el botón PXOM remite al visor SIOTUGA de la Xunta (`https://siotuga.xunta.gal/siotuga/carto`). Una primera petición sin User-Agent obtuvo 403; con User-Agent de navegador respondió 200. No se usa esta página como registro sintético.
- [Planes y programas de la sede municipal](https://sede.abegondo.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html): el enlace «Plan Xeneral de Ordenación Municipal (PXOM)» apunta al antiguo dominio de planeamiento de Xunta con `idconcello=15001`. No se confunden los planes antifraude o de subvenciones con actuaciones físicas.
- [Urbanismo SIOTUGA](https://siotuga.xunta.gal/siotuga/urb): la fila INE 15001 identifica Abegondo y enlaza su inventario. En esta revisión indica PXOM y aprobación 2023-10-19.
- [Inventario oficial actual de Abegondo](https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15001): fuente efectiva del adaptador. La titularidad de los datos se declara `source=xunta_siotuga`; el manifest usa la vía municipal del pipeline porque es el inventario al que remite el Concello.

La página carga las fichas por llamadas públicas del navegador. Se capturaron el HTML,
`assets/inventario/controls.min.js?2.5.0` y `conf/config.js`. El código público usa POST
`assets/inventario/query_document.php` con `id=15001` e `idclase` 14, 13, 16 y 18.
Las cuatro consultas devuelven arrays completos: la paginación de DataTables ocurre en
el cliente después de iterar todos los elementos, sin parámetros de página/límite en
la consulta. El adaptador consume todos los elementos de las cuatro clases y rechaza
respuestas con un nuevo formato/envoltorio; no impone un máximo ni corta resultados.
El campo oculto `token` es un campo público de la página usado por su propio JavaScript,
no una credencial de acceso. Se obtiene de nuevo en cada ejecución.

Las fichas se consultan en `assets/inventario/getIOTPU.php` mediante `iddoc` e `idp=0`,
tal como hace la web. Se verifican el identificador, el nombre municipal y la carpeta
ABEGONDO antes de construir los enlaces según `filesroot/folder/documents/pathesperado`.

## Cobertura observada y agrupación

Extracción mediante el adaptador resuelto desde el manifest: **19 instrumentos**, con
**637 enlaces documentales**, un registro por identificador oficial de instrumento:

| Clase de inventario | Registros |
| --- | ---: |
| Planeamiento general (14) | 1 |
| Planeamiento de desarrollo (13) | 3 |
| Histórico (16) | 8 |
| Delimitaciones de núcleo rural (18) | 7 |

Incluye el PXOM de Abegondo (28592), PEID Tanatorio Golpe (28488), PEID para un nuevo
centro de salud (28462), plan de infraestructuras PE/D3 (27864), instrumentos históricos
y delimitaciones rurales como A Igrexa, Herminde-Figueroa, O Igrexario, Xuanzo, Beade,
Fontao y Tras da Igrexa. Son instrumentos de planeamiento publicados, no afirmaciones
de obras ejecutadas ni licencias concedidas. No se extraen formularios, licitaciones
ni noticias. Los documentos de memoria, normativa, planos y anexos permanecen dentro
de su instrumento, con su grupo, título, identificador y URL de origen.

Cuatro históricos (22183, 23140, 24704 y 23139) devuelven `elementos=null`. Se conservan
sus metadatos oficiales y se declara `documentos_status=unavailable_in_source`; no se
fabrican enlaces ni se omiten esas entradas. Las incidencias jurídicas del inventario
y de la ficha se conservan, incluyendo anulaciones. `historico=true` refleja la clase
de la fuente, sin deducir vigencia jurídica de las demás clases.

Cobertura parcial: solo inventario urbanístico SIOTUGA, no inventario territorial IOT,
registro integral de obras, noticias municipales, contratos o licencias. Los IDs son
identificadores del inventario/documentación; no se presentan como números de expediente.
El guard compartido de entidades deja los 19 como `pendiente` por identidad insuficiente
para su criterio de actividad, y devuelve `adapter_incident/unknown_entity_spike`.
Esto se conserva en la evidencia: no se inventa una referencia de expediente para
sortearlo y no se considera el resultado autorizado para publicar.

## Fechas, geometría y ejecución

`fechaaddef` se conserva como `fecha_aprob`; `fechadog`, `fechabop` y
`fechanormativabop` se mantienen por separado como fechas de publicación DOG, BOP y
normativa BOP. `fechatextodef`, si existe, se etiqueta como texto refundido. Se mantiene
la correspondencia de campos en `provenance.date_fields`. La descripción de una resolución
dentro de un documento puede tener otra fecha: no sustituye ni se confunde con la
fecha de aprobación declarada en el inventario. No se genera una fecha genérica ni
una fecha de acuerdo. Se comprueba coherencia entre inventario y ficha.

Sin coordenadas verificadas: `geometry_status=unavailable`, `publication_ready=false`.
`licencias.enabled=false`, `schedule.enabled=false` y `geocode.jitter_missing=false`.
La actualización refresca el inventario completo y sus adjuntos, sin depender de un
corte temporal que perdería cambios documentales o jurídicos. Fallos HTTP, identidad
incorrecta o inventario vacío impiden reemplazar el JSONL por un resultado parcial.

## Validación y evidencia local

`python -m unittest municipio.test_abegondo -v`: cinco pruebas correctas sobre agrupación,
fechas separadas, históricos/incidencias, adjuntos ausentes, rechazo de identidad errónea,
conflictos de fechas, duplicados, formatos paginados/envoltorios, configuración del
manifest y licencias desactivadas sin acceso de red.

Se ejecutó `load_portal_adapter(load_manifest('abegondo')).backfill_proyectos(...)`,
configurando únicamente `evidence_dir` para las capturas locales. Resultado: 19 registros.
Tres muestras (índice PXOM 28592, índice PEID 28488 y documento provisional histórico
28274) respondieron HTTP 200, `application/pdf`, con firma `%PDF-` en sus primeros 512
bytes. Esto verifica muestras, no la disponibilidad de todos los enlaces ni el contenido
completo de cada PDF.

En `evidence/` se encuentran `proyectos.jsonl`, `validation.json` (incluye `live_records`,
`source_urls` y limitaciones), `live-result.json`, el informe de entidades, las cuatro
respuestas de inventario, las 19 fichas, capturas de descubrimiento, JavaScript público
y las tres muestras binarias. Evidencia local, fuera de los cuatro archivos fuente
entregados. Sin publicación, base de datos ni geocodificación.
