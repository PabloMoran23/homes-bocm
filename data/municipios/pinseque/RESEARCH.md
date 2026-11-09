# Pinseque (Zaragoza), INE 50209

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron el contrato `municipio/adapters/portal.py`, el cargador y esquema
`municipio/manifest.py`, y los ejemplos municipales disponibles. No se modifican
fuentes compartidas, dependencias ni registro de adaptadores: se carga mediante
el `portal.adapter` del manifest.

## Fuentes oficiales y alcance

Fuente utilizada: [Urbanismo del Ayuntamiento de Pinseque](https://pinseque.es/areas/urbanismo/).
Es un inventario documental vivo: el documento principal PGOU enlazado actualmente
está bajo `/uploads/2026/08/`. Esta ruta de subida no demuestra aprobación en 2026.
El apartado «NNSS de Pinseque homologación al Plan General de Ordenación Urbana»
aporta el PGOU y ocho planos únicos. A continuación aparecen diez encabezados de
modificaciones numeradas. El scraper recorre todos los enlaces del apartado, sin
límite de cantidad, agrupa por encabezado y deduplica las repeticiones de URL de
un mismo instrumento. No se observó paginación; si aparece un control de paginación
en el contenedor, la extracción falla para evitar una cobertura parcial silenciosa.

Resultado real: **10 instrumentos y 58 enlaces documentales únicos dentro de sus
grupos**: PGOU y modificaciones 1, 3, 4, 5, 6, 7, 8, 9 y 10. Incluyen Planillas,
UE-2, Sector 16, suelo industrial, viario y zonas verdes, cementerio, sistemas
generales, normas y suelo no urbanizable. La modificación 2 tiene encabezado pero
ningún documento antes del encabezado 3: se omite como registro sin soporte y se
informa expresamente en `headings_without_documents`. No se le atribuyen los
archivos de la modificación 3. La modificación 9 conserva sus cinco documentos,
incluidos los dos acuerdos distintos.

Se consultó también [Ordenanzas y Reglamentos](https://pinseque.es/ventanilla/ordenanzas-y-reglamentos/),
que mezcla normativa fiscal y urbanística, y se descubrió la
[sede electrónica](https://pinseque.sedelectronica.es/info.0). Esta última anuncia
una aprobación inicial del proyecto de urbanización UE-1 publicada el 30/10/2026;
el tablón de la sede no se extrae y no se presenta como cubierto. Los formularios
de solicitud de licencia no acreditan concesiones. La página de Urbanismo incluye
además documentos de Lago Azul y Prados del Rey antes del apartado PGOU: no forman
parte del ámbito de este adaptador. La cobertura es deliberadamente parcial al
inventario documental PGOU y modificaciones; no es un censo de obras físicas,
contratos, licencias, todas las actuaciones urbanísticas ni instrumentos vigentes.

## Semántica y procedencia

Cada registro identifica un instrumento publicado, con título literal, código INE,
municipio, provincia, URL documental principal y `inventory_url`. `documentos`
conserva todos sus enlaces únicos, títulos y página de procedencia, incluidos
acuerdos, anuncios y planos. La URL principal es el primer documento del grupo;
no implica que ese documento sea el texto consolidado. Los identificadores locales
se basan en PGOU/número de modificación, no en un expediente administrativo inventado.

No se afirma aprobación, vigencia, fase, ejecución o concesión de licencia. No se
emiten fechas normalizadas: los títulos mantienen las fechas de publicación de
BOA/BOPZ y las referencias de documentos de acuerdo por separado. En particular,
18/09/2002 en el anuncio y 2002-06-28 en el acuerdo de la modificación 1 no se
confunden. Las fechas incompletas de la modificación 6 («31.05.200», «COT-50.200»)
se conservan sin corregir. Los errores o discrepancias de etiquetas y rutas de
origen, como el plano 12bis de la modificación 5, tampoco se reinterpretan.
La lectura de PDF no forma parte del parser y no se valida el contenido jurídico
de cada archivo. Se mantiene `publication_ready: false`,
`geometry_status: unavailable`, sin coordenadas ni geometrías inventadas.
`schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son `false`.

## Verificación reproducible

Pruebas: `python -m unittest municipio.test_pinseque -v` con el runtime indicado:
**4 pruebas correctas**. Cubren aislamiento entre instrumentos, encabezados vacíos,
deduplicación, exclusión de formularios/noticias, rechazo de inventarios vacíos,
PDF de origen externo y paginación, actualización completa, licencias desactivadas,
semántica sin fechas o geometría inferidas y manifest.

Se ejecutó realmente `load_portal_adapter(load_manifest('pinseque')).backfill_proyectos`
con salida `evidence/proyectos.jsonl`. El cargador aplicó también la anotación de
entidades compartida. `evidence/validation.json` contiene `live_records: 10`,
fuentes, limitaciones, encabezado sin documentos, 58 enlaces y comprobaciones HTTP.
Se comprobaron tres PDF de muestra (PGOU, anuncio de la modificación 1 y anuncio
de la modificación 10): HTTP 200, `application/pdf`, firma `%PDF-`. Solo se guardaron
los primeros 8192 bytes de cada muestra; no se afirma haber validado los 58 archivos.
Las capturas HTML `evidence/urbanismo.html` y `evidence/ordenanzas.html` documentan
las páginas consultadas. La evidencia es local y no forma parte de los cuatro
archivos fuente entregados. No se usaron publicación, bases de datos ni despliegue.
