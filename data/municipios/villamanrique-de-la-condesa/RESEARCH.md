# Villamanrique de la Condesa — INE 41097, Sevilla

Investigación y extracción real: 9 de noviembre de 2026. Se inspeccionaron primero
`municipio/adapters/portal.py`, el cargador del registro, `municipio/manifest.py`
y los ejemplos Chipiona y Hernani. No se modifican fuentes compartidas.

## Fuentes oficiales descubiertas

- [Usos y destinos del suelo, portal municipal de transparencia](https://transparencia.villamanriquedelacondesa.es/es/transparencia/indicadores-de-transparencia/indicador/Usos-y-destinos-del-suelo-00024/).
  Fuente implementada: inventario documental vivo con 14 galerías en la página
  observada, de las que ocho son proyectos de actuación concretos. Respuesta
  HTTP 200, sin controles de paginación observados. El código rechaza la aparición
  de paginación explícita, evitando emitir una instantánea truncada.
- [Inventario municipal PGOU publicado el 22/11/2013](https://www.villamanriquedelacondesa.es/es/actualidad/noticias/Plan-General-de-Ordenacion-Urbanistica-de-Villamanrique-de-la-Condesa/).
  HTTP 200. Ofrece adaptación de normas y planes parciales Las Monjas,
  Las Carpinteras, Las Pedreras y Los Senderos del Quema. Descubierto, pero fuera
  de la extracción implementada. La fecha de la página es de publicación, no
  una fecha de aprobación de esos instrumentos.
- [Presentación municipal del avance del PGOM, 20/01/2026](https://www.villamanriquedelacondesa.es/es/actualidad/noticias/Presentado-el-avance-del-PGOM-de-Villamanrique-y-abierto-el-plazo-de-sugerencias-hasta-el-6-de-marzo/).
  HTTP 200. Enlaza directamente al [portal del nuevo plan](https://nuevoplandevillamanriquedelacondesa.es/),
  lo que documenta su relación municipal. No se convierte esta noticia en otro
  proyecto ni se extrae este segundo portal. Su existencia confirma que la
  cobertura implementada es parcial, no todo el planeamiento municipal vigente.

Las dos páginas municipales auxiliares y la fuente implementada están capturadas
localmente en `evidence/`; no se usan como instrucciones ni autorizaciones.

## Selección y agrupación

Una fila por `section.gallery` cuyo `h4.gallery-title` comienza con «Proyecto
(de) Actuación». La extracción real devuelve **8 registros y 34 enlaces PDF**:

| Proyecto identificado por el inventario | Documentos |
| --- | ---: |
| Explotación avícola, finca registral 7428 | 3 |
| Núcleo avícola, parcela 100 del polígono 21 | 3 |
| Explotación avícola, parcela 208 del polígono 3 | 4 |
| Nave almacén y vivienda vinculada a explotación agrícola | 3 |
| Alojamiento para temporeros (memoria La Juncosila y planos) | 8 |
| Almazara | 2 |
| Ampliación de núcleo avícola, proyecto en dos partes | 5 |
| Núcleo avícola, parcela 46 del polígono 12 | 6 |

Se conservan juntos proyecto, memoria, planos, estudios hidrológicos, informes,
resoluciones y anuncios de cada galería, con título y URL de procedencia en
`documentos`. El registro conserva también `inventory_url`; su `url` principal
es un PDF de proyecto/memoria. Los IDs derivan del título normalizado de la
galería y no del orden ni de una URL genérica. Una galería sin proyecto/memoria,
un inventario vacío o títulos duplicados provocan error, sin reemplazar la
salida anterior.

Se excluyen galerías de calificación ambiental, formularios, noticias,
licitaciones y el plan de despliegue de fibra. Los proyectos seleccionados pueden
ser privados: su inclusión acredita publicación municipal de un proyecto de
actuación, no obra pública municipal. Los enlaces vacíos del CMS hacia
`e-attachment.jsp` son marcadores sin documento y se omiten. Se retienen todos
los PDF oficiales de las galerías seleccionadas, incluso enlaces sin texto
visible, para los cuales se usa el nombre del archivo como etiqueta.

## Semántica y límites

No hay fechas explícitas a nivel de galería: se omiten `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob`. Los nombres de decretos y
anuncios no se convierten en fechas o fases. Admisión a trámite, exposición
pública o la palabra «definitivo» en un nombre de archivo no acreditan aprobación
ni concesión. No se interpreta el contenido jurídico de los PDF, ni se comprueba
la vigencia o ejecución actual de los proyectos.

No se inventan direcciones ni coordenadas; `geometry_status: unavailable` y
`publication_ready: false`. `licencias.enabled`, `schedule.enabled` y
`geocode.jitter_missing` están desactivados. No se ha verificado un registro de
licencias concedidas. La actualización vuelve a extraer la instantánea completa,
sin marcas temporales inferidas ni modificación del fichero de estado.

## Verificación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas ejecutadas:
`python -m unittest municipio.test_villamanrique_de_la_condesa -v` — **7 pasan**.
Cubren aislamiento documental, agrupación de partes, exclusiones, rechazo de
anuncios sin proyecto, paginación, enlaces ajenos, duplicados, configuración y
preservación de salida frente a errores.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`portal.config['capture_dir'] = 'evidence'` únicamente para esta ejecución.
La anotación compartida de entidades informa ocho proyectos sin desconocidos.

`evidence/validation.json` contiene `live_records: 8`, fuentes, limitaciones,
resultado y comprobaciones documentales. Se solicitó el PDF principal de cada
uno de los ocho proyectos: todos respondieron HTTP 200 con firma `%PDF-`.
Se guardaron solo prefijos binarios de esos ocho documentos, no descargas
completas; los otros 26 enlaces no se comprobaron individualmente. Las capturas
y los JSONL son evidencia local ignorada por Git; no forman parte de las cuatro
fuentes entregadas. Sin base de datos, publicación ni despliegue.
