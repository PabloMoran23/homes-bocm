# El Astillero — INE 39008

## Fuente y alcance comprobados (2026-11-07)

El [inventario de Urbanismo del Ayuntamiento](https://www.astillero.es/content/urbanismo) enlaza directamente sus secciones [Normativa](https://www.astillero.es/content/normas-urbanismo), [Anexos](https://www.astillero.es/content/anexos-urbanismo) y [Memoria](https://www.astillero.es/content/memoria-urbanismo). Las cuatro páginas responden HTTP 200. El adaptador vuelve a descubrir esos enlaces en cada ejecución y extrae los PDF actuales dentro del contenido municipal, excluyendo navegación y dominios externos. Falla si desaparece una sección o no contiene documentos.

La [Memoria original](https://www.astillero.es/ckfinder/userfiles/files/MEMORIA.pdf), descargada con HTTP 200 y firma PDF válida, identifica en su página 2 la **Revisión de las Normas Subsidiarias de Planeamiento Municipal de Astillero**. Describe su documentación como memoria, normas, anexos y planos. El registro agrupa memoria, normas y anexos disponibles; no se afirma cobertura de todos los planos. La misma página indica texto para aprobación provisional: no atribuimos aprobación definitiva, vigencia actual ni fecha a este instrumento. El título de registro se identifica mediante este documento, no mediante el rótulo PGOU que el portal aplica a otro enlace externo por IP. Ese enlace externo y las ordenanzas generales no se ingieren.

## Validación y límites

Captura directa acotada de cuatro páginas: **1 instrumento real, 33 documentos PDF enlazados**. Tres pruebas unitarias verifican descubrimiento, límites de dominio/ruta, deduplicación, ausencia de fechas/fases/geometría inventadas y fallo ante cambios de estructura. Muestra PDF verificada: Memoria. No se afirma haber descargado cada PDF ni disponer de un registro histórico exhaustivo, expedientes nuevos o licencias.

Evidencia local fuera del repositorio: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/el-astillero/proyectos.jsonl` y `validation.json`. Ejecutado únicamente `ElAstilleroAyuntamientoAdapter.backfill_proyectos` hacia esos artefactos y pruebas locales; sin publicación ni conexión a base de datos.

No se han verificado geometrías reales; `publication_ready: false`, `geometry_status: unavailable`. Licencias desactivadas, `schedule.enabled: false` y `geocode.jitter_missing: false`. La actualización regenera idempotentemente el inventario documental actual.
