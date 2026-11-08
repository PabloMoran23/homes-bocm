# Umbrete — INE 41094, Sevilla, Andalucía

Investigación y extracción real: 7 de noviembre de 2026. Un único adaptador:
`municipio.adapters.umbrete:UmbreteAyuntamientoAdapter`.

## Fuentes oficiales descubiertas

El [índice del Portal de Transparencia municipal](https://transparencia.umbrete.es/es/)
enlaza directamente los inventarios usados:

- [Indicador 50: PGOM](https://transparencia.umbrete.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Municipal-PGOM/).
  Un instrumento, 14 documentos: avance, documento inicial estratégico, memoria,
  planos, evaluación de salud y documentación administrativa.
- [Indicador 53: modificaciones y planes](https://transparencia.umbrete.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00022/).
  Quince instrumentos con 50 documentos: adaptación parcial a la LOUA,
  modificaciones, planes parciales SR-12 y SR-14, estudios de detalle y reformado
  del proyecto de urbanización SR-11. No se convierten memoria, plano, acuerdo,
  inscripción y anuncio del mismo instrumento en proyectos independientes.
- [Indicador 55: usos y destinos del suelo](https://transparencia.umbrete.es/es/transparencia/indicadores-de-transparencia/indicador/Usos-y-destinos-del-suelo-00022/).
  Plan Municipal de Vivienda y Suelo, expediente 2025/PES_02/002522,
  con diez documentos distintos; el informe técnico repetido se deduplica por URL.

Los tres inventarios se sirven completos en una página cada uno. No se observó
paginación. El parser rechaza enlaces de continuación o controles de paginación
si aparecen, en lugar de aceptar una primera página parcial. También rechaza
artículos desaparecidos, secciones desconocidas, PDF sin grupo y procedencia
externa inesperada. Las capturas conservan el HTML completo.

Se inspeccionaron además los indicadores 54 (actuaciones en ejecución y
tramitación, y convenios) y 57 (proyectos y contratación). Quedan fuera del alcance
de este adaptador. El indicador 57 mezcla pliegos de alumbrado, anuncios y algunos
proyectos técnicos de obras; no se importó como si fuera un registro de obras.
La web de participación `https://nuevoplangeneraldeumbrete.es/` apareció en la
búsqueda, pero no es fuente del extractor ni se duplicó el PGOM desde ella.

## Resultado y límites

**17 instrumentos reales, 74 enlaces documentales únicos dentro de sus grupos.**
Cobertura parcial de los indicadores 50, 53 y 55 actualmente publicados; no es
un registro histórico exhaustivo ni una certificación de vigencia jurídica.
Cuatro encabezados sin PDF usable se omiten y se enumeran en la validación:
2010/01, 2012/01, 2017/01 y 2017/04. Los tres últimos remiten a expedientes aún
en trámite del indicador 54. Las omisiones no se sustituyen por registros vacíos.

Los títulos y referencias se extraen del HTML, sin expedientes precargados.
Los documentos conservan título, URL, página de procedencia y texto de la
ficha. El expediente alfanumérico del plan de vivienda se conserva íntegro.
El PGOM, sin número de expediente publicado en su encabezado, se identifica
como paquete documental (`source_entity_type: documento`); los instrumentos
con referencia publicada conservan `expediente`. La clasificación compartida
final tiene cero entidades pendientes y estado `ok`.

No se infiere una fecha de aprobación desde el nombre de un PDF o la fecha del
CMS. Por ejemplo, el PGOM distingue en el texto de origen el acuerdo plenario
del 27/11/2025 y el anuncio en BOP del 4/12/2025. El adaptador no normaliza esas
fechas en campos de acuerdo/publicación: conserva sus rótulos documentales.
Tampoco interpreta el avance como aprobación definitiva del plan. No extrae
coordenadas, fases ni concesiones de licencias. Todos los registros llevan
`publication_ready: false` y `geometry_status: unavailable`. El manifest desactiva
licencias, programación y jitter. La actualización vuelve a leer el inventario
completo; no aplica filtros de fecha ni un límite arbitrario de registros.

## Comprobaciones y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_umbrete -v`: ocho pruebas correctas.
  Comprueban agrupación, aislamiento de documentos entre instrumentos,
  deduplicación, referencia alfanumérica, ausencia de fechas/geometría inferidas,
  rechazo de formularios/anuncios sin instrumento, errores de estructura,
  paginación, procedencia y preservación de la salida ante fallo de red.
- Ejecución real con `load_manifest('umbrete')`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Solo lectura de webs
  públicas y escritura local; sin base de datos ni publicación.
- `evidence/validation.json`: 17 registros, fuentes, omisiones, límites,
  clasificación compartida, runtime, instante UTC y comprobaciones documentales.
- `evidence/indicador-{50,53,55}.html`: capturas de la ejecución del adaptador.
  El índice y los indicadores 54 y 57 se conservan como evidencia de investigación.
- `evidence/sample-{50,53,55}.pdf`: tres descargas completas de muestra
  (acuerdo PGOM, normas de urbanización y resolución del plan de vivienda), todas
  con HTTP 200, `application/pdf` y firma `%PDF-`. No se descargaron ni analizaron
  los otros 71 documentos; sus enlaces se conservaron, sin afirmar accesibilidad
  individual comprobada.

La evidencia es local y queda fuera de los cuatro archivos fuente entregables.
