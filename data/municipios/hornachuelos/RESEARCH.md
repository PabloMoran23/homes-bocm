# Hornachuelos — Córdoba — INE 14036

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

- Mapa municipal: https://hornachuelos.es/mapa-web-2/ . Enlaza Urbanismo, PGOU y el estudio de viabilidad Multiaventura/Albergue.
- Urbanismo: https://hornachuelos.es/ayuntamiento/urbanismo/ . Describe competencias y publica impresos, declaraciones responsables y carteles. No constituye un registro de licencias concedidas; se excluye de los registros.
- Inventario seleccionado: https://hornachuelos.es/ayuntamiento/urbanismo/pgou/ . Identifica expresamente el «PLAN GENERAL DE ORDENACIÓN URBANÍSTICA DEL TÉRMINO MUNICIPAL DE HORNACHUELOS (PGOU)» y contiene documentación sustantiva, no una noticia o convocatoria.
- Fuente descartada: https://hornachuelos.es/estudio-viabilidad-proyecto-parque-multiaventura-y-albergue/ . La página HTML responde 200 y enumera 18 enlaces, pero la memoria de viabilidad y cinco muestras de proyectos de actuación/proyectos básicos responden 404. No se incluye este conjunto en la extracción. Las comprobaciones están en `evidence/multiaventura-checks.json`; la memoria falló además durante la primera comprobación en vivo.

## Cobertura y semántica

Un registro real: el PGOU publicado, agrupando **71 documentos** (34 de información y 37 del PGOU: memorias, normativa, fichas, catálogo, estudio ambiental, resumen y planos). Cada documento conserva título literal, URL, sección y página de procedencia. Los planos no se convierten en obras independientes. La etiqueta del enlace se conserva aunque parezca incompleta; no se corrigen supuestos errores editoriales del ayuntamiento.

Cobertura parcial del inventario documental del PGOU accesible actualmente, no un histórico exhaustivo municipal. La página está completa en un único HTML y no presenta paginación. El parser rechaza controles de paginación/continuación detectados para evitar truncamiento silencioso. No hay límite artificial de documentos. Requiere el encabezado específico del instrumento y documentación sustantiva; ante cambios de estructura falla sin sustituir el resultado anterior.

No se afirma vigencia jurídica, aprobación definitiva, concesión de licencia ni ejecución física. No se deducen fechas de nombres de archivos, fechas de noticias, metadatos del CMS o cláusulas normativas. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulos, así como coordenadas y geometría. El contenido de un documento puede referirse a instrumentos anteriores y no se traslada como fecha del PGOU. `publication_ready=false` indica que estos registros no autorizan publicación. Licencias, programación y jitter geográfico quedan desactivados en el manifest.

No se descargan ni interpretan automáticamente los 71 archivos. Se verificaron dos muestras sustantivas: memoria de ordenación (`/wp-content/uploads/docs/PGOU/pgou/01.pdf`) y normativa (`/wp-content/uploads/docs/PGOU/pgou/04.pdf`), ambas HTTP 200, `application/pdf`, firma `%PDF-`. Se capturaron los primeros 4096 bytes de cada una; no son copias PDF completas. Los demás enlaces se retienen sin garantía individual de disponibilidad.

## Implementación y verificación

Se inspeccionaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos Hernani, Chipiona y Manlleu. No se modifican fuentes compartidas ni dependencias.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_hornachuelos -v` — **6 correctas**. Cubren agrupación, procedencia, ausencia de fechas/geometría inventadas, rechazo de formularios y vacíos, paginación, documentos externos, retención de 122 documentos sin truncamiento, manifest/carga mediante registry, licencias desactivadas y preservación del resultado ante fallo.

Extracción real ejecutada mediante `load_portal_adapter(load_manifest('hornachuelos')).backfill_proyectos(...)`, con `capture_dir` apuntando a `evidence/`. Resultado: **1 registro, 71 documentos**. `update_proyectos` refresca la instantánea completa; no mantiene un cursor ni historial de bajas. Solo se reemplaza el JSONL después de completar y validar el inventario.

Evidencia local, sin incorporación al código: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de descubrimiento/inventario y muestras parciales PDF. `validation.json` incluye recuento real, URLs, comprobaciones documentales, paginación y limitaciones. La anotación de política compartida devuelve categoría `unknown`; no se fuerza una categoría comercial para un instrumento urbanístico. No se ejecutaron bases de datos, publicación ni despliegues.
