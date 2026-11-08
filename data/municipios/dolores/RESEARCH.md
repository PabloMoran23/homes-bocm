# Dolores — Alicante — INE 03064

Investigación y extracción real: 8 de noviembre de 2026.

## Fuente oficial y alcance

Inventario municipal seleccionado:
https://www.dolores.es/el-ayuntamiento/departamentos-municipales/urbanismo/

La página oficial de Urbanismo contiene una sección PGOU con la descarga
completa del Plan General de Ordenación Urbana y once documentos numerados:
índice, índice de memoria, memoria, dos anexos de memoria, normativa,
refundido de normativa, ordenanzas, ordenanzas modificadas, refundido de
ordenanzas y planos. Se extrae **un instrumento**, con **doce enlaces** en
`documentos`. Los componentes y refundidos no se presentan como proyectos
independientes ni se presupone qué versión prevalece jurídicamente.

La búsqueda también localizó la versión municipal inglesa de la misma página
(https://www.dolores.es/en/city-hall/city-departments/town-planning/), que
publica el mismo inventario: no se duplica. El portal enlaza la sede electrónica
de Dolores (https://dolores.sedelectronica.es/info.0) y su perfil del
contratante. No se ha acreditado allí un registro extraíble de licencias
concedidas. Los anuncios de contratación localizados en la búsqueda no se
convierten en proyectos ni en obras ejecutadas; quedan fuera del adaptador.

La cobertura es parcial y documental, limitada al PGOU publicado en esta
página. No incluye una relación histórica de modificaciones, expedientes,
licencias, todos los planes municipales ni todas las obras públicas. La fuente
HTML está disponible actualmente; eso no demuestra que todos sus documentos
sean vigentes. La antigüedad del contenido o los directorios de subida no se
interpretan como fechas de aprobación o de publicación del instrumento.

## Extracción y semántica

Se exige el contenedor de contenido municipal y una única sección PGOU. Se
recogen todos sus enlaces PDF/ZIP, con título documental y URL de procedencia;
se deduplican por URL. Se comprueba que haya descarga completa, memoria,
normativa y numeración consecutiva. Se rechazan contenido vacío, formularios,
enlaces ajenos, estructura ambigua y marcadores de paginación. El inventario
observado se sirve en una sola página, sin paginación: no se aplica un límite
de resultados. Si aparece paginación, la ejecución falla para revisión.

El identificador estable `dolores-pgou` corresponde al instrumento nombrado
por la fuente, no a una actuación deducida de una página genérica. Las
actualizaciones regeneran esta instantánea completa sin usar una marca
temporal que pueda ocultar documentos antiguos.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan
nulas: esta página no acredita esos datos. No se extraen fechas del CMS, del
nombre de los archivos ni del encabezado HTTP. Coordenadas y geometría nulas;
`geometry_status: unavailable` y `publication_ready: false`. No se infiere
ejecución, concesión de licencia o aprobación a partir de la disponibilidad
de un documento. El manifiesto desactiva licencias, programación y jitter.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_dolores -v`, **5 correctas**.
Cubren agrupación y procedencia, fechas y geometría desconocidas, duplicados,
rechazo de fuentes inutilizables/paginadas, instantánea incremental,
licencias desactivadas e identidad y opciones del manifiesto.

Ejecución real de `DoloresAyuntamientoAdapter.backfill_proyectos` con la
configuración del manifiesto y `evidence_dir` local: **1 registro**, **12
documentos enlazados**. Los doce destinos respondieron correctamente y sus
primeros bytes tienen firma PDF o ZIP válida. Esta comprobación es de acceso
y formato, no una lectura jurídica ni una validación completa de los archivos.

Evidencia local, fuera de los cuatro archivos fuente:

- `evidence/proyectos.jsonl`: registro real con todos los enlaces.
- `evidence/urbanismo.html`: HTML recuperado por el propio adaptador.
- `evidence/validation.json`: recuento, URLs, limitaciones, respuestas HTTP,
  tipos de contenido, destinos finales y comprobaciones de firma.
- `evidence/document-01.prefix` a `document-12.prefix`: capturas parciales de
  1024 bytes, no archivos completos. Algunos servidores ignoran Range; el
  cliente cierra la respuesta tras leer el prefijo.

No se usaron bases de datos, publicación, despliegues ni geocodificación.
