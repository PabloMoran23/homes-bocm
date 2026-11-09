# Ortigueira — INE 15061, A Coruña (Galicia)

Consulta y extracción real: 2026-11-09. Adaptador exclusivo del municipio.

## Descubrimiento y fuente oficial

La sección municipal de Urbanismo, Medio Ambiente y Medio Rural
<https://concellodeortigueira.gal/obras-servizos-e-medio-rural/?lang=es>
enlaza «Plan de urbanismo»:
<https://concellodeortigueira.gal/obras-servizos-e-medio-rural/plan-de-urbanismo/?lang=es>.
Esta página oficial, accesible por HTTP 200, presenta inventarios con columnas de
figura, consulta/descarga, aprobación definitiva, BOP, DOG y normativa. Es una fuente
de descubrimiento de instrumentos, no una noticia individual fijada como semilla.

Se extraen íntegramente las tablas HTML `gralPlanTableSortable` (3 filas) y
`planDesTableSortable` (7 filas). Cada fila identifica un instrumento urbanístico
con un enlace Word oficial. Se descargan y validan los 10 Word como archivos DOCX
con `word/document.xml`; se conserva la URL y el SHA-256 del contenido. Los Word
examinados contienen índices documentales de planos, memorias, normativa y anuncios;
no se presentan como texto íntegro de los planes ni como acuerdos firmados.

La página también lista 13 instrumentos territoriales supramunicipales en
`iot-inv-table` (planes territoriales/sectoriales y parques eólicos). Esa tabla no
forma parte de la cobertura: se evita atribuir a Ortigueira un proyecto regional
completo. El enlace municipal a SIOTUGA apunta al antiguo dominio
`http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php` y no es una segunda
fuente de extracción. No se afirma haber agotado el registro autonómico.

## Registros y semántica

La extracción produce **10 instrumentos**, no 10 licencias ni obras ejecutadas:

- Normas subsidiarias de planeamiento.
- Modificación puntual NSP número 3, zona de Lagarea.
- Modificación puntual NSP números 4 y 5, 6 modificada, Xeneral Franco (una fila).
- Plan parcial SAUI, A Rega/Cuiña, identificado según el texto del enlace municipal.
- Modificación puntual del plan parcial SAUI número 1, polígono industrial A Rega/Cuiña.
- Estudio de detalle: alineación interior, enlace de documento Luciano Pita.
- Estudio de detalle: Rúa Outeiro, Espasante.
- Estudio de detalle: plaza de Santo Antonio do Porto, Espasante.
- Estudio de detalle: avenida Xeral Franco, Santa Marta.
- Estudio de detalle: avenida Penela número 8.

Los títulos de salida retienen la denominación de la tabla y, en planeamiento de
desarrollo, la etiqueta del enlace. El rótulo de Luciano Pita en la página aparece
incompleto; el nombre completo se reconoce en el inventario Word, pero el parser no
inventa el texto que falta en la tabla. No se interpreta el nombre de un archivo
como una nueva fecha o un expediente independiente.

`fecha_aprob` procede de «APROB. DEF»; `fecha_publicacion_bop`,
`fecha_publicacion_dog` y `fecha_publicacion_normativa` conservan cada columna.
`fecha_publicacion` queda nula: no hay una fecha verificada de publicación de la
página. No se confunden aprobación y publicación ni se calcula una fecha de entrada
en vigor. Celdas ausentes o vacías quedan nulas. Los acuerdos consignados van de
1993 a 2012 y se transcriben tal como constan en la página, sin corregir posibles
errores históricos del inventario.

Los documentos de la misma fila/instrumento se agrupan en `documentos`; filas
repetidas con igual título y fechas se fusionan, conservando todos los enlaces.
Una modificación y el plan que modifica siguen siendo instrumentos distintos.
Las identidades estables derivan del título, no del orden de la tabla.

## Cobertura, paginación y geometría

**Cobertura parcial**: inventario municipal publicado, sin certificación de vigencia
actual ni de exhaustividad. No abarca todos los proyectos/obras municipales, la
tramitación reciente, documentos técnicos completos ni registros autonómicos.
Formularios, anuncios de contratación y noticias quedan fuera de las tablas
admitidas. No se ha verificado un inventario de licencias concedidas; sus métodos
escriben cero registros y su extracción está deshabilitada.

Las dos tablas ofrecen todas sus filas en el HTML recibido. Aunque tienen clases
y atributos DataTables, no presentan controles ni metadatos activos de paginación,
ni una carga AJAX de esas tablas en el contenido examinado. No se aplica límite de filas. El parser
rechaza controles de continuación, metadatos de paginación, carga dinámica,
cambios de esquema, tablas vacías y pérdida de enlaces, en lugar de aceptar una
primera página parcial. Una futura paginación requiere ampliar el recorrido.
`update_proyectos` renueva la instantánea completa; no promete historial incremental.

`geometry_status: unavailable`. Los inventarios Word enumeran planos, pero no hay
geometría vectorial asociada verificada. No se vectorizan planos, no se usa el
centroide municipal y no se inventan coordenadas. `lat`, `lon`, `geometry` nulos;
`publication_ready: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `python -m unittest municipio.test_ortigueira -v` con ese runtime: **6 pasan**.
Cubren fechas separadas, instrumentos con igual figura y distinta ubicación,
agrupación de documentos, estabilidad de ID, rechazo de fuentes incompletas o
paginadas, manifest, carga por registry y licencias deshabilitadas.

La extracción real se ejecuta mediante `load_manifest('ortigueira')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Se usa `portal.config.evidence_dir` solo en la ejecución local para capturas. Los
métodos verifican también los documentos remotos antes de escribir la instantánea.

Evidencias locales, no destinadas al commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (recuento, URLs y limitaciones), HTML de la página y
capturas DOCX. `schedule.enabled: false`. Sin cambios compartidos, dependencias,
base de datos, publicación ni despliegue.

La política de entidades compartida del registry devuelve `adapter_incident` con
`unknown_entity_spike`: los 10 registros quedan como `pendiente` y
`activity_eligible: false`, porque estas filas no aportan una referencia oficial de
expediente utilizable por esa política. La identidad del scraper no sustituye una
referencia oficial. Se conserva este resultado en las evidencias y no se altera la
política compartida ni se inventan números para superar la clasificación. La
extracción del inventario es utilizable para revisión documental, sin validación
para publicación o cómputo de actividad.
