# Chinchilla de Monte-Aragón — INE 02029, Albacete

Comprobación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y descubrimiento

La web del Ayuntamiento, https://www.webchinchilla.com/, enlaza su sección
[Urbanismo](https://www.webchinchilla.com/urbanismo/). Esta identifica expresamente
el **Plan de Ordenación Municipal** y ofrece nueve botones de documentación:

| Sección descubierta | PDF únicos en la sección |
| --- | ---: |
| Memoria informativa | 2 |
| Planos de información | 104 |
| Memoria de ordenación | 2 |
| Planos de ordenación | 77 |
| Anexos | 13 |
| Normas urbanísticas | 9 |
| Edificios catalogados | 36 |
| Escudos | 24 |
| Ordenanzas municipales de la edificación y la urbanización | 2 |

Se recorren los botones del bloque del POM hasta el siguiente encabezado de
instrumento. Cada sección se descarga completa y se comprueba su encabezado.
No se fija una noticia ni una lista local de PDF como fuente de registros.
Resultado: **un instrumento real con 269 documentos**, no 269 proyectos.
Los nombres completos proceden del nombre de archivo, pues algunos textos visibles
están abreviados. La identidad de cada documento es el ID municipal de descarga;
se eliminan enlaces duplicados de icono/texto y se retienen las secciones de origen.
Todos los enlaces y sus procedencias están en `evidence/proyectos.jsonl`.

La sección Urbanismo ofrece después «URBANIZACIÓN AR5», con dos normas zonales.
Ese bloque no forma parte de la extracción del POM ni se convierte automáticamente
en un proyecto de obra o una aprobación de plan parcial.

## Otras fuentes y cobertura parcial

La navegación municipal enlaza la sede con entidad 02029 y
https://chinchillademontearagon.sedipualba.es/transparencia.
La sede https://chinchillademontearagon.sedipualba.es/ enlaza el
[tablón oficial](https://chinchillademontearagon.sedipualba.es/tablondeanuncios/).
Los tres endpoints responden HTTP 200; se conservan capturas locales. En el tablón
se observan cinco páginas, anuncios de instalaciones energéticas y numerosos actos
no urbanísticos. **Este adaptador no extrae el tablón**, ni la primera página ni su
histórico: la cobertura declarada es exclusivamente el inventario documental del
POM. Tampoco cubre todas las modificaciones del planeamiento ni obras municipales.
No se deducen licencias concedidas de trámites, convocatorias, formularios o títulos
de anuncios; licencias permanece deshabilitado.

Las páginas del POM examinadas no muestran paginación. Se recorren todas las nueve
secciones sin límite de documentos. La aparición de enlaces de página/siguiente
provoca error explícito. También se falla si falta el inventario, cambia el título
de una sección, desaparecen sus documentos, o se recibe una descarga inesperada.
Un fallo no reemplaza una extracción previa por datos incompletos. Las actualizaciones
refrescan este inventario completo, sin interpretar desapariciones como derogaciones.

## Fechas, vigencia y geometría

Publicación, acuerdo y aprobación quedan en null: el HTML no acredita sus fechas.
La disponibilidad actual de estos archivos no acredita vigencia legal consolidada,
fase de tramitación ni aprobación definitiva. La memoria enlazada identifica el
POM, pero su narrativa histórica no se usa para inventar fechas del instrumento.
No se usan marcas de caché, fechas del buscador o fechas de descarga como aprobación.

geometry_status: unavailable

Hay planos PDF, incluidos usos y clasificación del suelo. No se ha verificado una
geometría vectorial o visor con identificador enlazable a este instrumento. No se
vectorizan planos, no se asigna centroide municipal y no se inventan coordenadas.
`publication_ready` es false. El clasificador compartido devuelve `pendiente` por
identidad insuficiente para actividad: la página no aporta número de expediente;
no se añade una referencia artificial para eludirlo. Es un inventario documental
real, no evidencia de nueva actividad constructiva.

## Validación reproducible y evidencias locales

Pruebas: `python -m unittest municipio.test_chinchilla_de_monte_aragon -v` con el
runtime indicado: **4 pruebas correctas**. Cubren descubrimiento, exclusión del
siguiente bloque, deduplicación, procedencia múltiple, fechas vacías, configuración,
rechazo de paginación/cambios y preservación de salida ante fallo.

Extracción real realizada mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando `evidence_dir`
local para guardar los diez HTML leídos por el adaptador. `evidence/validation.json`
registra `live_records: 1`, los 269 documentos, todas las URLs, limitaciones y el
resultado de la política compartida. Se conserva además una muestra PDF de la
memoria de ordenación y su texto. Los 269 enlaces se descubrieron en vivo; no se
ha comprobado la descarga individual de todos los PDF.

Solo cuatro archivos fuente añadidos. Evidencia local excluida de Git. Sin cambios
compartidos, dependencias nuevas, publicación, ejecución de pipeline completo o BD.
`schedule.enabled: false`, `geocode.jitter_missing: false`, `licencias.enabled: false`.
