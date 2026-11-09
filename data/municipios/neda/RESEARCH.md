# Neda — A Coruña — INE 15055

Investigación y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

- Web municipal: https://neda.gal/ . Su navegación enlaza la sede y el portal de transparencia. La categoría https://neda.gal/category/urbanismo/ contiene noticias, incluidas licitaciones de cartografía; no es un registro de licencias ni un inventario completo de actuaciones. No se extraen esas noticias.
- https://sede.neda.gal/opencms/gl/portal_transparencia/ redirige actualmente al inicio de la sede. Los procedimientos de comunicación previa/licencia describen trámites, no concesiones; se excluyen.
- Inventario oficial de la Xunta: https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15055 . El selector oficial confirma `15055 = Neda`. Ayuda sobre el inventario y su alcance: https://siotuga.xunta.gal/siotuga/axuda?lang=es_ES . El manifest usa el canal `proyectos.source: ayuntamiento` del pipeline municipal, pero identifica expresamente SIOTUGA/Xunta como procedencia; los registros llevan `source: xunta_siotuga`.

El HTML del inventario carga `assets/inventario/controls.min.js?2.5.0`, capturado en `evidence/inventario.js`. Ese cliente permite reproducir las consultas públicas, sin sesión privada: obtiene un token de formulario público nuevo desde el HTML y hace POST a `assets/inventario/query_document.php` con `id=15055`, `idclase` y dicho token. Se consultan todas las clases municipales que usa el cliente: 14 (general), 13 (desarrollo), 16 (histórico), 18 (delimitación rural). Esta última devuelve JSON null. Las respuestas son arrays completos; el JavaScript construye todas las filas y después activa DataTables para paginación local. No hay límite de registros ni truncamiento en el adaptador. Una respuesta con envoltorio de paginación o esquema distinto genera error, sin sobrescribir el resultado anterior.

Cada instrumento se consulta mediante POST a `assets/inventario/getIOTPU.php`, con `iddoc`, `idp=0`, `lang=gl_ES` y el token público. `datos_xerais` identifica municipio, instrumento, carpeta y fechas. Se valida la identidad y Neda antes de aceptar el detalle. Las URLs de los componentes se reconstruyen exactamente como en el cliente oficial: `filesroot + folder + /documents/ + pathesperado`, relativas a la raíz SIOTUGA. El registro retiene la URL de inventario y la procedencia POST reproducible con identificador, sin fijar tokens temporales.

## Resultado real y agrupación

| ID SIOTUGA | Instrumento | Aprobación según SIOTUGA | Documentos |
| --- | --- | --- | --- |
| 22402 | Normas subsidiarias de planeamento | 1992-07-22 | 52 |
| 25543 | Plan especial de reforma interior Xubia-Casadelos (PE-2) | 2005-02-18 | 60 |
| 25935 | Estudio de detalle para reajustar alineaciones/rasantes y volúmenes, Avda. Algeciras esquina Avda. Castelao | 2006-07-20 | 0 |
| 26396 | Histórico: normas subsidiarias de planeamento | 1980-02-13 | 19 |

**4 instrumentos, 131 enlaces documentales.** No se producen 131 proyectos. Los grupos documentales, títulos, identificadores y URLs permanecen dentro de su instrumento. IDs repetidos entre clases se agrupan y se rechazan contradicciones. El estudio de detalle es una ficha oficial auténtica con `elementos: null`; declara `sin_documentos_disponibles`. El instrumento de 1980 conserva la categoría histórica y `historico: true`, evitando afirmar su vigencia.

## Semántica y cobertura parcial

`fecha_aprob` procede exclusivamente de `fechaaddef` (aprobación definitiva informada por SIOTUGA). BOP, DOG, publicación de normativa BOP y texto refundido tienen campos separados. No se convierte una publicación en fecha de acuerdo y no se asigna fecha genérica. Las incidencias jurídicas se conservan. No se infiere ejecución de obras, vigencia legal, concesión de licencia, fase o coordenadas. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`.

Se cubre el inventario municipal de planeamiento expuesto actualmente, incluido el histórico, sin afirmar exhaustividad de todos los expedientes del ayuntamiento o de las obras físicas. La consulta regional separada `assets/iot/queryIotInv.php` se exploró y capturó: ofrece instrumentos territoriales de ámbito supramunicipal (directrices, planes sectoriales, red viaria, gasificación, etc.). Quedan explícitamente fuera de esta implementación. Tampoco se recorren todas las noticias, actas de plenos o anuncios de contratación. No se ha verificado un registro público de licencias concedidas; `licencias.enabled=false`. Programación y jitter geográfico desactivados.

## Validación y evidencia local

- `python -m unittest municipio.test_neda -v`: 6 pruebas correctas con el runtime indicado. Comprueban agrupación, fechas, histórico, documentos ausentes, aislamiento municipal, identidad, rutas, rechazo de envoltorios paginados, consulta de las cuatro clases, deduplicación y conservación de la salida anterior ante fallo parcial.
- Extracción live usando `load_manifest('neda')` y `load_portal_adapter(...).backfill_proyectos(...)`: 4 registros. Se ejecutó también la anotación compartida del registro de adaptadores: clasifica los cuatro como desconocidos, sin inventar referencias de expedientes municipales para forzar elegibilidad. Los IDs son identidades de catálogo, no números de expediente de obra.
- `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML y respuestas JSON de todas las clases y detalles contienen la evidencia local. Las capturas `discovery_*` corresponden a la exploración previa.
- Se verificó un PDF por cada instrumento que ofrece PDFs: HTTP 200 y cabecera `%PDF-`, conservando solo los primeros 1024 bytes en archivos `.pdf.prefix`. Los tres controles constan en validation.json. No se descargaron ni validaron todos los 131 documentos, ni se extrajeron geometrías de planos escaneados.
- Actualización: refresco completo del inventario, ya que las fechas de aprobación no permiten detectar publicaciones nuevas de instrumentos antiguos. Fallos HTTP, respuestas inesperadas o inventario completamente vacío abortan la extracción. No hay publicación, acceso a bases de datos ni geocodificación.
