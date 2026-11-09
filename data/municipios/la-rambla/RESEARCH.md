# La Rambla — Córdoba — INE 14057

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes descubiertas y alcance elegido

El sitio oficial [Ayuntamiento de La Rambla](https://larambla.es/) enlaza en su navegación a [Documentos](https://larambla.es/ayuntamiento/documentos/), el inventario utilizado por el adaptador. La página mezcla formularios, fiscalidad, actas, urbanismo y otros documentos. Se extraen exclusivamente instrumentos identificados en «Instancias y normas subsidiarias» y el paquete PGOU formado por «Planos de Información», «Planos de Ordenación» y «Documentación PGOU». Las cuatro secciones se sirven completas en el HTML, dentro de desplegables Divi; no se observó paginación. El parser falla si aparece paginación, falta una sección, cambia su estructura o una sección queda sin documentos compatibles. No hay límites de registros ni cortes de páginas silenciosos.

Se consultó también el [portal municipal de transparencia](https://transparencia.larambla.es/), enlazado por la portada. No se incorporan sus categorías genéricas como proyectos. Se localizó el [portal del PBOM](https://larambla.lab360.es/), que muestra «Diagnóstico Previo», expediente 1225U09 y material de participación; no se integra en esta implementación ni se confunde con el paquete PGOU antiguo del inventario. La atribución de ese portal separado apareció en una noticia de prensa, sin verificar en esta revisión un enlace desde el Ayuntamiento. El inventario municipal incluye además un plan climático de 2026, que queda fuera del alcance urbanístico seleccionado. Una respuesta inicial a la portada sin User-Agent fue HTTP 403; la portada y el inventario respondieron HTTP 200 con User-Agent de navegador, también durante la ejecución del adaptador.

## Resultado vivo y agrupación

Ocho instrumentos con **58 documentos** enlazados:

| Instrumento, según el inventario | Documentos |
| --- | ---: |
| Modificaciones en el PGOU «Carrera Baja» | 1 |
| Plan Parcial Sector PP-2A «La Redonda – A» | 1 |
| ADAPTACIÓN DE LAS NORMAS SUBSIDIARIAS A LA LOUA | 7 |
| Aprobación definitiva modificación NN.SS. en calle Guevara, Valenzuela y Las Flores | 1 |
| NN.SS. La Rambla | 1 |
| MODIFICACIÓN ESTUDIO DE DETALLE UE-7 | 2 |
| Admisión a trámite Proyecto de Actuación Olivos Lorente | 3 |
| PGOU | 42 |

Los siete documentos de adaptación se agrupan por el nombre del instrumento anterior al separador del título. Los títulos repetidos de UE-7 y Olivos Lorente identifican un solo instrumento cada uno: se retienen todos sus enlaces distintos, incluidos anuncios, certificado y documento técnico. Los 21 planos de información, 17 de ordenación y cuatro documentos generales del PGOU constituyen un único registro. Los IDs se derivan del nombre normalizado del instrumento, sin depender del orden del inventario. Cada documento conserva título literal normalizando espacios, URL, sección e inventario de procedencia; cada registro enlaza a su primer documento y al inventario.

No se emiten solicitudes, bonificaciones, ordenanzas fiscales, actas generales, anuncios de contratación ni noticias. Tampoco se crea un proyecto a partir de «Plano Urbanístico (Avance)», cuya atribución concreta no está identificada en el listado, o del bloque genérico «Parcelario y planos». No se añade la copia de normas subsidiarias situada en «Ordenanzas no fiscales»: esta extracción está delimitada a las cuatro secciones indicadas.

## Semántica y limitaciones

Es cobertura parcial del inventario documental que el municipio publica actualmente, con documentos históricos. No equivale a catálogo exhaustivo de planeamiento, registro de licencias concedidas o inventario de obras en ejecución. La admisión a trámite de Olivos Lorente no se interpreta como aprobación o licencia. Los rótulos de aprobación del inventario se conservan en sus títulos; no se atribuyen fechas de acuerdo, publicación o aprobación. Ni los directorios de subida ni las fechas de actualización del CMS permiten fijarlas. No se analiza íntegramente el contenido de los PDF ni se certifica vigencia jurídica.

Sin coordenadas, geocodificación aleatoria o fase inferida. Los registros declaran `publication_ready: false`, `geometry_status: unavailable` y cobertura parcial. El manifest identifica Córdoba e INE 14057, desactiva `schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled`. El método de licencias produce salida vacía explícitamente desactivada. La actualización vuelve a leer todo el inventario; no pretende reconstruir bajas o un histórico incremental.

## Verificación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_la_rambla -v`: cinco pruebas correctas. Comprueban agrupación y aislamiento documental, exclusión de formularios, extracción dinámica y deduplicación, ausencia de fechas/coordenadas inferidas, rechazo de cambios estructurales/paginación/enlaces externos, conservación de la salida ante errores y resolución del manifest mediante el registro compartido.

Se ejecutó realmente `load_portal_adapter(load_manifest('la-rambla')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `adapter.config['evidence_dir'] = 'evidence'`. Resultado: ocho registros, 58 documentos y anotación de entidades compartida correcta. Se verificó además por GET parcial el primer documento de cada uno de los ocho instrumentos: todos HTTP 200 y firma `%PDF-`. Se conservaron solo los primeros 1024 bytes de cada PDF; no se afirma haber comprobado los otros 50 enlaces ni leído íntegramente esos ocho documentos.

Evidencias locales, no destinadas al commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (conteo vivo, fuentes, limitaciones, pruebas, hash de captura y comprobaciones PDF), `evidence/inventory.html`, `evidence/document_checks.json`, prefijos PDF y capturas auxiliares de descubrimiento. No se usa base de datos, despliegue, publicación ni geocodificación.
