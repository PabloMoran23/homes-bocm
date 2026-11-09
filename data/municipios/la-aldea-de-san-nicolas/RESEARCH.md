# La Aldea de San Nicolás — INE 35020, Las Palmas

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes y alcance

Se revisaron primero `municipio/adapters/portal.py`, los adaptadores existentes,
los manifiestos de Chipiona y Hernani y `municipio/manifest.py`. La fuente municipal
localizada fue https://laaldeasanicolas.es/plan-general-de-ordenacion/; el acceso
directo terminó con ConnectTimeout y no se utiliza como evidencia descargada.

La fuente operativa es el catálogo público oficial del Gobierno de Canarias,
producido/mantenido por Gobierno de Canarias y sistematizado por GRAFCAN:

- https://datos.canarias.es/catalogos/general/dataset/planeamiento-urbanistico-de-la-aldea-de-san-nicolas
- https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=planeamiento-urbanistico-de-la-aldea-de-san-nicolas

El endpoint `package_show` devuelve el inventario completo de recursos del conjunto,
no una página de búsqueda. Se exige `success=true`, identidad exacta del conjunto,
estado activo y coincidencia entre `num_resources` y la longitud del inventario.
No hay límites de extracción ni cortes por número de registros. Si aparece
paginación en un índice documental el parser falla, sin aceptar cobertura truncada.

Resultado real: **5 instrumentos**, **17 distribuciones**, **348 enlaces PDF**.
Las distribuciones SIPU/FIP, consultas GRAFCAN e índices documentales se agrupan
por la denominación del instrumento, eliminando solo el sufijo de publicación para
la identidad. Se conserva el nombre completo y descripción de cada distribución.
Las adaptaciones territoriales se mantienen separadas; cada PDF conserva su índice
como procedencia y solo se acepta dentro de la carpeta del instrumento.

| Instrumento | Índice oficial | PDF enlazados |
| --- | --- | ---: |
| Plan General de Ordenación Supletorio | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/PGOS/indice.html | 136 |
| Adaptación Básica al D.L. 1/2000 del PGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/287/indice.html | 182 |
| Adaptación del PGO, DT 1ª Ley 4/2017, El Convento | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/convento/indice.html | 1 |
| Adaptación del PGO, DT 1ª Ley 4/2017, Los Caserones | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/caserones/indice.html | 1 |
| Plan Especial de la Desembocadura del Barranco | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/LAld/288/indice.html | 28 |

Los cinco índices respondieron HTTP 200. También se verificaron HTTP 200,
`application/pdf` y firma `%PDF-` leyendo únicamente los primeros 1024 bytes del
PDF de El Convento: `TNP/adpgo-las-dt1ley417-convento-dop-po.pdf`.
No se descargaron ni interpretaron íntegramente los 348 documentos.

## Semántica y límites

Son instrumentos reales identificados en un catálogo oficial de planeamiento
municipal, no noticias ni anuncios de contratación ni formularios de licencia.
El catálogo contiene instrumentos históricos: no se afirma que todos estén vigentes,
que sean obras ejecutadas o que la cobertura agote el planeamiento y las obras del
municipio. `source=gobierno_de_canarias` identifica al publicador real; el valor
`proyectos.source=ayuntamiento` del manifiesto selecciona el flujo de adaptador del
portal municipal del esquema existente, no implica autoría municipal del catálogo.

Los títulos/descripciones originales contienen fechas de acuerdo y publicación:
se conservan como texto sin transformarlas en fechas estructuradas. Los campos
`created`, `issued`, `metadata_modified` y `modified` del catálogo no acreditan la
fecha de aprobación del instrumento. En particular, el catálogo cita 19/07/2017
para ambas adaptaciones a la Ley 4/2017; no se corroboró que sea fecha del acto de
adaptación. Tampoco se corrige la fecha COTMAC 21/01/2001 del título del Plan
Especial. No se inventan fechas, fases, expedientes ni coordenadas.

Todos los registros indican `publication_ready=false`, `geometry_status=unavailable`
y cobertura documental. Licencias desactivadas: no se ha verificado un registro
público de concesiones. `schedule.enabled=false` y `geocode.jitter_missing=false`.
La actualización vuelve a leer todo el inventario; no usa fechas del catálogo como
cronología incremental. Un error de fuentes no sustituye el JSONL previo.

## Verificación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_aldea_de_san_nicolas -v`: **5 correctas**.
Cubren agrupación, exclusión de formularios, procedencia, ausencia de fechas
inventadas, separación territorial de documentos, rechazo de inventarios
incompletos, paginación, errores de fuente y conservación del resultado previo.

Extracción real mediante `LaAldeaDeSanNicolasAyuntamientoAdapter.backfill_proyectos`,
instanciado con el manifiesto y `config={'evidence_dir': 'evidence'}`; salida
`evidence/proyectos.jsonl`. No se ejecutó ningún flujo de publicación o base de datos.

Evidencia local no destinada a commit: `evidence/validation.json` con `live_records=5`,
fuentes y limitaciones; `regional-inventory.json`; los cinco `*-index.html`;
`document-check.json` y `sample-document-prefix.bin`. El adapter permite capturar
las respuestas descargadas mediante `config.evidence_dir`; no reutiliza las capturas
como sustituto de una petición real.
