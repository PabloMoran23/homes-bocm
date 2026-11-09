# Casarrubios del Monte — INE 45041, Toledo

Investigación y extracción real: 9 de noviembre de 2026. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y alcance

El [inventario municipal de normativa urbanística](https://casarrubiosdelmonte.es/ayuntamiento/normativa-urbanistica/)
responde HTTP 200 y publica instrumentos identificados y sus documentos en
acordeones cuyo contenido completo está en el HTML. No se observó paginación.
El parser rechaza enlaces de siguiente página o paginación reconocida; no aplica
límites ni recortes de resultados. Un cambio de contenedor o un inventario sin
documentos identificados provoca error.

Se extraen **cinco instrumentos con once enlaces documentales**:

- Plan Parcial Polígono Industrial Monte Boyal: ordenanza reguladora, plano y
  partes 1 y 2 del plan, agrupados en un registro (4 documentos).
- Modificación del artículo 63 del Plan Parcial Monte Boyal: registro separado
  de modificación, con el anuncio/documento de aprobación (1 documento).
- Normas Subsidiarias de Planeamiento: documento normativo (1 documento).
- Plan Parcial Urbanización Calypo-Fado: plan y plano de clasificación (2 documentos).
- Plan Parcial Urbanización Los Guindales: clasificación/gestión y planos 024 y
  026 (3 documentos). La sección municipal «URBANIZACIÓN LOS GUINDALES. PLANOS»
  identifica expresamente esos dos números como plano de parcelas y superficies;
  los enlaces correspondientes aparecen en «NORMAS DEL 11 AL 31».

La identificación estable utiliza el instrumento, no cada PDF. Cada documento
retiene título, URL y página de procedencia. Los enlaces de los dominios municipal
con y sin www se conservan tal como se publican; las descargas comprobadas
redirigen al dominio sin www. Los once enlaces devolvieron HTTP 200 y firma PDF
válida. Se capturaron completos cuatro PDFs y se verificó el comienzo de los
restantes; no se afirma haber interpretado todo su contenido.

Otras fuentes descubiertas: [Urbanismo](https://casarrubiosdelmonte.es/servicios-municipales/servicios-al-ciudadano/urbanismo/),
[transparencia](https://casarrubiosdelmonte.es/ayuntamiento/portal-de-transparencia/) y
[sede electrónica](https://casarrubiosdelmonte.sedelectronica.es/info.0).
No forman parte de la extracción: no se ha verificado allí un registro público
completo de licencias concedidas. La fuente seleccionada sí proporciona documentos
concretos de instrumentos, y permite una cobertura real y acotada. Las noticias,
formularios y anuncios de contratación no se convierten en proyectos o licencias.

## Semántica y limitaciones

Esto es una instantánea parcial del inventario documental publicado actualmente,
no una declaración de vigencia jurídica, una lista exhaustiva del planeamiento,
un histórico de obras ni de licencias. Se excluyen ordenanzas generales de
edificación, cartografía general sin atribución inequívoca a un instrumento y
planos de otros desarrollos sin instrumento identificado. No se crean proyectos
por cada mapa, parte documental o encabezado de sección.

El parser no interpreta el interior de los PDFs. Las fechas de publicación,
acuerdo y aprobación quedan null porque no hay metadatos estructurados en el
inventario, no porque se asegure que no existen fechas en los documentos.
La inspección del PDF de la modificación del artículo 63 muestra precisamente
la diferencia: publicación BOP número 141 de **27 de julio de 2021**, acuerdo
plenario de aprobación definitiva de **31 de agosto de 2020**. Estas fechas no
se fijan como constantes del scraper ni se confunden con la fecha de rastreo.
El título de archivo «APROBACION» tampoco genera por sí solo una fase.

No se verificó geometría: sin centroides, geocodificación ni coordenadas
sintéticas. `publication_ready: false`, `geometry_status: unavailable`,
`schedule.enabled: false`, `geocode.jitter_missing: false` y
`licencias.enabled: false`. Update vuelve a consultar toda la instantánea
soportada y reemplaza el JSONL atómicamente; no simula un incremental por fechas.

## Validación y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_casarrubios_del_monte -v`
— cinco tests correctos: agrupación y deduplicación, modificación independiente,
exclusión de formularios/ordenanzas/mapas anónimos/enlaces externos, planes y mapas
asociados, fallo por estructura vacía/cambiada o paginación y actualización.

Extracción real mediante `load_manifest` → `load_portal_adapter` →
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **5 registros**, política
de entidades `ok`, cero entidades desconocidas. No se ejecutó el pipeline global.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: los cinco registros reales.
- `evidence/validation.json`: recuento, URLs, pruebas, verificaciones y limitaciones.
- `evidence/inventory.html`: captura de la fuente municipal.
- `evidence/document-checks.json`: HTTP, redirección y firma de los once PDFs.
- `evidence/live-result.json`: resultado de la extracción mediante el registro de adaptadores.
- `evidence/modificacion-art63.pdf`, `nnss.pdf`, `calypo.pdf`, `guindales.pdf` y
  textos extraídos para inspección de la modificación y las normas subsidiarias.
