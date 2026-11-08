# Palomares del Río — Sevilla — INE 41070

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

- [Indicador municipal de modificaciones del PGOU y planes parciales](https://transparencia.palomaresdelrio.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00031/).
- [Documentación del nuevo PGOM](https://www.palomaresdelrio.es/es/pgom/documentacion/).

Se descubrieron desde las áreas de Urbanismo, PGOM y el portal de transparencia municipal. El inventario de transparencia tiene ocho bloques: se excluye la consulta del reglamento del registro de entidades urbanísticas porque no constituye un instrumento de ordenación ni una obra. Los restantes siete bloques representan cinco instrumentos, tras agrupar fases. La documentación PGOM aporta un sexto instrumento real en proceso de redacción, respaldado por su documento informativo; no se presenta como plan aprobado.

Resultado: **6 registros**, correspondientes a:

1. Actuación de Transformación Urbanística ARI-1 Casa Alegre.
2. Modificación de la Ficha 10 del Catálogo, Casa Alegre.
3. Innovación décima del PGOU, relativa a usos de gasolineras y servicios auxiliares.
4. Estudio de detalle de parcelas 19, 20 y 21, SUZ-PP-07 El Villarejo.
5. Modificación del Plan Parcial SUZ-PP-08 El Zorrero.
6. Plan General de Ordenación Municipal, con documentación informativa de su redacción.

Los documentos iniciales, definitivos y de consulta de cada instrumento se agrupan conservando todos los enlaces oficiales y los títulos originales en `documentos` y `source_sections`. En Casa Alegre se separan los dos instrumentos: los anuncios/certificados comunes se vinculan a ambos; el documento específico de la ATU y el de la ficha no se mezclan. La propuesta de ordenación previa se conserva con la ATU. El anuncio inicial y el certificado del Pleno descargados confirman que son dos instrumentos tramitados conjuntamente.

El PDF titulado `EXPEDIENTE EST. DETALLE NUEVO`, ubicado por el ayuntamiento en la carpeta de innovación décima, tiene en su primera página el expediente **2020/URB_01/000012, MODIFICACIÓN Nº 10 DEL PGOU; GASOLINERAS**. Se comprobó su contenido: pese al nombre ambiguo del archivo, pertenece a la innovación décima. Se conserva su título fuente sin reinterpretarlo como otro estudio de detalle.

## Exclusiones y límites

[Documentos de Urbanismo](https://www.palomaresdelrio.es/es/urbanismo/documentos/) contiene solicitudes, declaraciones responsables y autoliquidaciones, además de paginación. No se emplea como fuente de licencias ni de proyectos. Las noticias generales, anuncios de contratación y formularios no generan registros.

La cobertura es parcial: dos inventarios documentales actualmente accesibles, no un histórico exhaustivo de todas las actuaciones del municipio ni un registro de concesiones de licencia. No se infiere vigencia legal ni estado de ejecución de los encabezados del CMS. No se asignan coordenadas ni fechas. En particular, las fechas de acuerdo, publicación en BOP, firma y redacción de documentos pueden ser diferentes: se retienen los documentos originales en lugar de atribuir una fecha única al instrumento. Las fechas incorporadas a nombres de archivo tampoco se convierten en fechas de aprobación.

Los colectores OpenCMS de las galerías de transparencia declaran totales de 1, 2, 2, 3, 3 y 9; todos caben en la página observada. Los enlaces adicionales de Casa Alegre y El Zorrero se sirven como enlaces directos fuera de esas galerías. El colector PGOM declara un documento. El parser comprueba los totales contra los enlaces y rechaza paginación activa, cambios de secciones no reconocidos, ausencia de instrumentos o documentos y redirecciones inesperadas. Si aparece paginación no soportada, falla para revisión: no devuelve una primera página incompleta.

## Validación reproducible y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_palomares_del_rio -v`

Cinco tests correctos: agrupación de fases y separación de instrumentos, exclusión de reglamentos/formularios y enlaces externos, ausencia de fechas o geometría inferidas, rechazo de vacíos/paginación/totales incompletos y escritura mediante el adaptador con respuestas simuladas.

Se ejecutó además `PalomaresDelRioAyuntamientoAdapter('palomares-del-rio').backfill_proyectos(Path('evidence/proyectos.jsonl'))` contra ambos sitios reales, sin bases de datos ni publicación. Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/document_checks.json`, capturas HTML de las fuentes y PDFs/textos seleccionados. La comprobación de enlaces lee el principio de cada PDF para verificar HTTP y firma; no equivale a una revisión textual íntegra de todos los documentos.

Manifest: `licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`. Cada registro declara `publication_ready=false` y `geometry_status=unavailable`.
