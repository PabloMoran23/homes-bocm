# La Unión (Murcia), INE 30041

Investigación: 7 de noviembre de 2026. Cobertura implementada: comunicados oficiales sobre obras públicas concretas. No equivale a registro de expedientes urbanísticos ni a autorizaciones o licencias.

## Fuentes y límites

- Web municipal oficial: https://www.ayto-launion.org/ . La portada publica enlaces a noticias fechadas; WordPress expone REST en el mismo dominio.
- Consulta pública reproducible: https://www.ayto-launion.org/wp-json/wp/v2/posts?search=obras&per_page=100&page=1&orderby=date&order=desc . Paginación mediante `X-WP-TotalPages`. El adaptador consulta hasta cinco páginas por ejecución, con 0,5 s entre páginas; falla explícitamente si el límite impide terminar el historial.
- Urbanismo: https://www.ayto-launion.org/servicios/urbanismo/ . La respuesta HTML 200 muestra shortcodes WPFilebase sin renderizar; no ofrece ahora documentos de planeamiento consumibles. No se convierte esta página genérica en proyecto.
- Sede: https://launion.sedelectronica.es/ . No se ha verificado un registro público de licencias concedidas; `licencias.enabled: false`.
- Se investigó el subdominio `prueba.ayto-launion.org`: su biblioteca devuelve PDFs de planes parciales, pero no se encontró enlace de delegación desde portada o Urbanismo de la web oficial. Se excluye completamente del adaptador y de los registros aceptables. Las rutas equivalentes del dominio principal devuelven 404 o categorías vacías.

## Ejemplos oficiales verificados

- Obra de mejora de la Asociación de Amas de Casa: https://www.ayto-launion.org/2026/10/14/el-ayuntamiento-de-la-union-finaliza-las-obras-de-mejora-en-la-asociacion-de-amas-de-casa-gracias-al-programa-experiencial-la-union-avanza-en-formacion-y-empleo/ (`posts/28099`).
- Reforma integral de la Biblioteca Municipal: https://www.ayto-launion.org/2026/09/10/el-ayuntamiento-de-la-union-culmina-la-reforma-integral-de-la-biblioteca-municipal/ (`posts/27871`).
- Licitación de actuaciones de seguridad vial en calle Murcia y calle Real: https://www.ayto-launion.org/2026/06/23/el-ayuntamiento-de-la-union-licita-cerca-de-un-millon-de-euros-para-transformar-la-seguridad-vial-de-calle-murcia-y-calle-real/ (`posts/27439`). Es una noticia sobre una licitación de obra pública, no una licencia urbanística concedida.

El identificador de registro deriva del ID oficial de noticia; cada registro representa un comunicado. Diferentes noticias pueden referirse a la misma obra y no se presentan como expedientes independientes. El título debe identificar una intervención física y un activo concreto; se descartan exposiciones artísticas, formularios, reclamaciones y páginas genéricas. La consulta textual `obras` y el filtro conservador limitan la cobertura: no garantizan recoger todas las actuaciones del municipio.

## Semántica y publicación

`fecha_publicacion` procede exclusivamente del campo WordPress `date`; no se interpreta como fecha de aprobación, adjudicación o licencia. El scraper no infiere fases. No hay coordenadas, polígonos, centroides ni jitter. Cada registro indica `origen: comunicado_municipal`, `geometry_status: unavailable` y `publication_ready: false`. El manifest incluye `schedule.enabled: false` y `geocode.jitter_missing: false`.

Las llamadas usan un User-Agent de navegador compatible porque la petición urllib por defecto recibió HTTP 403; no requieren autenticación. Los errores de red se propagan; cero resultados genera error explícito para revisión. No se ejecuta ingestión, geocodificación o publicación.

## Comprobaciones

`python3 -m unittest municipio.adapters.test_la_union -v`: cuatro pruebas pasan; verifican exclusión de ruido/formularios/staging, fechas ausentes, semántica, paginación, deduplicación y error al no extraer registros.

`python3 -m py_compile municipio/adapters/la_union.py municipio/adapters/test_la_union.py`: correcto.

La ejecución real usa directamente `LaUnionAyuntamientoAdapter.backfill_proyectos` y guarda JSONL y métricas fuera del repositorio, en el directorio de evidencias del orquestador. No carga credenciales ni realiza operaciones de base de datos.

Ejecución real: cuatro páginas, historial de consulta completo (`truncated: false`), 32 comunicados retenidos tras excluir la petición de obra ID 12697 en revisión manual. Evidencias: `artifacts/municipio-local-batches-20261107/la-union/proyectos.jsonl` y `validation.json`, fuera del repositorio.
