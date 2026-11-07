# Aguilar de la Frontera — Córdoba — INE 14002

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales y alcance

El portal municipal <https://aguilardelafrontera.es/> y el de transparencia
<https://transparencia.aguilardelafrontera.es/> devolvieron HTTP 403 desde este
entorno, también con variantes www y rutas de urbanismo. No se afirma que esas
webs carezcan de documentos. El inventario de transparencia enlazado expresamente
en publicaciones municipales del BOP es
<https://transparencia.aguilardelafrontera.es/transparencia-en-materia-de-urbanismo-obras-publicas-y-medio-ambiente/>;
no se utiliza como si se hubiese podido extraer.

El catálogo público
<https://aguilardelafrontera-opendata.e-admin.es/api/3/action/package_search?q=urbanismo>
respondió correctamente, con cinco conjuntos: mercados, equipamientos educativos,
edificios e inmuebles, alumbrado y callejero. Son inventarios de bienes o
estadísticas, no proyectos. No se convierten en actuaciones.

Fuente implementada: publicaciones del **Ayuntamiento de Aguilar de la Frontera**,
anunciante **389**, en el Boletín Oficial de la Provincia de Córdoba:

<https://bop.dipucordoba.es/buscar?buscar=1&emisor=389&texto=Plan+Parcial&porPagina=100&ordenarPor=2>

Es un inventario de anuncios municipales publicado por la Diputación, no una
fuente periodística. Se verifica el emisor de cada resultado, el dominio de los
documentos, las fechas del boletín y la firma `%PDF-` de cada descarga seleccionada.
Se conservan emisor, título literal, identificador BOP, URL, fecha de publicación,
consulta de descubrimiento, tipo de contenido y SHA-256 de los documentos.

## Resultado real y agrupación

La consulta devolvió **60 anuncios**, revisados íntegramente por el parser. Se
seleccionaron **6 documentos**, agrupados en **5 instrumentos**:

| Instrumento | Publicaciones conservadas |
| --- | --- |
| Plan Parcial SI-11 | [BOP-A-2012-1047](https://bop.dipucordoba.es/visor-pdf/21-02-2012/BOP-A-2012-1047.pdf), 21/02/2012 |
| Plan Parcial SR-15 | [BOP-A-2016-1626](https://bop.dipucordoba.es/visor-pdf/26-05-2016/BOP-A-2016-1626.pdf), 26/05/2016 |
| Plan Parcial SR-22, Cerro Romano y entorno | [BOP-A-2014-779](https://bop.dipucordoba.es/visor-pdf/19-02-2014/BOP-A-2014-779.pdf), 19/02/2014; [BOP-A-2014-1437](https://bop.dipucordoba.es/visor-pdf/18-03-2014/BOP-A-2014-1437.pdf), 18/03/2014 |
| Modificación del Plan Parcial SR-16 | [BOP-A-2011-9935](https://bop.dipucordoba.es/visor-pdf/22-11-2013/BOP-A-2011-9935.pdf), 22/11/2013 |
| Modificación del Plan Parcial SR-17 | [BOP-A-2013-2694](https://bop.dipucordoba.es/visor-pdf/16-04-2013/BOP-A-2013-2694.pdf), 16/04/2013 |

La inspección de los seis PDF con `pdftotext` confirmó instrumentos reales.
SI-11 y SR-15 contienen ordenanzas del plan y sus acuerdos de aprobación.
Los documentos SR-22 describen el mismo ámbito y el mismo acuerdo de aprobación
inicial de 23/01/2014; el segundo es una notificación del primero, no un nuevo
proyecto. Se conservan ambos bajo un solo registro. Las modificaciones SR-16 y
SR-17 son instrumentos distintos, separados de sus planes base. La identidad de
una modificación incluye su descripción, para no fusionar modificaciones de
distinto objeto solo por compartir sector.

El buscador también devuelve oposiciones, ordenanzas, subastas y menciones a planes
en otros documentos: se excluyen. Los proyectos de reparcelación, urbanización y
estudios de detalle que mencionan un plan parcial también se excluyen de este
alcance específico. No se han fijado registros precargados: cada ejecución vuelve
a descubrir los anuncios y descargar los documentos seleccionados.

## Fechas, cobertura parcial y límites

La consulta actual completa contiene publicaciones de 2010 en adelante, que es el
inicio del buscador moderno del BOP. No se cubre el archivo anterior a 2010, ni se
afirma un censo exhaustivo del planeamiento municipal: el alcance implementado son
los planes parciales identificables por sector y sus modificaciones. Se investigó
también el Plan de Reforma Interior AM-2: sus documentos de 2018/2021 y 2024/2025
corresponden a tramitaciones con referencias distintas; no se mezclan con los
planes parciales ni se incorporan a esta extracción.

El scraper comprueba el contador `Resultados del ... al ... de ...` contra todas
las tarjetas y URLs únicas. Si hay más de cien resultados, divide el intervalo
desde 04/01/2010 hasta la fecha de ejecución y consulta recursivamente ambos
subintervalos. Comprueba que el número final de documentos únicos coincide con
el total inicial. Una fecha con más de cien resultados, un cambio del total durante
la consulta, un emisor incorrecto, un sector ambiguo o un PDF inaccesible provocan
error antes de reemplazar la salida. No se descarta silenciosamente otra página.
La extracción real actual no necesitó subdividir: 60 de 60 resultados.

Las fechas de publicación proceden de la ruta fechada del BOP, no del año del
identificador del anuncio. En particular BOP-A-2011-9935 está publicado el
22/11/2013; se conserva esa discrepancia sin inventar una corrección. El registro
agrupado expone la publicación más reciente y cada documento mantiene la suya.
No se deducen fechas de acuerdo/aprobación de esas fechas: ambos campos permanecen
nulos. Tampoco se infiere la fase actual, vigencia, concesión de licencia, ejecución
material o ubicación geométrica. `publication_ready: false`, sin coordenadas,
`geometry_status: unavailable`. No se extrae texto personal de notificaciones.

`licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados.
Las actualizaciones refrescan la instantánea completa; no simulan un incremental
basado en fechas de publicación.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `python -m unittest municipio.test_aguilar_de_la_frontera -v`, **12 correctos**.
Comprueban agrupación SR-22, separación de modificaciones, exclusiones semánticas,
procedencia y fechas, rechazo de cambios de estructura y municipio, paginación
completa o inconsistente, documentos inválidos, actualización y manifest/carga
dinámica. Son fixtures pequeñas de la estructura observada; no necesitan red.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir'] = 'evidence/live-captures'` antes de cargar
el adaptador. Resultado: **5 registros, 6 documentos, 60 anuncios examinados**.
La anotación compartida de entidades terminó con estado `ok`, sin desconocidos.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/parser-tests.txt`, captura HTML de la consulta
y los seis PDF en `evidence/live-captures/`, además de capturas de investigación y
textos de los documentos inspeccionados. No se usaron bases de datos, publicación,
geocodificación, despliegues ni cambios de dependencias.
