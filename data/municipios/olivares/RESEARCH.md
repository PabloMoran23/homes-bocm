# Olivares — Sevilla — INE 41067

Investigación y extracción en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron primero `municipio/manifest.py`, el contrato `municipio/adapters/portal.py`,
el registro de adaptadores y los ejemplos Chipiona y Manlleu. No se necesitan cambios compartidos.

## Fuentes oficiales y descubrimiento

La búsqueda del planeamiento de Olivares condujo al portal municipal de transparencia,
identificado como Ayuntamiento de Olivares. Sus indicadores contienen galerías de documentos
concretos y títulos, no solo menciones en buscadores:

- [Indicador 50: PGOU](https://transparencia.olivares.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00032/).
- [Indicador 53: modificaciones](https://transparencia.olivares.es/es/transparencia/indicadores-de-transparencia/indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00032/).
- [Indicador 54: actuaciones](https://transparencia.olivares.es/es/transparencia/indicadores-de-transparencia/indicador/54.-Se-publica-informacion-precisa-de-los-Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion.-00032/).

Las tres páginas respondieron HTTP 200 en la ejecución del adaptador. El inventario se
extrae de `article.sg-indicador-trans section.gallery`, con `h4.gallery-title` y enlaces
documentales `h4.title-element a`. La navegación general queda fuera de los registros.
No se observó paginación en estas galerías. El adaptador rechaza marcadores de paginación
y enlaces page/searchPage/offset si aparecieran, para evitar una extracción parcial silenciosa.
Cada ejecución actualiza una instantánea completa del ámbito declarado.

## Resultado y agrupación

Seis registros reales, con doce enlaces documentales:

| Instrumento | Enlaces |
| --- | ---: |
| PGOU de Olivares | 1 |
| Modificación 14 PGOU | 1 |
| Modificación 13 PGOU | 1 |
| Modificación del proyecto de reparcelación UR-10 | 3 |
| Modificación 12 PGOU | 5 |
| Delimitación de dos unidades en UZ-10B | 1 |

Cada galería nombrada representa un instrumento, con ID estable derivado de su título,
URL del inventario, documento principal y colección `documentos` con título, URL y
`source_url`. Memorias, planos, documento ambiental y valoración de salud de la
modificación 12 se mantienen juntos. Los acuerdos inicial y definitivo de la modificación
UR-10 se agrupan sin mezclarlos con la galería genérica de documentos UR-10.
La modificación de un título puede cambiar el ID; no existe identificador municipal
estructurado en estas galerías.

El enlace PGOU apunta a la Diputación:
`http://3web.dipusevilla.es/planeamiento/OlivaresPGOU/67PGad%20.htm`.
Se conserva exactamente como lo publica el Ayuntamiento; no se ha verificado la disponibilidad
del destino histórico ni se recorre su inventario interno. El PGOU tiene ficha municipal
sustantiva, que describe aprobaciones de 2006 y 2008; no es un registro sintético creado
solo a partir de la navegación general.

Se descargó íntegro el documento de la modificación 14 desde su enlace oficial:
`https://transparencia.olivares.es/export/sites/olivares/es/transparencia/.galleries/IND-53-/APORBACION-DEFINITIVA-MODIFICACION-PGOU-14.pdf`.
Resultado: HTTP 200, application/pdf, 542137 bytes, firma `%PDF-` válida. Captura y SHA256
locales en `evidence/modificacion-14.pdf` y `evidence/document-check.json`.
El resto de documentos se conserva como enlaces del inventario, sin afirmar que todos sus
destinos hayan sido descargados o que su contenido haya sido interpretado.

## Límites y semántica

Cobertura parcial de instrumentos urbanísticos con galería titulada. Se excluyen la
expropiación de Avda. Estadio 29, la galería genérica «Documentos en información pública»
(con documentos UR-10 que requieren interpretación adicional), las actividades sometidas
a calificación ambiental, los contratos y los formularios de licencia. Los indicadores de
contratación no se usan como proyectos. No se pretende inventariar todas las obras públicas
ni todas las modificaciones vigentes. La categoría del indicador 53 menciona aprobaciones,
pero su contenido también incluye tramitación: no se utiliza esa etiqueta general como fase.

No se infieren fechas a partir de nombres de archivos, actualizaciones del CMS o fechas de
publicación. `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulas;
los títulos originales de documentos conservan su referencia a aprobación inicial,
provisional o definitiva, sin afirmar vigencia del conjunto. No se han normalizado las
fechas narradas en la ficha del PGOU. No hay coordenadas ni geometría extraídas, y
`publication_ready=false`. `licencias.enabled=false`, `schedule.enabled=false` y
`geocode.jitter_missing=false`.

## Validación reproducible

- `python -m unittest municipio.test_olivares -v`: cuatro pruebas correctas, con agrupación,
  exclusión de formularios y documentos genéricos, fases/fechas nulas, enlaces inesperados,
  rechazo de paginación, identidad estable y ejecución del contrato con red simulada.
- Extracción real mediante `load_manifest('olivares')`, `load_portal_adapter(manifest)` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, usando `capture_dir='evidence'`.
  Resultado: seis registros, doce enlaces; política de entidades ejecutada por el registro.
- `evidence/validation.json` contiene `live_records`, `source_urls`, límites, recuento documental,
  hora de ejecución y resultado de pruebas. `evidence/inventory-1.html` a
  `inventory-3.html` capturan las respuestas usadas en la extracción. La evidencia es local
  y no forma parte de los cuatro archivos fuente entregados.
