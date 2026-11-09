# Los Corrales, Sevilla — INE 41037

Investigación y extracción en vivo: 9 de noviembre de 2026. Municipio de Andalucía,
provincia de Sevilla. El portal municipal https://www.loscorrales.es/ enlaza su
portal oficial de transparencia https://transparencia.loscorrales.es/; la portada
identifica el Ayuntamiento y su dirección en Los Corrales (Sevilla).

## Inventarios oficiales y cobertura

Se recorren cuatro páginas completas, sin límites de registros ni paginación
observada. Se extraen sus enlaces de las galerías documentales municipales,
incluidos los que aparecen en tablas y no solo en tarjetas:

- [PGOU y planos, indicador 50](https://transparencia.loscorrales.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00075/).
  Un documento del PGOU y ocho del PBOM: índice, memoria, respuesta a supervisión,
  dos cartografías, documento inicial estratégico, resumen ejecutivo y memoria de
  impacto en salud. Se generan dos registros, conservando los ocho documentos del
  PBOM juntos. El índice identifica el documento de información, diagnóstico,
  avance y DIE; la respuesta a supervisión identifica expresamente el PBOM de Los
  Corrales. El PBOM no se confunde con el PGOU ni se considera aprobado.
- [Modificaciones y planes parciales, indicador 53](https://transparencia.loscorrales.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00074/).
  Dos registros: PERI del sector SUNC-1 (un PDF con memoria, ordenanzas, etapas,
  estudio económico y planos) y modificación puntual nº 1 del PGOU (tres PDF:
  consulta pública, documento ambiental estratégico y borrador). Se comprobó el
  contenido de los tres documentos de la modificación. El archivo denominado
  `DEFINITIVO-MP-1-PGOU-LOS-CORRALES_F.pdf` dice **BORRADOR** en su portada:
  ni el nombre del archivo ni el título del indicador acreditan aprobación.
- [Usos y destinos del suelo, indicador 55](https://transparencia.loscorrales.es/es/transparencia/indicadores-de-transparencia/indicador/Usos-y-destinos-del-suelo-00074/).
  Un registro del estudio de detalle de calle Sosa 14 y 16, con cuatro documentos:
  anuncio inicial, anuncio definitivo, resumen y estudio. La lectura de los PDF
  confirma el mismo emplazamiento y objeto: agrupación de dos parcelas para una
  vivienda unifamiliar. Se excluyen informe y edicto de innecesariedad de avance
  de asentamientos: no se presentan como otro proyecto ni como avance redactado.
- [Obras de infraestructura, indicador 62](https://transparencia.loscorrales.es/es/transparencia/indicadores-de-transparencia/indicador/Obras-de-infraestructura-realizadas-y-o-las-aprobadas-pendientes-de-ejecucion-00074/).
  Un registro con un proyecto técnico real de alumbrado público. La portada y
  memoria identifican la mejora de eficiencia energética del alumbrado público de
  Los Corrales, promovida por su Ayuntamiento. No se afirma ejecución o recepción.

Resultado vivo: **6 registros y 18 enlaces PDF**. Se verificaron los 18 enlaces
mediante respuesta HTTP correcta y firma `%PDF` de los primeros 1024 bytes. Las
capturas completas de las cuatro páginas y los PDF consultados se guardan en
`evidence/`, fuera de los cuatro archivos fuente entregables.

También se inspeccionó el indicador de proyectos/pliegos de licitación (57), que
solo ofrece un enlace genérico «20151123 - Proyecto de Licitación 1»: no se
convierte ese anuncio en un proyecto. La noticia municipal del inicio del PBOM
sirvió para descubrimiento, pero no se emite como otro registro. No se rastrean
noticias generales, actas, BOP completo ni expedientes privados. Esto es cobertura
parcial de inventarios documentales actuales, no un histórico exhaustivo.

## Semántica, agrupación y límites

Cada registro conserva `inventory_url` y cada documento su título literal, URL y
página de procedencia. La asociación usa nombres y carpetas revisados, no
proximidad indiscriminada entre enlaces. Los identificadores son estables por
instrumento. Se deduplican enlaces repetidos dentro del mismo instrumento.
Documentos desconocidos en las galerías seleccionadas provocan error salvo los
identificables como parte de la carpeta explícita de MP1. La desaparición de una
fuente, redirección inesperada, inventario sin documentos compatibles o aparición
de paginación provoca error antes de sustituir la salida; no se devuelve una
instantánea parcial silenciosa. Actualización vuelve a conciliar las cuatro
páginas y no usa un corte de fecha.

No se extraen fechas a partir de nombres de archivo, firmas o fechas del CMS.
Como ejemplo de distinción comprobada en los documentos de Sosa: el anuncio
inicial se publica en BOP el 21/07/2025 y cita resolución de 09/07/2025; el anuncio
definitivo se publica el 16/10/2025 y cita acuerdo del Pleno de 26/09/2025. Son
hechos distintos. El adaptador conserva sus enlaces pero omite campos de fecha
en vez de extrapolar esas fechas a todos los documentos o incorporarlas como
constantes. Tampoco asigna fases por el nombre del indicador.

Sin coordenadas, geometría, geocodificación aproximada ni fechas inventadas.
`publication_ready=false` y `geometry_status=unavailable` en todos los registros.
`licencias.enabled=false`: un instrumento de planeamiento no equivale a licencia
concedida. `schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_los_corrales -v` — **8 correctas**.
Cubren agrupación y aislamiento PGOU/PBOM y PERI/MP1, los cuatro documentos del
estudio, deduplicación, exclusiones, identidad municipal, ausencia de fechas y
coordenadas inferidas, paginación, vacíos, documentos desconocidos, origen externo,
licencias desactivadas, carga por manifest/registro y preservación de salida ante
fallo de red.

Extracción real mediante `load_portal_adapter(load_manifest('los-corrales'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura de las páginas
activada por `adapter.config['evidence_dir']='evidence'`. El registro compartido
aplicó su política de entidades: seis registros, cero categorías desconocidas.
`evidence/validation.json` conserva recuento vivo, fuentes, limitaciones, resultados
y verificación de los 18 documentos. No se ejecutó publicación ni acceso a bases
de datos.
