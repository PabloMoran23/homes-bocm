# Zalla — INE 48096, Bizkaia

Verificación: 2026-11-08. Adaptador específico del nuevo Plan General de Ordenación
Urbana (PGOU), no del conjunto del planeamiento municipal.

## Descubrimiento y autoridad

- Portal municipal: https://www.zalla.eus/ redirige a
  https://www.zalla.eus/es-ES/Paginas/default.aspx (HTTP 200). Su HTML inicial
  contiene principalmente estructura y scripts; no se ha interpretado como
  inventario vacío de proyectos.
- Inventario documental utilizado: https://zallaplanorokorra.eus/es/ (HTTP 200),
  apartado «Documentos». Micrositio del PGOU con identificación del Ayuntamiento,
  dirección municipal y enlace a zalla.eus. La versión euskera está en la raíz.
- Procedencia oficial confirmada por el anuncio municipal del BOB:
  https://www.bizkaia.eus/lehendakaritza/Bao_bob/2024/05/20/II-2483_cas.pdf
  y por la nueva exposición pública:
  https://www.bizkaia.eus/lehendakaritza/Bao_bob/2025/07/23/II-4487_cas.pdf
  Ambos designan expresamente el micrositio como lugar de consulta del avance.
  Son contexto y verificación de autoridad, no semillas de registros adicionales.
- También se descubrió el catálogo foral
  https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-zalla.
  Sus datos globales/calificaciones orientativos no se convierten en proyectos.
- Los procedimientos de sac-old.zalla.eus (licencias y aprobación de proyectos)
  son instrucciones de solicitud, no concesiones ni instrumentos concretos.

## Resultado y semántica

Extracción real mediante el adaptador cargado desde el manifest: **1 instrumento,
9 enlaces documentales únicos**. Memoria, planos, documento inicial estratégico,
informe previo, síntesis y materiales de participación se agrupan bajo el mismo
PGOU. Los enlaces repetidos no duplican documentos. El cuestionario de Google
Forms se excluye por ser una herramienta de aportaciones. Los documentos
auxiliares no se convierten en obras, licencias ni proyectos independientes.

La lista completa de documentos de la sección española se recorre sin límite
artificial de registros. La página corresponde a un único instrumento, sin
paginación observada. Si aparecen enlaces siguientes/rel=next/rutas /page/, el
parser falla explícitamente. Cambios de identidad, sección ausente, enlaces
inesperados o pérdida de documentos básicos también fallan antes de reemplazar
la salida. La actualización vuelve a leer la instantánea completa, sin usar un
cursor que pueda omitir documentos.

La memoria y el DIE se descargaron y verificaron como PDF (HTTP 200). La carpeta
Dropbox de planos se conserva con sus parámetros exactos: no se ha enumerado su
contenido ni se afirma haber descargado todos los planos. Los demás enlaces son
los publicados en el inventario; su mera presencia no prueba disponibilidad del
archivo. La variante en euskera no se extrae como otro instrumento.

La página describe el proceso completo, incluidas fases futuras. Eso no prueba
aprobación inicial ni definitiva del nuevo plan. El registro conserva `fase=null`.
El anuncio de 2024 distingue acuerdo de 10-05-2024 y publicación BOB de
20-05-2024; el de 2025 distingue decreto de 14-07-2025 y publicación de 23-07-2025,
referida a un nuevo plazo de exposición pública del avance (expediente 1888/2024).
Ninguna es aprobación definitiva del PGOU. El extractor no analiza esos PDF como
fuente de fechas: las fechas del registro quedan nulas y no se infieren de rutas
/uploads/2024/05 ni de metadatos HTTP.

## Cobertura y geometría

Cobertura parcial: solo el nuevo PGOU documentado en este micrositio. No incluye
el archivo de modificaciones de NNSS, obras municipales, otras administraciones,
ni un histórico de licencias. No se afirma que el avance sea planeamiento vigente.
`licencias.enabled=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`.

`geometry_status: unavailable`. Hay planos en una carpeta externa, pero no se ha
verificado una geometría vectorial enlazada al instrumento. No se extraen ni
inventan coordenadas a partir del nombre municipal, direcciones o PDFs.
`lat`, `lon`, `geometry` nulos; `publication_ready=false`.

## Validación reproducible

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_zalla -v`: 3 pruebas pasan.
  Verifican agrupación/deduplicación, exclusión del cuestionario y enlaces ajenos,
  conservación de parámetros, fechas y fase nulas, cambios de fuente, paginación,
  actualización del snapshot y licencias deshabilitadas.
- Extracción real mediante `load_manifest('zalla')`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 1 registro, 9 documentos.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/live-pgou.html`, capturas de inicio y ambas lenguas, BOB 2024/2025
  (PDF y texto), `evidence/memoria.pdf` y `evidence/die.pdf`.
  `validation.json` conserva URLs, conteo, limitaciones y comprobaciones HTTP.
  La política compartida de entidades marca categoría desconocida (1/1), sin
  error de extracción; no se ha forzado una categoría de obra para un PGOU.

Solo se añaden los cuatro archivos fuente solicitados. Evidencia local sin
publicación, cambios compartidos, dependencias nuevas ni escrituras externas.
