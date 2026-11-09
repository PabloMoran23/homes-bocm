# Museros — INE 46177, provincia de Valencia

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

- Área de Urbanismo municipal: https://museros.org/inici/es/area-de-urbanismo/
- Inventario documental enlazado desde esa área: https://museros.org/inici/es/normas-subsidiarias-de-planeamiento-de-museros/

La segunda página contiene actualmente dos conjuntos documentales reales, no una
lista de noticias ni anuncios de contratación. El adapter lee el HTML en vivo y
agrupa los enlaces PDF por sus encabezados en `article .entry-content`:

1. Modificación puntual de las normas subsidiarias nº 9: creación de las subzonas
   CASCO-NHT y CASCO-GEN en el núcleo antiguo. Dos documentos, uno expresamente
   etiquetado como borrador y otro como modificación nº 9.
2. Texto consolidado de planeamiento urbanístico de Museros: 29 documentos,
   incluyendo síntesis, índice, normas, mapas OE/OP y plano guía.

Resultado vivo: **2 registros, 31 enlaces PDF**. Cada documento conserva su título,
URL y página de procedencia en `documentos`. Los planos y el índice son componentes
del mismo conjunto; no se crean 29 proyectos ficticios. Los identificadores del
instrumento permanecen estables si cambian los nombres de archivo o su orden.

La página es estática y no mostró paginación. Se procesa hasta el final sin límites
de registros. Si aparecen controles de paginación, se produce un error explícito
para revisar el recorrido. También falla ante contenedores ausentes, documentos
sin agrupación, secciones desconocidas, instrumentos duplicados, identificadores
ambiguos o documentos esenciales ausentes. El límite de respuesta HTTP produce
error, nunca una extracción parcial silenciosa.

## Semántica y limitaciones

La presencia del documento no acredita aprobación definitiva ni vigencia jurídica.
El inventario no ofrece fechas de publicación o acuerdo inequívocas: `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulas. Los directorios
`2026/03`, `2026/10` y las fechas en nombres de archivo no se convierten en fechas
administrativas. La fase del instrumento queda nula; la condición de borrador se
conserva en el título del documento correspondiente.

Cobertura parcial del municipio: sólo se implementa este inventario actual de NNSS.
El área municipal también enlaza documentos de movilidad y emergencias, excluidos
de este alcance. Los antiguos PDF del Plan General Estructural que aparecen en
buscadores no se incorporan como si fueran el planeamiento vigente. No se afirma
haber recorrido un archivo histórico completo, el tablón electrónico ni todas las
obras municipales. Los formularios de solicitud de licencia no son concesiones;
no se ha verificado un registro público de licencias concedidas.

Sin geometría vectorial verificada ni coordenadas. Los mapas PDF se conservan como
enlaces, sin geocodificar sus ámbitos. `publication_ready` es falso;
`licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` son falsos.

## Verificación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_museros -v`: cinco pruebas correctas. Comprueban
agrupación y procedencia, exclusión de navegación/formularios, ausencia de fechas
y geometrías inferidas, estabilidad de IDs, deduplicación, errores ante cambios
de estructura y paginación, carga del manifest y licencias desactivadas sin red.

Extracción real mediante `load_manifest('museros')`, `load_portal_adapter(...)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. El adapter permite
`portal.config.capture_dir` para capturar el HTML exacto de la misma petición.
La actualización vuelve a obtener una instantánea completa, sin filtros por fecha.

Evidencia local, sin incorporar a fuentes:

- `evidence/proyectos.jsonl`: registros reales, incluidos metadatos de la política
  compartida aplicada por el loader del repositorio.
- `evidence/validation.json`: recuento, URLs, limitaciones y comprobación documental.
- `evidence/inventory.html`: respuesta exacta usada por el adapter.
- `evidence/urbanismo.html` y `evidence/normas.html`: capturas de investigación.
- `evidence/document_checks.json`: comprobación HTTP y firma PDF de los enlaces;
  lectura en streaming de los primeros 1024 bytes, no análisis íntegro de los PDF.
  Los 31 enlaces respondieron HTTP 200 con firma `%PDF-`.
- `evidence/document-*-prefix.bin`: muestras de cabeceras de tres documentos.

Sin cambios compartidos, dependencias nuevas, publicación ni acceso a bases de datos.
