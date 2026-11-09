# Villaverde del Río — Sevilla — INE 41101

Investigación y extracción real: 8 de noviembre de 2026. Se revisaron primero
`municipio/manifest.py`, el contrato `municipio/adapters/portal.py`, el registro
de adaptadores y los ejemplos Chipiona y Manlleu. No hay cambios compartidos.

## Fuentes oficiales descubiertas

- Ayuntamiento: https://www.villaverdedelrio.es/es/ . Identifica al Ayuntamiento
  de Villaverde del Río, CIF P4110100G; enlaza la sección PBOM y la sede.
- Inventario utilizado, indicador 50 del portal municipal de transparencia:
  https://transparencia.villaverdedelrio.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00028/
- PBOM: https://www.villaverdedelrio.es/es/temas/pbom/ . La captura HTML actual
  contiene el título y «Noticias PBOM», pero ningún documento utilizable. El
  título de esta página no se convierte en un registro.
- Obras públicas, indicador 57:
  https://transparencia.villaverdedelrio.es/es/transparencia/indicadores-de-transparencia/indicador/57.-Se-publican-los-proyectos-los-pliegos-y-los-criterios-de-licitacion-de-las-obras-publicas.-00028/
  Listado de licitaciones en plazo sin entradas actuales en la consulta observada.
  No es un inventario histórico completo de obras ni prueba de adjudicación o
  concesión de licencia. No se generan registros de esta página.
- La búsqueda también localizó la sede https://villaverdedelrio.sedelectronica.es/info.0 .
  Sus categorías de trámites no acreditan licencias concedidas; no se implementa
  extracción de solicitudes ni se afirma cobertura de su tablón.

## Cobertura y agrupación

El indicador 50 publica narrativa identificativa y una galería de 32 PDF,
extraídos íntegramente como **tres instrumentos**, sin convertir cada plano en
un proyecto separado:

| Instrumento | Fecha de acuerdo expresada en la página | Adjuntos |
| --- | --- | --- |
| Normas Subsidiarias | 1993-12-21 | 17 |
| Adaptación parcial de las NNSS a la LOUA | 2012-04-26 | 2 |
| Avance del PGOU | 2015-01-22, aprobación del avance por Pleno | 13 |

El parser requiere esa narrativa y documentos para cada instrumento. Los
archivos `NNSS-*` se agrupan en NNSS, `AdaptacionVillaverde_V5.pdf` y
`Publicacion-en-el-BOP.pdf` en adaptación, y `C1av*` en avance PGOU. El índice
preliminar del avance se descargó y se leyó con `pdftotext`: identifica el avance
de Villaverde del Río y sus documentos de información/ordenación. Esto permite
mantener dentro del avance su plano informativo de NNSS/LOUA y los planos del
Camino del Convento, sin inventar instrumentos independientes. Los enlaces de
búsqueda autonómica y el adjunto vacío del CMS se excluyen.

Cada documento conserva título, URL absoluta y página de procedencia. Los IDs
son estables por instrumento. Una repetición de URL no duplica el documento.
Los documentos PDF desconocidos en la galería, cambios de narrativa, procedencia
externa o desaparición de un grupo producen error para exigir revisión.

La galería está completa en una página y no mostró controles de paginación.
El adaptador rechaza explícitamente paginación si aparece: no hay límite de
páginas ni corte silencioso de resultados. `update_proyectos` vuelve a obtener
la instantánea completa; no usa una fecha de corte que perdería documentos.

## Semántica y límites

Son instrumentos reales documentados, no licencias ni certificación de obras
materialmente ejecutadas. La fase del PGOU es únicamente avance aprobado. No
se afirma aprobación definitiva del PGOU ni vigencia actual del conjunto. La
cobertura es parcial e histórica respecto del universo municipal; no incluye
modificaciones o planes de desarrollo ajenos a esta galería ni todo el PBOM.

`fecha_acuerdo` procede de frases explícitas de la página, retenidas en
`acuerdo_descripcion` junto a la URL de procedencia. La fecha CMS 2015-12-02
aparece en dos adjuntos de la adaptación y se conserva como
`documentos[].fecha_publicacion`; no se interpreta como fecha del BOP, del
acuerdo ni de aprobación. La fecha de publicación global queda nula. No se
extraen fechas legales del contenido de los PDF ni se deducen de nombres de
archivo. El resto de adjuntos carecen de fecha CMS en esta galería.

No hay coordenadas ni geometría verificada: `geometry_status: unavailable`,
`publication_ready: false`, `geocode.jitter_missing: false`. No se verificó un
registro público de licencias concedidas, por lo que `licencias.enabled: false`.
`schedule.enabled: false`.

## Validación ejecutada

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villaverde_del_rio -v`

**9 pruebas correctas**: agrupación y aislamiento documental, fechas separadas,
procedencia, navegación irrelevante, duplicados, IDs estables, rechazo de vacíos,
cambios y paginación, carga mediante manifest/registro y protección del resultado
anterior ante errores HTTP.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura local de la
respuesta exacta mediante `capture_dir`. Resultado: **3 registros / 32 enlaces
documentales**. El envoltorio del registro aplica también la política de
entidades existente. No se ejecutaron publicación, geocodificación ni bases de
datos.

Se descargaron tres PDF de muestra con HTTP 200, tipo `application/pdf` y firma
`%PDF`: `NNSS-Aprobacion-definitiva.pdf`,
`C1av_docINDICE-PRELIMINAR_dic2014_p.pdf` y `Publicacion-en-el-BOP.pdf`.
Los demás enlaces se retienen, pero sus destinos no se verificaron uno a uno.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/inventory.html`, `evidence/pbom.html`,
`evidence/works_indicator.html`, `evidence/document_checks.json` y los tres PDF.
La validación incluye fuentes, recuentos por instrumento, limitaciones,
comprobaciones documentales, runtime, fecha de extracción y hashes de capturas.
No se debe incluir esta evidencia en un commit.
