# Yuncler — INE 45203, Toledo

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

La [página municipal de Urbanismo](https://www.aytoyuncler.com/luis-miguel/)
contiene un acordeón URBANISMO que identifica el Plan General de Ordenación
Municipal y un grupo «Plan de ordenación». El [contacto municipal](https://www.aytoyuncler.com/page-templates-2/contact-us/)
identifica este dominio como página oficial del Ayuntamiento de Yuncler.
La [ficha del directorio estatal](https://administracion.gob.es/espanaadmon/quienesquien/ficha-unidad-organica?selectorServicio=organigramasEstructurasDirectorios&selectorget=L01452034)
identifica Ayuntamiento de Yuncler, Toledo, y código de entidad L01452034.

El grupo documental municipal es la fuente implementada: **un instrumento POM,
cinco enlaces documentales**. Se recorren todos los enlaces entre su encabezado y
el encabezado siguiente, Ordenanzas; las normas y fichas no son proyectos
independientes. Se conservan etiquetas, URL literales y página de procedencia.
El identificador corresponde al instrumento, no al número de documentos. No se
inventan expedientes administrativos. La sección está completa en una página,
sin paginación observada. Si aparecen controles de continuación en Urbanismo se
produce un error explícito, sin devolver silenciosamente solo la primera página.

También se investigó la [sede electrónica](https://yuncler.sedelectronica.es/info.0):
ofrece trámites de solicitud de licencia, transparencia y tablón con anuncios
heterogéneos. No constituye evidencia de licencias concedidas. Los anuncios de
contratación, formularios, ordenanzas y noticias no se convierten en proyectos.
La cobertura no pretende ser un inventario de todos los expedientes municipales:
no incorpora los PAU de URI-11/URR-24 ni modificaciones posteriores publicadas
en boletines. La mera existencia de los documentos del POM no acredita su
vigencia ni que sea la versión consolidada más reciente.

## Documentos y disponibilidad comprobada

Las URL del inventario usan HTTP; se retienen literalmente en la extracción.
La comprobación de disponibilidad se hizo sobre el mismo host y ruta mediante
HTTPS. Los resultados y URL finales están en `evidence/document_checks.json`.

| Etiqueta municipal | Ruta final del documento | Comprobación HTTPS |
| --- | --- | --- |
| Normas urbanísticas | DOCUMENTO-2-NORMAS-URBANISTICAS.pdf | HTTP 200, application/pdf, firma PDF |
| Fichas | DOCUMENTO-3-FICHAS.pdf | HTTP 200, application/pdf, firma PDF |
| General | Plano-GeneralCL-01.pd | HTTP 404; enlace publicado roto |
| Parcelas | Plano-parcelas-CL-03.pdf | HTTP 200, application/pdf, firma PDF |
| Casco Urbano | Plano-casco-urbano-CL-02.pdf | HTTP 200, application/pdf, firma PDF |

Todos cuelgan del directorio municipal `/wp-content/uploads/2020/05/`.
Se capturaron solamente los primeros 1024 bytes de cada respuesta documental,
sin analizar exhaustivamente el contenido ni geometrías de los PDF. El enlace
General se conserva terminado en `.pd`, sin corregirlo mediante conjeturas.
El adapter lee el inventario actual en cada ejecución; estas comprobaciones de
disponibilidad documentan esta ejecución, no una garantía permanente.

## Semántica y límites

No hay fechas acreditadas de publicación, acuerdo o aprobación en el grupo:
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulas. El directorio de
carga de WordPress no se utiliza como fecha de aprobación. No se infiere fase,
ejecución, concesión de licencia, coordenadas ni geometría. Cada registro declara
`publication_ready: false` y `geometry_status: unavailable`. Licencias,
programación y jitter quedan desactivados en el manifest. La actualización
relee la instantánea completa; no simula un incremental fechado.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_yuncler -v`, cinco pruebas correctas.
Cubren agrupación y deduplicación, aislamiento frente a ordenanzas/formularios,
conservación del enlace roto, ausencia de metadatos inventados, rechazo de fuentes
vacías/ambiguas/cambiadas o paginadas, actualización y configuración del manifest.

Extracción real mediante `load_manifest('yuncler')`, `load_portal_adapter(...)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro real con
5 documentos**. La política compartida lo anota como identidad desconocida
(`unknown: 1`); no se fuerza su clasificación como actuación ejecutada. No se
ejecutó publicación, geocodificación ni acceso a bases de datos.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, captura HTML `evidence/luis-miguel.html`,
`evidence/document_checks.json` y prefijos de respuestas documentales.
