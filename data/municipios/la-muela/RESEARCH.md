# La Muela — Zaragoza — INE 50182

Investigación y extracción real: 9 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py`, el cargador de adaptadores
y los ejemplos de Manlleu, Hernani y Chipiona. No se modifica código compartido.

## Inventarios oficiales descubiertos

* [Área de Urbanismo](https://lamuela.org/areas/urbanismo/): descripción genérica
  de servicios y planos del municipio y la urbanización. No es un inventario de
  proyectos concretos ni permite afirmar concesiones de licencias.
* [Archivo de Urbanismo](https://lamuela.org/category/urbanismo/): fuente del
  adaptador. En la captura actual hay siete artículos: seis avisos de tráfico y
  una memoria de modificación del PGOU con expediente y documentación. El widget
  publica `data-post-limit="-1"`, `data-pagination-mode="standard"`, sin enlaces de
  paginación. No se recorta el listado. El rastreador sigue páginas HTML enlazadas,
  deduplica URLs y falla ante paginación dinámica o más de cien páginas; nunca
  escribe un resultado parcial si falla una página o un detalle seleccionado.
* [Actuaciones/proyectos PRTR](https://lamuela.org/el-ayuntamiento/plan-de-recuperacion-transformacion-y-resiliencia/actuaciones-proyectos-del-ayuntamiento-de-la-muela-financiados-con-fondos-prtr/):
  inventario adicional consultado, fuera del alcance de esta implementación.
  Contiene referencias a Residencia San Roque (1306/2021), fondos bibliográficos
  (1322/2022) y renovación de abastecimiento de Calle Huesca y adyacentes
  (347/2022). No se convierten las convocatorias de subvención en aprobaciones
  de proyectos ni se afirma cubrir este inventario.

## Registro extraído y procedencia documental

La [ficha municipal](https://lamuela.org/memoria-justificativa-de-modificacion-del-pgou/)
identifica el **expediente 1808/2024**, modificación del PGOU sobre compatibilidad
del uso deportivo con educativo. Se extraen asunto, descripción, identificador y
fecha de publicación del artículo en el archivo: **2024-08-28**. Se agrupan en un
solo instrumento los dos documentos de la ficha, conservando título, URL y
`url_procedencia`:

* [Anuncio BOPZ 6251/2024](https://lamuela.org/wp-content/uploads/2024/04/bop-6251-2024.pdf).
* [Memoria justificativa](https://lamuela.org/wp-content/uploads/2024/04/20240822-Otros-2024-1808-01-Mem-Just-Mod-Usos-dotacional-deportivo.pdf).

Ambos se descargaron para evidencia: HTTP 200, `application/pdf` y firma `%PDF-`.
El texto del BOPZ (número 198, de 28 de agosto de 2024) identifica resolución
2024-1952 de **22 de agosto de 2024**, aprobación inicial y exposición pública de
un mes. La firma del anuncio es de 23 de agosto. Estas fechas son distintas de la
publicación. La ficha menciona además providencia de 19 de agosto e informe de
Secretaría de 28 de junio; no son fechas de aprobación del instrumento.

El adaptador analiza HTML, no el contenido de PDF: `fecha_acuerdo`, `fecha_aprob`
y `fase` quedan nulos. No deduce fechas de los nombres de archivos ni de las
carpetas `/2024/04/`, que no coinciden con las fechas de los documentos. Tampoco
toma las fechas de las noticias relacionadas que aparecen en la ficha.

## Cobertura y límites

Resultado de la ejecución real: **1 instrumento**, **2 enlaces documentales**.
Cobertura parcial del archivo municipal de Urbanismo, no un registro completo de
planeamiento vigente, histórico urbanístico, actuaciones PRTR u obras municipales.
Las noticias de cortes de calle, formularios y licitaciones no se emiten como
instrumentos. Si hay varios anuncios del mismo expediente, se agrupan y conservan
todas las publicaciones y los documentos sin mezclarlos con otros expedientes.
Cambios estructurales, ausencia de instrumentos o falta de documentos provocan
error explícito. Las actualizaciones refrescan el archivo completo.

No se extraen licencias otorgadas. `licencias.enabled=false`,
`schedule.enabled=false` y `geocode.jitter_missing=false`. Sin coordenadas ni
geometría verificadas; `publication_ready=false`. No se afirma vigencia actual,
aprobación definitiva, ejecución material ni concesión de licencia.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_muela -v
```

Seis pruebas: semántica de fechas y enlaces, exclusión de avisos/formularios,
fallo ante cambios de estructura, recorrido paginado y agrupación con aislamiento
entre expedientes, conservación del resultado previo ante fallo y carga del
manifest. Extracción real mediante `LaMuelaAyuntamientoAdapter.backfill_proyectos`
con `capture_dir=evidence/live`. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/parser-tests.txt`, capturas HTML de investigación y ejecución, los dos
PDF y el texto del anuncio BOPZ. Sin publicación, base de datos ni geocodificación.
