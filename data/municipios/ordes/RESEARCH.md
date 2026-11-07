# Ordes — INE 15059, A Coruña, Galicia

Verificado el 2026-11-07 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

El portal municipal mantiene el menú **PLANEAMENTO URBANISTICO** en
https://concello.ordes.gal/p/pxom . El cuerpo central de esta URL está vacío:
el inventario útil está en el menú, que enlaza el PXOM vigente, las NNSS de 1996
(derogadas), la documentación de tramitación del PXOM y convenios urbanísticos.
El adaptador descubre los dos enlaces del PXOM desde este menú; no utiliza una
noticia ni una licitación como semilla de proyectos. Las NNSS derogadas y los
convenios quedan fuera del alcance declarado.

- Inventario vigente: https://concello.ordes.gal/p/pxom-ad-en-vigor-16-04-2024-
- Tramitación: https://concello.ordes.gal/p/doc-tramitacion-pxom
- Publicación oficial enlazada y contrastada (HTTP 200):
  https://www.xunta.gal/dog/Publicados/2023/20231226/AnuncioG0691-181223-0002_gl.html
- Inventario SIOTUGA enlazado por el Concello (HTTP 200):
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15059

Las tres páginas municipales respondieron HTTP 200. Las páginas de documentos
son listas estáticas, sin paginación observada. Se leen todos sus enlaces de
contenido; la aparición de paginación provoca un error explícito. No se impone
un límite que trunque registros o documentos. El método update vuelve a extraer
esta instantánea completa; no promete un histórico incremental de borrados.

## Entidad y fechas

Resultado vivo: **1 instrumento real**, el Plan xeral de ordenación municipal de
Ordes (PXOM), con **13 referencias agrupadas**: siete documentos de aprobación,
registro, normativa y correcciones; dos enlaces a SIOTUGA/registro autonómico;
y cuatro carpetas municipales de tramitación alojadas en Google Drive. Ninguno
de estos documentos se convierte en un proyecto adicional. Se preservan los
URLs completos, etiquetas y página municipal de procedencia de cada enlace.
Las carpetas se retienen como referencias, sin autenticación ni enumeración de
su contenido. Los PDFs se enlazan, pero no se afirma haber descargado o validado
cada uno. Los enlaces de registro son puntos de acceso, no IDs de expediente.

Se extraen fechas explícitas de las etiquetas municipales:

- `fecha_aprob` y `fecha_acuerdo`: 2023-12-13, orden de aprobación definitiva.
- `fecha_publicacion`: 2023-12-26, publicación del anuncio en el DOG 243.
- `fecha_entrada_vigor`: 2024-04-16, según el título de la página municipal.

La resolución que hace pública la aprobación es del 15 de diciembre: **no** es
la fecha de aprobación del plan. El texto del DOG contrastado confirma la orden
del 13 de diciembre. Las publicaciones de normativa en BOP de 19/02/2024 y
22/03/2024 permanecen en las etiquetas de sus documentos y no sustituyen la
fecha del DOG. No se conoce la fecha de publicación de la página web municipal.
`fecha` queda nula para evitar una fecha genérica ambigua. Las fechas de acuerdos
inicial/provisionales se guardan solamente en sus referencias de tramitación;
no cambian la fase de aprobación definitiva del instrumento agrupado.

## Cobertura parcial y geometría

Esta extracción cubre el PXOM que el portal identifica como vigente y su
tramitación enlazada. No es un censo completo de modificaciones, planeamiento
de desarrollo, convenios, reparcelaciones ni obras públicas. Tampoco se extraen
como proyectos los antecedentes de otros instrumentos mencionados en el DOG.
No se ha verificado un registro de licencias concedidas: formularios, solicitudes,
noticias y anuncios de contratación no se convierten en licencias o proyectos.
`licencias.enabled` y los métodos correspondientes quedan deshabilitados/vacíos.

`geometry_status: unavailable`. SIOTUGA devuelve una interfaz de inventario con
selector municipal; la captura no expone geometría del instrumento. No se ha
verificado una capa vectorial enlazada por expediente ni recorrido el visor o
el registro autonómico. No se digitalizan planos PDF. Latitud, longitud y
geometría permanecen nulas; `publication_ready: false`.

## Implementación y comprobación

Solo se añaden el manifest, este documento, el adaptador y sus pruebas.
El manifest identifica Ordes, A Coruña, Galicia, INE 15059, con
`schedule.enabled: false` y `geocode.jitter_missing: false`.

Pruebas sin red: `python -m unittest municipio.test_ordes -v`: **7 pasan**.
Cubren descubrimiento/deduplicación, documentos agrupados, separación de fechas,
procedencia, rechazo de formularios/páginas incompletas, paginación inesperada,
conservación del fichero previo ante fallo y contrato del manifest/licencias.

Extracción real ejecutada mediante `load_manifest('ordes')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, con captura local habilitada
mediante `adapter.config['capture_dir'] = 'evidence'`. Produjo 1 registro y
13 referencias. El anotador compartido se ejecutó: estado ok, categoría unknown
(1/1); no se modifica su política ni se fuerza una categoría.

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: registro real extraído.
- `evidence/validation.json`: recuento vivo, URLs fuente, limitaciones y pruebas.
- `evidence/pxom.html`, `evidence/pxom-ad-en-vigor-16-04-2024-.html`,
  `evidence/doc-tramitacion-pxom.html`: respuestas de la ejecución del adaptador.
- `evidence/dog.html` y `evidence/siotuga.html`: comprobaciones complementarias.

No se han usado credenciales, bases de datos ni herramientas de publicación.
