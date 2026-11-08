# Colindres — Cantabria — INE 39023

Verificado el 2026-11-08. Cobertura parcial del inventario documental de
planeamiento publicado por el Ayuntamiento. Tres instrumentos reales, 29 enlaces
a PDF. No constituye un inventario exhaustivo de obras, proyectos o licencias,
ni una comprobación de vigencia jurídica de cada documento.

## Fuentes oficiales descubiertas

- https://www.colindres.es/index.php/normativa/urbanismo/ — HTTP 200; índice
  titulado «Plan General de Ordenación Urbana 1964:». Una única página sin
  paginación, con 29 entradas de acordeón Divi. Los enlaces no están en etiquetas
  `a`: se publican en el array JSON `et_link_options_data`, asociado a las clases
  de cada entrada. Se interpreta JSON, sin ejecutar JavaScript.
- https://www.transparenciacolindres.es/ — HTTP 200, redirige a
  https://transparenciacolindres.es/. Su enlace Urbanismo devuelve al índice
  anterior. Planes y Memorias, personal y plan antifraude no se consideran
  por sí mismos proyectos físicos o instrumentos urbanísticos.
- https://colindres.sedelectronica.es/info.0 — HTTP 200; catálogo de trámites,
  incluido «Solicitud de Licencia o Autorización Urbanística», y enlace al tablón.
  El formulario no demuestra una concesión. No se ha extraído ni se afirma haber
  agotado el tablón o un registro público de licencias.
- La búsqueda oficial también descubre noticias sobre la contratación de la
  redacción de un nuevo PGOU y la intención de modificarlo para vivienda.
  No se convierten adjudicaciones de servicios o intenciones en planes aprobados.

Capturas locales: `evidence/urbanismo.html`, `urbanismo-live.html`,
`transparencia.html`, `sede.html`, `discovery.json` y los 29 PDF.

## Agrupación y procedencia

1. PGOU 1964: un registro con las tres entradas «NORMAS URBANÍSTICAS» y
   24 entradas de planos/división en polígonos. Los planos de luz y alcantarillado
   pertenecen al mismo instrumento: no se presentan como obras independientes.
2. «MODIFICACION PUNTUAL REDIA»: un registro y su PDF.
3. «MODIFICION PUNTUAL 2 COLEGIO»: un registro y su PDF; se conserva la grafía
   publicada por el índice.

Cada documento conserva su título, URL y página de procedencia. Se verificaron
los 29 enlaces por GET: HTTP 200 y cabecera binaria `%PDF`. `documents.json`
registra tamaño y SHA-256 de cada captura. Los dos primeros PDF de normas son
idénticos; se conservan ambos enlaces del Ayuntamiento, sin duplicar instrumentos.
Las portadas de ambas modificaciones se inspeccionaron visualmente y corresponden
a modificaciones del Plan General de Colindres. Son escaneos sin texto extraíble;
no se interpretan anotaciones manuscritas como acuerdos ni se asignan fechas.

La identidad del PGOU deriva del índice y su año; la de cada modificación de la
URL documental estable, no de su posición en el acordeón. Las fechas de publicación,
acuerdo y aprobación quedan nulas. Ni «1964», ni `/uploads/2019/06/`, ni la fecha
de consulta se convierten en fechas de actos. No se asigna fase de aprobación.
No hay geometría verificada: latitud, longitud y geometría son nulas;
`publication_ready=false`, `geocode.jitter_missing=false` y programación desactivada.
La política compartida clasifica los tres registros como `unknown` por falta de
referencia de expediente/identidad de acto verificadas. No se inventa una referencia
para conseguir elegibilidad de actividad. Este resultado requiere revisión independiente.

## Extracción y validación

El adaptador descarga el índice con timeout de 40 segundos y máximo de 3 MB;
valida título, estructura, clases y URLs municipales PDF. No impone un máximo de
registros ni corta entradas. Ante paginación, acordeones adicionales, destinos
huérfanos, documentos sin enlace, formatos desconocidos o estructura ambigua,
falla antes de sustituir el resultado. Actualizar refresca la instantánea completa;
no mantiene un falso cursor incremental. Las licencias están desactivadas.

- `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_colindres -v`:
  seis pruebas, agrupación y fechas, rechazo de formularios/noticias, paginación,
  destinos inválidos, inventarios ampliados sin truncamiento y contrato del manifest.
- Extracción real mediante `load_manifest('colindres')`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: tres registros, reparto
  de documentos 27/1/1. Se aplica la política compartida sin modificarla.
- `evidence/validation.json`: recuento, URLs, resultado, pruebas y limitaciones.
  Evidencia local; no se incorpora a los cuatro ficheros fuente de la entrega.
