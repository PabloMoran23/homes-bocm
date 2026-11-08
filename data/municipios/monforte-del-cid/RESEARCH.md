# Monforte del Cid — INE 03088, Alicante

Verificación en vivo: 2026-11-08. Cobertura deliberadamente parcial: un instrumento,
el Plan General municipal, con sus 18 documentos directos agrupados. No es un
inventario completo de actuaciones ni un registro de licencias concedidas.

## Inventarios oficiales descubiertos

- https://www.monfortedelcid.es/areas-municipales/urbanismo/ enlaza «Planeamiento»
  a la sede electrónica. Los impresos de solicitud, declaraciones responsables y
  autoliquidaciones de esta página no son concesiones y se excluyen.
- https://monfortedelcid.sedelectronica.es/transparency/03a1a276-f386-4b3d-9195-ac9c03a4acf0/
  es el apartado 7 de transparencia: planeamiento urbanístico (120 documentos),
  planeamiento en tramitación (27), medio ambiente (8), obras e infraestructuras
  (1), indicadores (0), convenios (1) y bienestar animal (2). Los contadores son
  documentos, no cantidades de proyectos. Captura: `evidence/urbanismo-inventory.html`.
- https://monfortedelcid.sedelectronica.es/transparency/c2e943e9-2609-4a2e-a28c-68f516d07c5c/
  divide los 120 documentos en Plan General (38) y planes de desarrollo (82).
  El adaptador verifica el título y contador del Plan General en este índice.
- https://monfortedelcid.sedelectronica.es/transparency/813eccc0-589a-4bb4-a5c9-a2a10f0ffcff/
  es el expediente documental del «PLAN GENERAL - (CTU 19-09-2008)».
  Se extraen sus 18 documentos directos: edicto, anuncio, corrección de error,
  memoria justificativa, normas urbanísticas, catálogo y planos. Los enlaces
  estables `preview-document/<uuid>` y los títulos originales se conservan juntos
  en `documentos`, con la carpeta de procedencia en `source_url`.
- https://monfortedelcid.sedelectronica.es/transparency/dd712f68-0349-4818-86e5-54e7f9a5d329/
  es el inventario de planes de desarrollo. Se examinó su estructura de sectores,
  estudios y documentos; no se incorpora a esta cobertura acotada.
- https://www.monfortedelcid.es/category/obras-e-infraestructuras/ es una categoría
  de noticias municipales. No se usa para convertir noticias, inversiones o
  anuncios de contratación en supuestos proyectos o licencias.

## Alcance, agrupación y paginación

El ámbito incluido son los documentos directamente adscritos al Plan General,
no sus instrumentos modificativos independientes. Las subcarpetas
«MODIFICACIONES PUNTUALES DEL P.G. APROBADAS (15)» y «ESTUDIOS DE DETALLE - PGOU (5)»
se conservan como exclusiones explícitas en el registro y en el resultado de
extracción; no se presentan como parte del instrumento base. También se excluyen
los 82 documentos de planes de desarrollo, los 27 en tramitación y otros apartados.

La sede usa Wicket: entrega diez entradas inicialmente y carga otras mediante
«Mostrar más». El adaptador lee el callback público de la respuesta actual, sin
JavaScript ejecutado, mantiene sesión HTTP y procesa exclusivamente componentes
XML. No inventa URLs de descarga. La extracción real consumió la página inicial,
un bloque con otras diez entradas (ocho documentos y dos subcarpetas) y un bloque
terminal que oculta el botón. Verifica 18 + 15 + 5 = 38. Cambios de contador,
respuestas inválidas, falta de memoria justificativa, páginas sin progreso con
continuación o límites de paginación provocan error antes de sustituir el JSONL.

Cada documento no se convierte en proyecto separado: el UUID de la carpeta
identifica el único instrumento. No se inventa un número de expediente municipal.
El incremental refresca esta instantánea completa y no escribe un cursor que pueda
omitir documentos. Los PDF no se interpretan ni se extraen sus geometrías: la
procedencia procede de los títulos y enlaces del inventario municipal. Las
capturas exploratorias de vistas previas son evidencia auxiliar, no un respaldo
local usado para sustituir una fuente en vivo inaccesible.

## Fechas y limitaciones

«CTU 19-09-2008» se conserva como `fecha_referencia_ctu`, con su fuente; no se
infiere que sea publicación, acuerdo o aprobación definitiva. `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son null. Revisiones de planos
como «rev. 02-26» tampoco se convierten en fechas de aprobación del instrumento.
No se afirma que esta carpeta incluya todas las modificaciones vigentes.

No hay coordenadas ni geometrías verificadas: `lat`, `lon`, `geometry` son null y
`publication_ready` es false. La política compartida clasifica el registro como
`pendiente / insufficient_identity_evidence`: existe un instrumento identificable
por su carpeta y documentación, pero no se inventa una referencia de expediente
para superar esa política. Preparado para revisión del scraper, no para publicación.
Licencias, programación y jitter permanecen desactivados.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_monforte_del_cid -v`: 7 tests OK. Cubren agrupación,
  significado de fechas, bloques sucesivos y terminal vacío de Wicket, detección
  de truncamiento y bucles, exclusión de formularios/login, carga por manifest y
  contrato de licencias desactivadas.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 1 registro, 18 documentos,
  tres respuestas de inventario y dos subcarpetas excluidas. Anotación de política
  compartida aplicada mediante el registro estándar.
- `evidence/validation.json` contiene recuentos reales, URLs, limitaciones y
  referencia a las capturas `live-00.html`, `live-01.html`, `live-02.xml` y
  `live-03.xml`. Evidencia local, fuera de los cuatro archivos fuente entregables.
