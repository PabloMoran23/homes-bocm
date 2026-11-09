# Cacabelos — INE 24030, León

Verificación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y selección

La página municipal de [Urbanismo](https://www.cacabelos.org/ayuntamiento/urbanismo/)
conduce a [Normativa urbanística](https://www.cacabelos.org/ayuntamiento/urbanismo/normativa-urbanistica/).
Esta última enlaza expresamente al [Archivo de Planeamiento Urbanístico y Ordenación del Territorio de la Junta](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=030).
El archivo identifica CACABELOS, código INE 24030. La página municipal acredita
la procedencia y el archivo autonómico aporta el inventario estructurado y los
listados documentales. La extracción comprueba ese enlace municipal en cada ejecución.

El inventario actual sin activar «Mostrar históricos» contiene cuatro instrumentos:

| cDocId | Instrumento | Publicación | Acuerdo | Ficheros |
| --- | --- | --- | --- | --- |
| 280775 | Normas Subsidiarias de Planeamiento Municipal | 2001-05-17 | 2000-09-29 | 4 |
| 282708 | Modificación puntual 1/2004 | 2006-02-28 | 2005-06-30 | 6 |
| 283374 | Modificación de NN.SS. reordenando manzana «Antigua Bodega Carpal» | 2006-07-31 | 2006-06-30 | 3 |
| 282164 | Plan parcial «Parque de la Pequeña Industria» | 2004-04-06 | 2003-12-19 | 1 |

Listados de documentos, uno por instrumento:

- https://servicios.jcyl.es/PlanPublica/ldoc_files.do?cDocId=280775
- https://servicios.jcyl.es/PlanPublica/ldoc_files.do?cDocId=282708
- https://servicios.jcyl.es/PlanPublica/ldoc_files.do?cDocId=283374
- https://servicios.jcyl.es/PlanPublica/ldoc_files.do?cDocId=282164

Cada registro corresponde a un instrumento identificado por `cDocId`, con todos
sus ficheros en `documentos`, sus nombres, enlaces `openFichero.do?cFicheroId=...`
y listado de procedencia. Se eliminan los identificadores temporales de sesión
de las URLs. No se convierten catorce ficheros en catorce proyectos. Los títulos,
identificadores y fechas se extraen del HTML vivo, sin catálogo precargado.

La página municipal también ofrece catálogo, memoria, planos y mapas topográficos.
No se crean instrumentos independientes para esos documentos ni se les asigna una
identidad PLAU sin verificarla. Se descargó la memoria municipal durante la
investigación; sus primeras páginas no aportaron texto extraíble con pdftotext.
La sección [Obras](https://www.cacabelos.org/ayuntamiento/urbanismo/obras/) solo enlaza
información de inspección técnica de edificios, no un inventario de obras físicas.
La sede electrónica aparece como acceso municipal público y anuncia solicitudes:
no se ha verificado un registro de licencias concedidas; licencias desactivadas.
No se extraen anuncios de contratación, formularios ni noticias ajenas a instrumentos.

## Semántica y límites

Cobertura parcial municipal: inventario PLAU consultable actualmente, excluyendo
históricos y sin pretender un censo de todas las obras, expedientes o revisiones
en tramitación. Que los documentos estén hoy publicados no acredita por sí solo
su vigencia jurídica o el estado actual de ejecución.

`fecha_publicacion` y `fecha_acuerdo` reproducen columnas distintas del archivo.
No se transforma el acuerdo en `fecha_aprob`, ni se utiliza la fecha de publicación
como aprobación. `fecha` y `fecha_aprob` son nulas; no se infiere fase. No se generan
coordenadas ni geometrías a partir del centro municipal o de imágenes de planos.
`publication_ready: false`, `geometry_status: unavailable`, programación y jitter
desactivados en manifest.

El inventario revisado tiene cuatro filas, por debajo del tamaño de página
observado (15), sin controles activos para otras páginas. Los listados de ficheros
tienen 4/6/3/1 filas, sin paginación. El adaptador aborta expresamente si encuentra
paginación (incluidos controles JavaScript con `pager.offset`), una página llena
de 15 filas, cambio de esquema, municipio distinto o documentos ausentes.
No publica una primera página truncada. Para fuentes futuras paginadas será
necesario ampliar el recorrido. Las actualizaciones refrescan el snapshot completo;
un fallo antes de terminar conserva el archivo anterior y no modifica el estado.

La anotación compartida de entidades deja estos cuatro registros como `pendiente`
por no disponer de una referencia administrativa de expediente reconocida por esa
política. Se conserva ese resultado en la evidencia: `plau_id` es un identificador
de catálogo oficial y no se presenta artificialmente como número de expediente.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cacabelos -v`

Resultado: **10 pruebas correctas**. Cubren identidad municipal, fechas distintas,
ausencia de datos inferidos, agrupación de documentos, separación de instrumentos,
exclusión de formularios/contratación, cambios de esquema, paginación y conservación
del snapshot ante fallo. Fixtures HTML pequeñas incluidas en el archivo de pruebas;
no dependen de red ni de los archivos locales de evidencia.

Extracción real mediante `load_manifest('cacabelos')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando `capture_dir`
solo en memoria para guardar capturas locales. Resultado: **4 registros, 14 enlaces
documentales**. Se comprobó un PDF por instrumento: cuatro respuestas HTTP 200,
`application/pdf` y firma `%PDF-`. Solo se conservaron 2048 bytes por PDF, sin
comprobar íntegramente el contenido de todos los ficheros. Los endpoints HTTPS
oficiales redirigen esos documentos a `http://www.jcyl.es/plaupdf/...`.

Evidencia local excluida del control de versiones: `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML municipal y PLAU, y prefijos PDF. `validation.json`
registra recuentos, URLs efectivamente consultadas, comprobaciones documentales,
política compartida y límites. Sin publicación, bases de datos ni geocodificación.
