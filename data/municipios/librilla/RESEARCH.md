# Librilla — INE 30023, Murcia

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.librilla:LibrillaAyuntamientoAdapter`.

## Fuentes oficiales y alcance

- https://www.librilla.es/ — web municipal, HTTP 200; enlaza la sede actual.
- https://www.librilla.es/areas/area.asp?id=18 — Área de Urbanismo, HTTP 200.
  En la captura consultada muestra una noticia de fiestas, no un inventario de
  proyectos ni de licencias concedidas. No se convierte esa noticia en registro.
- https://www.librilla.es/plan-general-municipal-ordenacion.asp — inventario
  documental oficial accesible, HTTP 200. Su encabezado identifica el Plan
  General Municipal de Ordenación (Modificaciones Aprobación Provisional).
  La página contiene 228 enlaces PDF únicos: fichas de ordenanzas, memorias,
  información, ordenación y planos de sectores. Todos pertenecen al mismo PGMO;
  se extrae **un instrumento**, conservando cada título y URL, sin transformar
  cada plano, ficha o memoria en un proyecto independiente.
- https://sede.librilla.regiondemurcia.es/web/inicioWebc.do?opcion=noreg&entidad=30023
  — sede enlazada por el ayuntamiento, HTTP 200, identifica al Ayuntamiento de
  Librilla. Expone un catálogo de trámites y accesos JavaScript a Transparencia
  y Tablón. No se ha verificado su inventario de instrumentos ni un registro
  público de concesiones; queda fuera de la extracción. Las solicitudes de
  licencia no constituyen licencias concedidas.

La cobertura es parcial: inventario documental del PGMO servido actualmente por
la web municipal, no un histórico completo de obras ni de planeamiento local.
No se afirma que este paquete sea la última versión, ni que esté vigente. No se
incorporan anuncios de contratación, noticias genéricas o modelos de solicitud.

## Procedencia, agrupación y fechas

El parser exige el contenedor `#noticias`, un encabezado específico del Plan
General y documentos PDF bajo `descargas.librilla.es/pgom/`. Cada documento lleva
su `source_url`; la URL del registro identifica el inventario. Los enlaces se
conservan exactamente como están publicados (HTTP), sin inventar destinos HTTPS.
Se deduplican por URL sin límites de cantidad. El inventario observado es una
lista HTML íntegra, sin paginación. Si aparecen controles de paginación reconocidos
el adaptador falla explícitamente: no devuelve solo la primera página.

La expresión «Modificaciones Aprobación Provisional» procede del encabezado, y se
conserva como parte del título; no se deduce una fase normalizada, aprobación
definitiva o fecha de acuerdo. La página no identifica fechas de publicación o
aprobación propias del instrumento. La fecha actual y la actualización del pie
del CMS no se usan como fechas del expediente. No se crean coordenadas ni
geometría. El registro declara `publication_ready: false`.

Muestra documental comprobada:
http://descargas.librilla.es/pgom/MEMORIAS/1700_01%20Normas%20Urbanisticas.pdf
agotó el tiempo de conexión de 25 segundos, tanto por HTTP como al probar HTTPS.
No se obtuvieron bytes PDF; no se afirma disponibilidad ni contenido documental
verificado. El inventario municipal sí es utilizable y contiene nombres y enlaces
reales del instrumento, pero los documentos solo se referencian. El adaptador no
descarga automáticamente los 228 PDF.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_librilla -v`: **6 pruebas correctas**.
Cubren agrupación y deduplicación, conservación de 240 documentos sin truncado,
ausencia de fechas/coordenadas inferidas, rechazo de inventarios vacíos o ajenos,
paginación, escritura a través del adaptador, preservación del resultado anterior
si falla la extracción y carga del manifest con licencias desactivadas.

Ejecución real mediante `load_manifest('librilla')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 228 enlaces**.
El wrapper del registro ejecutó la anotación de entidades compartida: estado
`ok`, un registro de entidad desconocida; no acredita una clasificación edificatoria.
La evidencia local no se incorpora a los cuatro archivos fuente:

- `evidence/proyectos.jsonl`: salida real del adaptador.
- `evidence/validation.json`: cantidad, URLs consultadas, limitaciones y resultado
  de la comprobación documental.
- `evidence/pgmo.html`: captura del inventario de la ejecución real.
- `evidence/home.html`, `evidence/urbanismo.html`, `evidence/sede.html`: capturas de
  descubrimiento oficial.

Sin publicación, base de datos, geocodificación ni ejecución programada.
`schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son `false`.
Las actualizaciones reemplazan el inventario completo; no simulan un histórico
incremental ni usan el estado para omitir documentos.
