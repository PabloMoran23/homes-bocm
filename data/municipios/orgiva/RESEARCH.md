# Órgiva (Granada), INE 18147

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.orgiva:OrgivaAyuntamientoAdapter`.

## Fuentes oficiales descubiertas

- [Web municipal](https://www.ayuntamientodeorgiva.es/): enlaza la sede electrónica y el portal de transparencia.
- [Inventario de urbanismo](https://orgiva.sedelectronica.es/transparency/980c434f-f3bc-4aac-8fb1-19aefaa6111d/): contiene planeamiento, normativa, obras públicas, medio ambiente y convenios. No se trata como un registro de licencias concedidas.
- [Planeamiento urbanístico, fuente de extracción](https://orgiva.sedelectronica.es/transparency/dfa36414-bbe5-4574-a2c1-ce698b725e59/): inventario de documentos y carpetas del Ayuntamiento. Selección deliberadamente parcial: instrumentos de planeamiento general identificados como PBOM y Plan de Delimitación de Suelo Urbano. Otros estudios de detalle, certificados, órdenes de ejecución y proyectos de urbanización quedan fuera de esta implementación. No se convierten certificados ambiguos en proyectos adicionales.
- [Noticia municipal del avance, 24/05/2024](https://www.ayuntamientodeorgiva.es/2024/05/24/avance-del-plan-basico-de-ordenacion-municipal-pbom/): enlaza directamente la carpeta oficial del PBOM. Se utilizó para descubrir y contrastar la procedencia; su fecha es de publicación de la noticia, no de aprobación del instrumento, y no se incorpora como fecha del registro.
- [Categoría municipal de noticias de urbanismo](https://www.ayuntamientodeorgiva.es/category/urbanismo/): tres páginas observadas, con obras y también información ajena a proyectos. No forma parte de la extracción y no se declara cobertura de su archivo.

## Resultado y agrupación documental

La ejecución real produjo **2 instrumentos y 37 enlaces documentales**:

1. [PBOM](https://orgiva.sedelectronica.es/transparency/23dafdfb-eb8b-4e38-be07-442229eaa839/): un registro que conserva los **36 documentos** del árbol completo. Incluye consulta previa (2), avance (34), informe y decreto, memoria de información y diagnóstico, memoria de ordenación, participación, resumen ejecutivo y planos. Los planos de información son 20, aunque la primera respuesta solo enseña 10; los planos de ordenación son 8. Las piezas de consulta previa y avance se agrupan bajo el mismo instrumento, sin crear un proyecto por plano o por versión documental.
2. [Plan de Delimitación de Suelo Urbano Órgiva](https://orgiva.sedelectronica.es/preview-document/99fcd51d-2316-41b4-b9f3-b712512b3153): un registro con el documento publicado en el inventario. Su enlace identifica el documento, no una página genérica.

Cada documento conserva título, enlace estable al visor oficial, carpeta de procedencia y descripción del inventario cuando existe. Los identificadores de registros derivan de la URL estable del instrumento. No se fijan los enlaces Wicket cifrados temporales como identificadores o enlaces documentales.

La navegación de carpetas se resuelve con acciones públicas Wicket y su cabecera `Ajax-Location`, dentro de una sesión HTTP pública. La paginación `Mostrar más` se consume hasta desaparecer; una misma acción puede devolver páginas sucesivas. Se leen exclusivamente los fragmentos XML `component`, sin ejecutar JavaScript. Se controla el avance por entradas nuevas y se contrasta, en cada subcarpeta, el número de documentos únicos con el total anunciado por la sede. Límites de seguridad, respuestas inesperadas, ciclos, discrepancias de recuento o falta de instrumentos producen error antes de reemplazar la salida. No hay truncamiento silencioso.

## Semántica y límites

Esta es una fotografía del inventario público disponible, no un histórico exhaustivo, una declaración de vigencia o un listado de concesiones. La presencia de documentos de consulta y avance del PBOM no acredita aprobación definitiva. Tampoco se deduce una aprobación del Plan de Delimitación por su nombre.

Dos comprobaciones adicionales de visores oficiales respondieron HTTP 200 y mostraron los títulos esperados y formato PDF: anuncio de consulta pública previa del PBOM y Plan de Delimitación. Se guardaron las páginas de metadatos, sin descargar masivamente los PDF. Las fechas que el visor llama **Fecha de creación** (24/05/2024 y 19/09/2022 respectivamente) no se convierten en fechas de publicación, acuerdo o aprobación. No se analizó el contenido íntegro de los PDF y no se afirma que todos sus enlaces de descarga funcionen.

No se extraen formularios, anuncios de contratación, noticias ajenas, coordenadas ni fechas inferidas. `publication_ready=false` y `geometry_status=unavailable` en todos los registros. El manifest desactiva licencias, ejecución programada y jitter; invocar los métodos de licencias produce un error explícito. No se utilizan geocodificación, bases de datos ni publicación.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_orgiva -v`, **9 correctas**. Cubren agrupación de subcarpetas, procedencia, ausencia de fechas/coordenadas inferidas, estabilidad de identificadores, paginación con URL reutilizada, falta de progreso, recuentos incompletos, preservación de una salida anterior ante error, fuentes vacías, formato incorrecto, navegación externa y manifest.

Extracción ejecutada directamente con `OrgivaAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, usando `config={'capture_dir': 'evidence/live'}`. Resultado: **2 registros**, **36 + 1 documentos**, **24 peticiones** del adaptador. `update_proyectos` vuelve a leer el inventario completo; no se presume un mecanismo incremental por fecha que la fuente no ofrece.

Evidencia local, excluida del control de versiones: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/live/source-000.txt` a `source-023.txt` (HTML, respuestas XML de paginación y cuerpos de navegación), capturas de descubrimiento y `evidence/preview-0.html`, `evidence/preview-1.html`. El índice de `source_urls` en validation corresponde al número de captura. La validación incluye recuentos, URLs consultadas y limitaciones. Ninguna evidencia sustituye la lectura real de la fuente en futuras ejecuciones.
