# La Guardia de Jaén — INE 23038, provincia de Jaén

Investigación y extracción real: 9 de noviembre de 2026.

## Fuente oficial y alcance

Inventario del Portal de Transparencia del Ayuntamiento:
[Planeamiento de Ordenación Urbana](https://laguardiadejaen.com/portal-transparencia/planeamiento-de-ordenacion-urbana/).
La página identifica expresamente el término municipal de La Guardia de Jaén.
Se consultó el HTML actual mediante HTTPS, no una lista de expedientes precargada.
El contenido se sirve completo en seis pestañas Divi; no se observó paginación ni
carga diferida. El adaptador recorre todas las pestañas y todos sus bloques de
ámbito; rechaza paginación reconocible, categorías desconocidas, inventarios
vacíos, metadatos no reconocidos e instrumentos sin documentos.

Resultado: **16 instrumentos, 192 enlaces PDF con título**, agrupados así:

| Categoría municipal | Instrumentos |
| --- | --- |
| Revisión de Normas Subsidiarias | Término Municipal |
| Adaptación parcial de NN.SS. a LOUA | Término municipal |
| Modificaciones de NN.SS. | Trascastillo y Azadores; El Arrabal; U.A. Nº 1; La Manseguilla; suelo industrial Los Cascajales; Guadualla |
| Planes parciales | El Arrabal, Ciudad Jardín-Entrecaminos; Los Cascajales B; Jardines de la Yuca; Ciudad Jardín-Entrecaminos FASE V; SAUR-1 El Fontanar |
| Modificaciones de planes parciales | Reordenación Jardines de la Yuca; Los Cascajales B |
| Estudio de detalle | Azadores |

Cada registro agrupa memoria, normativa, anexos, boletines y planos asociados
al mismo bloque de ámbito dentro de su categoría. La revisión, las modificaciones
y los planes originales son instrumentos separados, aunque compartan ámbito.
La URL del inventario, categoría, ámbito y metadatos literales permiten localizar
el bloque; cada documento conserva título, URL de descarga y página de procedencia.
La identidad deriva de categoría y ámbito, sin depender del orden de documentos.

No se incluyen solicitudes de licencia, anuncios de contratación, noticias o
documentos aislados como proyectos adicionales. Se excluyen iconos PNG y anclas
PDF sin texto: el HTML repite enlaces vacíos a `BOP-2013-8715.pdf` junto a muchos
planos, sin atribución documental fiable. Los enlaces titulados se conservan y
deduplican por URL dentro de cada instrumento.

## Fechas y limitaciones

`fecha_aprob` y `fecha_publicacion` proceden exclusivamente de los rótulos
«Fecha de aprobación» y «Fecha de publicación» del bloque correspondiente. No
se deduce `fecha_acuerdo`, fase ni fecha genérica, ni se toma la fecha del CMS o
del directorio de subida como fecha administrativa. Los literales originales se
retienen en campos terminados en `_fuente` y en `metadata_fuente`.

* SAUR-1 El Fontanar indica aprobación **21/13/2008**: se conserva el literal y
  un aviso, omitiendo la fecha normalizada imposible.
* El Arrabal, Ciudad Jardín-Entrecaminos indica aprobación **30/12/1998** y
  publicación **03/04/1998**: se conservan ambas fechas con aviso de inconsistencia.
* Las publicaciones indicadas con guion no se completan artificialmente.

El propio Ayuntamiento advierte que la documentación es meramente informativa
y que debe contrastarse su vigencia con la Administración competente. Por eso
todos los registros llevan `vigencia_verificada: false`, `publication_ready: false`
y `geometry_status: unavailable`. No se extraen coordenadas de los planos ni se
inventan ubicaciones. El catálogo no garantiza la totalidad del histórico ni
ofrece evidencia de ejecución de obras físicas. No se ha verificado un registro
público de licencias concedidas: `licencias.enabled: false`. También están
desactivadas la programación y la generación de coordenadas por jitter.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_guardia_de_jaen -v` — **7 correctas**.
Cubren separación de documentos entre instrumentos, deduplicación, fechas
explícitas e inválidas, inconsistencias, identidad estable, rechazo de vacíos,
paginación y formularios sin documentación, actualización y licencias desactivadas.

Se ejecutó realmente `LaGuardiaDeJaenAyuntamientoAdapter.backfill_proyectos`
con `config={"capture_dir": "evidence"}` y salida `evidence/proyectos.jsonl`:
**16 registros y 192 enlaces**. No intervienen bases de datos ni publicación.

`evidence/inventory.html` contiene la respuesta del inventario utilizada por el
adaptador. `evidence/validation.json` recoge recuento, URL, limitaciones y las
comprobaciones documentales. Se muestreó el primer PDF de cada uno de los 16
instrumentos: **16 HTTP 200, application/pdf y firma %PDF-**. Se guardaron los
primeros 1024 bytes de cada muestra como `document-01.prefix` a
`document-16.prefix`; no son archivos PDF completos. No se validaron los otros
176 enlaces ni el contenido íntegro de los documentos. La evidencia permanece
local, fuera de los cuatro archivos fuente entregados.
