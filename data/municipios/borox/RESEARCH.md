# Borox — Toledo — INE 45021

Investigación y extracción: 9 de noviembre de 2026. Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y descubrimiento

La búsqueda del inventario municipal de Urbanismo condujo a
https://www.ayuntamientodeborox.com/index.php/ayun/urbanismo .
Se descargó y examinó el HTML real del artículo Joomla, no solo el resultado del
buscador. Su sección **NORMAS SUBSIDIARIAS** contiene tres planos JPG y dos PDF
normativos del núcleo urbano y Nuevo Borox. Estos cinco documentos se agrupan en
**un instrumento**: no se convierten capítulos, ámbitos o planos de distintos años
en cinco actuaciones. Los rótulos originales y enlaces permanecen en `documentos`.
El título del registro procede del encabezado del inventario.

Documentos comprobados mediante descargas HTTP satisfactorias y firma de fichero:

- https://www.ayuntamientodeborox.com/images/Ordenacion_nucleo_borox_1984.jpg
- https://www.ayuntamientodeborox.com/images/ordenacion_nucleo_borox_1985.jpg
- https://www.ayuntamientodeborox.com/images/ordenacion_suelo_urbano_nuevo_borox.jpg
- https://www.ayuntamientodeborox.com/images/urbanismo/normas_para_nucleo_urbano.pdf
- https://www.ayuntamientodeborox.com/images/urbanismo/normas_para_urbanizacion_nuevo_borox.pdf

El PDF del núcleo contiene el capítulo III de las normas; el PDF de Nuevo Borox es
escaneado (la extracción local con pdftotext no produjo texto útil). Los planos se
conservan como fuentes documentales, sin derivar geometrías. El adaptador vuelve a
leer el inventario y descargar sus documentos en cada ejecución; verifica firmas y
registra hashes SHA-256, tipo de contenido y URL resuelta. No utiliza registros
precargados ni depende del directorio de evidencia para extraerlos.

## Exclusiones y cobertura parcial

El mismo artículo ofrece formularios de obra, segregación y actividades. No son
licencias concedidas y se excluyen; `licencias.enabled=false`.
También ofrece normativa de Antonio del Rincón y planos de polígonos industriales
(Borox, Antonio del Rincón y Jesús Menchero). Se descargó adicionalmente la normativa
de Antonio del Rincón: es una tabla de superficies y parámetros urbanísticos. Ni la
ficha ni la tabla identifican con suficiente precisión otro instrumento o proyecto
concreto, por lo que no se crea un expediente artificial a partir de ellos.

El resultado es un inventario documental parcial, no un histórico exhaustivo de
proyectos, obras o licencias del municipio. Tampoco acredita la vigencia jurídica
del instrumento. La página observada no tiene paginación: el parser rechaza
paginadores reconocidos (`rel=next`, `.pagination`, `.pagenav`) para evitar aceptar
una primera página sin revisión. Procesa todos los enlaces admisibles del bloque
NNSS, sin límite de resultados. Rechaza contenedores ausentes y documentos sin
firma válida, preservando el fichero de salida anterior si falla la extracción.

## Fechas, procedencia y geometría

1984 y 1985 son años de los rótulos de documentos, no fechas completas de
aprobación. El artículo muestra una modificación CMS del 4 de noviembre de 2026:
no se asigna como publicación del instrumento ni fecha de acuerdo. Los campos
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulos. No se afirma fase,
concesión, ejecución o aprobación. No hay coordenadas inventadas;
`geometry_status=unavailable`, `publication_ready=false`,
`geocode.jitter_missing=false` y `schedule.enabled=false`.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_borox -v`

Seis pruebas correctas: agrupación y procedencia, exclusión de formularios y
normativa aislada, ausencia de fechas inferidas, rechazo de fuentes vacías,
paginación y documentos externos, carga del manifiesto/licencias desactivadas y
preservación de la salida ante fallo de red.

Extracción real mediante `load_manifest('borox')`, `load_portal_adapter(manifest)`
y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir']='evidence'` únicamente para esta ejecución.
Resultado: **1 registro real y 5 documentos**. El envoltorio de política de
entidades clasificó su categoría como desconocida (`unknown=1`), sin impedir la
salida; no se fuerza una categoría de obra a un instrumento de planeamiento.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/urbanismo.html`, los cinco documentos y el
PDF adicional de Antonio del Rincón revisado para justificar su exclusión.
`validation.json` incluye recuento vivo, URLs y limitaciones. No se utilizaron
credenciales, bases de datos, publicación ni geocodificación. Las actualizaciones
refrescan la instantánea completa; no se simula un cursor incremental.
