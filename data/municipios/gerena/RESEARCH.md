# Gerena — INE 41045, Sevilla

Investigación y extracción real: 8 de noviembre de 2026. Python preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`. Sin dependencias nuevas, base de datos, geocodificación ni publicación.

## Descubrimiento de fuentes oficiales

- [Instrumentos de planeamiento](https://www.gerena.es/es/ayuntamiento/normativa-municipal/instrumentos-de-planeamiento/): página municipal que remite expresamente al indicador 53 del Portal de Transparencia. El enlace original usa HTTP; se verificó directamente su equivalente HTTPS.
- [Inventario ITA 53](https://transparencia.gerena.es/es/transparencia/indicadores-de-transparencia/indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00033/): fuente implementada. Contiene instrumentos concretos y documentos asociados, no una lista de noticias o formularios. Incluye un estudio publicado en el portal en febrero de 2026, además de documentación histórica.
- [Anuncios del Área de Urbanismo](https://www.gerena.es/es/ayuntamiento/anuncios/urbanismo/): dos estudios de detalle (Las Lumbreras y dotaciones del sector 1), con anuncios de aprobación inicial. No se ingieren como nuevas actuaciones: el inventario de transparencia ya recoge documentación de esos ámbitos, incluida documentación posterior. Un anuncio inicial no acredita aprobación definitiva.
- [Tramitación del nuevo PGOM](https://www.gerena.es/es/ayuntamiento/normativa-municipal/tramitacion-del-nuevo-pgom/) y [POU](https://www.gerena.es/es/ayuntamiento/normativa-municipal/pou/): páginas oficiales adicionales con fases/documentación y enlaces. Investigadas y capturadas, fuera del alcance del adaptador. No se afirma cobertura completa del planeamiento municipal.

No se ha verificado un inventario público de concesiones de licencias: `licencias.enabled: false`. Los modelos de solicitud y los anuncios de contratación no se utilizan como registros.

## Unidad documental, paginación y procedencia

Se recorren `section.gallery` con `h4.gallery-title`, reteniendo los enlaces a recursos de `.galleries/IND-53-/` dentro de cada sección. Se conservan PDF, TIFF, XLS y fotografías documentales. Las carpetas contienen planos, memorias, publicaciones, certificados y antecedentes; cada enlace conserva título y `source_url` de la página donde se encontró. No se convierte cada documento en una actuación distinta.

Se agrupan por título de galería y se eliminan enlaces duplicados. La galería «ED Equipamiento SUO1» contiene además otro estudio bajo `ESTUDIO-DE-DETALLE.-2020.-COLEGIO/`: se separa en un segundo registro con sus 38 documentos, frente a los 3 del grupo anterior. Los documentos de apoyo se conservan como tales; por ejemplo, un informe denominado «CONSEJO CONSULTIVO - Bollullos» dentro de esa carpeta no se transforma en una actuación de Gerena. El título genérico del grupo de 2026 se precisa con la descripción explícita de su documento (manzana M-3-13-1).

El portal OpenCMS pagina **cada galería independientemente** mediante `pagegalleryfiles-N-1`. Se siguen todos los enlaces de paginación observados, incluyendo los que se descubran en páginas posteriores. Al descargar una página adicional solo se incorporan los documentos de la galería solicitada: las otras galerías vuelven a mostrar su primera página. Se comprueba el marcador de página activa y se rechazan respuestas repetidas o galerías vacías/desaparecidas. El límite defensivo de 500 páginas por galería provoca error, nunca una salida parcial silenciosa. La salida se escribe solo después de completar la extracción.

Extracción observada: **30 registros, 234 enlaces únicos**, procedentes de 29 galerías y **12 páginas HTTP**: base y 11 páginas adicionales. Galerías con páginas extra: Adaptación Parcial (2 páginas), Modificación 2 SUO1 (2), PE Recinto Ferial (2), 2 MOD PE Las Cruces (2), Equipamiento SUO1 (5) y Lumbreras (4).

El identificador estable deriva del título del grupo municipal, no del orden ni de parámetros de página. `url` apunta a un documento concreto, `inventory_url` al inventario común. Un cambio de título en origen puede cambiar el identificador. Las modificaciones de un plan son instrumentos diferenciados; planos y anuncios del mismo instrumento permanecen juntos. El incremental refresca el inventario completo porque no existe un cursor fiable.

## Semántica y limitaciones

`tipo: planeamiento_urbanistico`, sin inferir `fase`, vigencia, ejecución material o concesión de licencia. Las menciones de aprobación incluidas en títulos originales se conservan como texto de origen. No se deducen fechas de nombres de archivo. Los pocos sellos temporales visibles del CMS se guardan a nivel documental en `fecha_publicacion_portal`; no son fechas del acuerdo ni necesariamente de publicación en BOP. No se emiten `fecha_aprob`, `fecha_acuerdo` ni una fecha genérica.

Sin coordenadas, geometría ni ubicaciones ficticias: `geometry_status: unavailable`, `publication_ready: false`, `geocode.jitter_missing: false`, `schedule.enabled: false`. La fuente es un inventario documental municipal parcial: no equivale a todos los proyectos, obras públicas, expedientes, ni a un registro legal exhaustivo. No se descargó ni interpretó el contenido de los 234 documentos; la disponibilidad de todos los enlaces tampoco se verifica exhaustivamente.

## Validación y evidencia local

Pruebas offline: `python -m unittest municipio.test_gerena -v` — **8 pruebas correctas**. Comprueban agrupación y aislamiento entre galerías, paginación completa, respuestas que ignoran la página, páginas repetidas, desaparición del inventario, enlaces externos, separación del estudio del colegio, retención de TIFF, semántica de fechas, carga del manifest, refresco y licencias desactivadas.

Extracción real mediante `GerenaAyuntamientoAdapter('gerena', config={'capture_dir': 'evidence/captures'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`. `evidence/validation.json` contiene `live_records: 30`, los 12 `source_urls`, limitaciones, runtime, pruebas y comprobación documental. `evidence/captures/` conserva las respuestas HTML del adaptador (nombre SHA-256 abreviado de la URL). `evidence/*.html` contiene las páginas adicionales de investigación.

Se descargó íntegramente una muestra: `22-PUD-001-25-publ-aprob-def-BOP.pdf`, HTTP 200, `application/pdf`, firma `%PDF-`, 319298 bytes. Copia en `evidence/sample-bop-vpo.pdf`, texto extraído en `evidence/sample-bop-vpo.txt`, URL y SHA-256 en validation. La muestra corresponde al anuncio del estudio de reasignación de viviendas VPO. Su texto distingue el acuerdo plenario de 26 de enero de 2023 y el BOP n.º 45 de 24 de febrero de 2023; estos datos de la comprobación puntual no se incorporan automáticamente a los registros del scraper HTML; no se extrapola su contenido al resto del inventario. Toda la evidencia es local y queda fuera de los cuatro archivos fuente.
