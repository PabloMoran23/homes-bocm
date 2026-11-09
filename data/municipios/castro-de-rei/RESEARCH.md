# Castro de Rei — Lugo — INE 27010

Verificación y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial e inventario descubierto

La navegación municipal «Urbanismo → PXOM» lleva a
https://www.castroderei.gal/es/pxom/ . La página identifica expresamente el
«PLAN GENERAL DE ORDENACIÓN MUNICIPAL DE CASTRO DE REI» como «Documento
aprobado definitivo» y embebe el inventario:
https://www.castroderei.gal/archivos/file_manager.php . Ambos devolvieron HTTP 200.
No se usa una noticia ni un documento aislado como inventario.

El gestor contiene una carpeta de instrumento, `CASTRO_DE_REI_PXOM_APROBADO
DEFINITIVO`, con tres tomos. El adapter descubre y recorre todos los enlaces de
subcarpetas y conserva los documentos agrupados en **un único PXOM**:

- TOMO I-LITERATURA: 32 documentos.
- TOMO II- PLANOS: 7 documentos.
- TOMO III-PLANOS: 8 documentos.

Resultado vivo: **1 instrumento, 47 enlaces documentales únicos**. Incluyen
memoria, normativa, ordenanzas, estudios, catálogos y planos. Cada documento
conserva título, enlace original `url_fuente`, URL HTTPS normalizada e
`inventario_url` que lo publicó. No son 47 proyectos independientes.
Se verificaron mediante GET dos portadas/índices PDF (HTTP 200, cabecera PDF);
se conserva una muestra en `evidence/pxom-portada-indice.pdf`. No se descargaron
ni auditaron todos los PDFs.

No se observó paginación: son listados de directorios con recuentos explícitos.
Se contrastan en cada página las cantidades anunciadas de carpetas y archivos
contra los enlaces extraídos. Se falla ante recuentos inconsistentes, enlaces
no reconocidos (incluida paginación), ciclos, cambios de instrumento, ausencia de
documentos y límite de recorrido; nunca se entrega un resultado truncado.
Los límites son errores explícitos y no topes de registros aceptados.

## Semántica y límites

La fase procede del texto municipal «Documento aprobado definitivo».
El inventario no publica fechas de acuerdo, aprobación ni publicación del
instrumento: `fecha_acuerdo`, `fecha_aprob` y `fecha_publicacion` quedan null.
No se toman fechas del nombre de los archivos, del copyright, de la respuesta
HTTP ni de la página WordPress como fechas de aprobación.

Como contraste documental, el BOP de Lugo del 15 de diciembre de 2020
https://www.deputacionlugo.gal/sites/deputacionlugo.org/files/inline-files/15-12-2020.pdf
anuncia la normativa y cita la aprobación por orden de 10 de julio de 2020 y su
publicación en DOG de 24 de julio. Son hitos distintos; este adapter **no procesa
ese BOP ni incorpora sus fechas**. El registro refleja únicamente lo extraído del
archivo municipal actual.

Cobertura parcial: exclusivamente el PXOM alojado en este archivo; no pretende
cubrir modificaciones posteriores en otras fuentes, todos los instrumentos,
obras públicas o un histórico del tablón. La sede municipal enlaza
https://castroderei.sedelectronica.gal/board y el perfil de contratación; no se
extraen sus anuncios como proyectos ni como concesiones. Los listados de
contratación/servicios que aparecen en la página municipal de sede tampoco
constituyen un registro de licencias concedidas. Licencias deshabilitadas.

## Geometría

`geometry_status: unavailable`. La web municipal enlaza
https://www.castroderei.gal/gis/ , cuyo visor presenta puntos de interés,
naturaleza, patrimonio, servicios y zonas. No se verificó una geometría vectorial
asociable al instrumento extraído. Los planos PDF se retienen como documentos,
sin vectorizarlos ni inventar coordenadas. `lat`, `lon` y `geometry` quedan null;
`publication_ready` es false y `geocode.jitter_missing` es false.

## Validación reproducible

`python -m unittest municipio.test_castro_de_rei -v`: cuatro pruebas pasan,
con fixtures sintéticos que comprueban agrupación recursiva y deduplicación,
proveniencia, fechas desconocidas, cambios de fuente, paginación o recuentos
incompletos, ciclos, inventario vacío, carga por registry y licencias vacías.
Los fixtures no se usan como datos reales.

Extracción real mediante `load_manifest('castro-de-rei')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json` y
`evidence/captures/*.html`. El wrapper del registry aplica además la política de
entidades existente; no se modifica ninguna fuente compartida.
`schedule.enabled: false`. Sin publicación, DB ni despliegue.
