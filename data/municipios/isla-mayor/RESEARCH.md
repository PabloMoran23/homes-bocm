# Isla Mayor — Sevilla — INE 41902

Investigación y extracción real: 9 de noviembre de 2026. Un único adaptador,
limitado al inventario documental del nuevo Plan General de Ordenación Municipal.

## Fuentes oficiales descubiertas

- [Micrositio municipal del PGOM](https://www.islamayor.es/es/pgom/).
- [Inventario documental del PGOM](https://www.islamayor.es/es/pgom/documentacion/):
  fuente implementada, HTTP 200, identificación explícita del plan de Isla Mayor.
- [Archivo de planeamiento en transparencia](https://transparencia.islamayor.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00055):
  fuente oficial adicional inspeccionada y capturada, fuera de la cobertura de este
  adaptador. Contiene PGOU 2009, modificaciones de NNSS, estudios de detalle,
  planes parciales y documentos de urbanización. Sus galerías tienen paginación
  independiente (`pagegalleryfiles-28-1`, `pagegalleryfiles-31-1`,
  `pagegalleryfiles-34-1`, entre otras). No se extrae su primera página como si
  constituyera el archivo completo. Tampoco se mezclan instrumentos históricos
  con el nuevo PGOM.

## Cobertura implementada y agrupación

La extracción real produjo **1 instrumento y 62 enlaces PDF**, agrupados en
`documentos`, con título, URL, sección o secciones y URL de procedencia. Se
mantienen las distintas versiones de cartografía cuando sus URL difieren; una
URL repetida conserva sus secciones sin crear otra actuación. No se crean
62 proyectos a partir de los planos del mismo PGOM.

El HTML entrega nueve bloques: FASE INICIAL (1), FASE 1 (1), FASE 2-1 (1),
Fase 2-2 (1), Fase 2-3 (20), FASE 3 (1), Fase 3 Avance - Memoria (4),
Fase 3 Avance - Cartografía (30), Fase 3 Avance - Anexos (3).
No hay controles de paginación en este inventario. Los ocho colectores que
incluyen comentarios de recuento usan `rows=10000`; todos los `listResultSize`
coinciden con los enlaces entregados. El bloque de resolución tiene un enlace
directo, sin comentario de colector. El parser verifica los recuentos presentes,
todos los bloques y todos los enlaces del directorio documental, sin límite
silencioso. Si aparecen controles de paginación, recuentos incompletos, enlaces
fuera de los bloques o documentos inesperados, falla explícitamente. Una futura
paginación requerirá implementar su recorrido antes de producir otro snapshot.

La ficha genérica y la navegación no bastan para generar un registro: se exige
identificación municipal y documentación real dentro de las tablas oficiales.
No se extraen formularios de licencia, noticias ni anuncios de contratación.

## Semántica y comprobación documental

Se descargó y abrió con `pdftotext` la
[resolución enlazada sobre el avance](https://www.islamayor.es/export/sites/islamayor/.galleries/documentacion-pgom/RESOLUCION-FIRMADA-APROBACION-AVANCE.pdf).
HTTP 200, `application/pdf`, firma `%PDF-`, 138795 bytes. La resolución
572/2026, de 25/05/2026, identifica el expediente `2023/PPP_01/000001` y la toma
en consideración del Avance y Documento Inicial Estratégico, participación pública
y solicitud de inicio de evaluación ambiental. Esto confirma un instrumento
concreto en elaboración; no acredita aprobación definitiva. El rótulo del enlace
no se convierte automáticamente en una fase legal de aprobación.

La fecha de la resolución se documenta aquí como comprobación manual, sin
precargarla en el scraper. El adaptador no analiza los PDF: `fecha_publicacion`,
`fecha_acuerdo` y `fecha_aprob` permanecen nulas. Una fecha de firma, una fecha
de resolución y una fecha de publicación tienen significados distintos. No se
usan fechas del CMS como fechas de acuerdo. Tampoco se afirma vigencia del plan
ni ejecución de obras. Las secciones son etiquetas documentales de la fuente.

No se extraen coordenadas ni se geocodifica: geometría y coordenadas nulas,
`geometry_status: unavailable`, `publication_ready: false`. Licencias desactivadas
por ausencia de un registro público verificado de concesiones. El manifiesto
desactiva programación y jitter. Cobertura parcial: no representa todas las
obras ni todos los instrumentos municipales.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `python -m unittest municipio.test_isla_mayor -v`: **8 correctos**.
Comprueban agrupación, retención de enlaces/secciones, ausencia de fechas y
coordenadas inferidas, rechazo de páginas genéricas, recuentos incompletos,
paginación, documentos inesperados, cambios de origen y preservación del
snapshot anterior si falla el parser. También verifican el contrato de refresco
y licencias desactivadas.

Ejecución real mediante `IslaMayorAyuntamientoAdapter.backfill_proyectos`, usando
el manifiesto y `capture_dir=evidence`, sin publicación ni conexión a bases de
datos. Evidencias locales excluidas de los cambios fuente:

- `evidence/proyectos.jsonl`: un PGOM con 62 documentos reales.
- `evidence/validation.json`: `live_records`, `source_urls`, limitaciones,
  recuentos, momento de consulta y hashes de las capturas.
- `evidence/pgom-live.html`: HTML de la misma ejecución del adaptador.
- `evidence/pgom.html`, `evidence/transparencia.html`: exploración oficial inicial.
- `evidence/resolucion-avance.pdf` y `.txt`: comprobación documental manual.

Solo se descargó un PDF para verificar contenido; los otros 61 enlaces se
retienen del inventario sin afirmar haber validado individualmente su contenido.
