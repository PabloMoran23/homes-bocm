# Alcaudete — INE 23003, Jaén, Andalucía

Investigación y extracción: 7 de noviembre de 2026. Implementación de un único
adaptador municipal, con cobertura documental parcial y retrospectiva.

## Descubrimiento de fuentes oficiales

- Ayuntamiento: https://www.alcaudete.es/es/informacion-urbanistica2
  responde HTTP 200, pero muestra «No hay elementos disponibles en este momento».
  Captura local: `evidence/informacion-urbanistica.html`.
- Portal municipal de transparencia:
  https://alcaudete.sedelectronica.es/transparency anuncia 127 elementos en
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE». La expansión Wicket pública
  ensayada con sesión HTTP devuelve un cuerpo vacío; no se convierte ese contador
  en expedientes ni se afirma que no existan documentos. Capturas:
  `evidence/transparencia.html`, `evidence/urbanismo-ajax.xml`.
- Inventario oficial actualmente enlazado por Diputación de Jaén:
  https://www.dipujaen.es/conoce-diputacion/areas-organismos-empresas/areaF/urbanismo/planeamiento/
  El enlace «Desarrollo del Planeamiento de la Provincia» lleva a
  https://www.dipujaen.es/export/sites/default/galerias/galeriaDescargas/diputacion/dipujaen/infraestructuras-municipales/Urbanismo/DESARROLLO-ACTUAL_OCTUBRE-25.pdf
  La página también remite a SITUA de Junta de Andalucía
  (https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf), que no forma
  parte de esta extracción. El PDF rotula «ACTUALIZADO A: OCTUBRE 2025», aunque
  sus pies llevan 10/09/2026; ninguna de esas marcas se trata como fecha de acuerdo.
- La búsqueda oficial también encontró una publicación posterior sobre la
  modificación 22 del PGOU: https://www.juntadeandalucia.es/boja/2026/181/31
  Esto confirma que el inventario retrospectivo no asegura cobertura actual de
  todos los actos. No se incorpora como proyecto adicional: la cobertura elegida
  son Estudios de Detalle, no modificaciones del PGOU ni resultados de búsqueda.

## Unidad de extracción y alcance

Se descarga de nuevo la página provincial y se descubre el PDF por el texto de
su enlace, sin fijar el nombre de archivo. Se procesa íntegro con `pdftotext
-layout`, ejecutable ya instalado; no se añaden dependencias. Se delimita la
sección exacta «MUNICIPIO: 003. ALCAUDETE» y se recorren sus cinco páginas PDF
9–13. Se extraen todas las filas explícitas «Estudio de Detalle»: **17 registros**.
Entre ellos: Peñuelas, Camino Bermejo/Geranio, Los Zagales, El Lanchar, Los Llanos,
Papelicos de Noguerones y los reajustes en Sabariego y Avda. Andalucía 18B.

Se conservan las continuaciones del ámbito y sus extractos de acuerdos. Las
repeticiones de un mismo ámbito normalizado se agrupan por instrumento,
reteniendo todos sus extractos y enlaces a páginas. Los IDs dependen del ámbito,
no del nombre/versionado del PDF. Los enlaces documentales son a la ficha
resumen provincial y su página PDF, no se presentan como proyectos técnicos ni
como acuerdos originales descargados.

La siguiente subsección «BOBADILLA (LA)» se excluye: el alcance es expresamente
la sección 003 del inventario, no la totalidad de documentos de las entidades
locales de Alcaudete. Sí se conservan los estudios de Noguerones y Sabariego
incluidos en esa sección. Se excluyen todas las demás figuras (PGOU, planes
parciales, reparcelaciones, etc.), ordenanzas, formularios, contratación y noticias.
No se atribuyen concesiones de licencia, ejecución física ni vigencia actual.

El inventario es un PDF completo, no una lista paginada HTTP. No hay límite
artificial de páginas o filas. Se exige encontrar el cierre de la sección y al
menos un estudio; se rechazan documentos vacíos, redirecciones externas,
cambios de formato y enlaces de siguiente página detectados en el índice.
No hay recuperación silenciosa de capturas locales si falla la fuente viva.

## Fechas, procedencia y limitaciones

`source: diputacion_jaen` identifica la procedencia real. `proyectos.source:
ayuntamiento` es el selector de ruta del esquema existente, no una afirmación
sobre el editor de los documentos. Diputación es fuente oficial secundaria.

Las columnas «Fecha BOP» y «Fecha acuerdo» contienen información distinta y
algunas inconsistencias. No se convierten en fechas estructuradas: los actos y
sus fechas se retienen literalmente en `extractos_fuente`, junto a la página
correspondiente. No se rellena `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni
`fecha_aprob` mediante inferencias. Tampoco se asigna una fase actual a partir
de una fila histórica. No se inspeccionaron los acuerdos originales para
resolver esas discrepancias.

Sin geometría comprobada (`geometry_status: unavailable`, `publication_ready:
false`). `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing`
están desactivados. No hay acceso a bases de datos, geocodificación o publicación.

## Verificación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_alcaudete -v` — seis pruebas correctas:
aislamiento territorial, varias páginas, agrupación, ámbitos multilínea y con
espaciado interno, ausencia de fechas/geometría inventadas, procedencia,
rechazo de secciones incompletas e índices vacíos/paginados y carga del manifest.

Extracción real mediante `load_manifest('alcaudete')` y
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['capture_dir'] = 'evidence'`. El registro aplica además
la política compartida de entidades: 17 registros, cero categorías desconocidas.
`update_proyectos` repite el inventario completo, sin cursor de fechas supuesto.

Resultados locales no destinados a commit:

- `evidence/proyectos.jsonl`: 17 registros reales, IDs únicos.
- `evidence/validation.json`: recuento vivo, URLs, limitaciones y pruebas.
- `evidence/inventory.html`, `inventory.pdf`, `inventory.txt`: fuentes de la
  extracción final y texto utilizado por el parser.

Solo se añaden los cuatro archivos fuente autorizados; no se modifica código
compartido, dependencias ni configuración de despliegue.
