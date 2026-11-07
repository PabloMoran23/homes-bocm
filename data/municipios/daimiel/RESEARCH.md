# Daimiel — Ciudad Real — INE 13039

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales y descubrimiento

El índice municipal de [Normativa](https://www.daimiel.es/es/transparencia-normativa) enlaza estos dos inventarios actuales del Ayuntamiento:

- [Normativa sobre urbanismo y medio ambiente](https://www.daimiel.es/es/transparencia-normativa-sobre-urbanismo-y-medio-ambiente): secciones «Plan de Ordenación Municipal 2009» y «Modificaciones al Plan de Ordenación Municipal 2009».
- [Normativa y documentos en tramitación](https://www.daimiel.es/es/transparencia-normativa-y-documentos-en-tramitacion): documentos individualmente rotulados como modificaciones del POM.

Se revisó el contrato `municipio/adapters/portal.py`, el cargador `municipio/manifest.py`, el registro de adaptadores y los ejemplos de Chipiona, Hernani y el manifest de Manlleu. El nuevo manifest usa importación dinámica y no necesita cambios compartidos.

La Delegación de Urbanismo expone modelos de solicitud y noticias, que no constituyen un registro de licencias otorgadas. No se usan. Tampoco se extraen ordenanzas, consultas de reglamentos, contratación ni planes operativos de emergencia (PAMFEMA/PAMIN/PLATEMUN), pues la cobertura elegida es el planeamiento urbanístico documental.

## Extracción y agrupación

El parser recorre los pares de párrafos Drupal de texto y archivos asociados. Conserva todos los documentos de la sección del POM, sin convertir cada plano en un proyecto. Agrupa modificaciones por su número explícito en el título; las modificaciones 7 y 9 tienen documentación en ambos inventarios. Cada documento conserva el rótulo original, URL PDF, sección y URL de inventario de procedencia. El resumen «Modificaciones al Plan de Ordenación Municipal» se vincula como documento del POM, sin crear un instrumento adicional. Los identificadores se basan en el instrumento, no en las rutas cambiantes de los archivos.

Resultado real: **7 instrumentos, 56 enlaces documentales**:

| Instrumento | Documentos |
| --- | ---: |
| POM 2009 (incluido resumen de modificaciones) | 46 |
| Modificación 5 | 1 |
| Modificación 6 | 1 |
| Modificación 7 | 2 |
| Modificación 9 | 4 |
| Modificación 10 | 1 |
| Modificación 11 | 1 |

Ambas páginas sirven los listados completos sin paginación observada. No hay límite de registros ni corte silencioso; si aparece un paginador, el adaptador falla expresamente para requerir revisión. La ausencia de párrafos, instrumentos o URLs documentales válidas también causa error. La salida solo se reemplaza después de obtener y procesar ambas páginas correctamente. `update_proyectos` refresca el inventario completo; no afirma disponer de un historial incremental.

## Semántica y límites

Cobertura parcial de documentos publicados del POM, no un inventario exhaustivo de licencias, expedientes, proyectos físicos u obras. La presencia de documentos en la categoría «en tramitación» no prueba su estado actual: puede conservar versiones históricas. Un rótulo «Aprobación definitiva» se conserva como título documental, sin inferir fechas o estado legal del instrumento. No se deducen fechas de acuerdo, aprobación o publicación de nombres, años del POM, rutas CMS o fechas de indexación. No se han extraído fechas del contenido PDF. No se afirma que todos los documentos sean versiones consolidadas o vigentes.

No hay coordenadas ni geometría verificada. Los registros declaran `publication_ready: false` y `geometry_status: unavailable`. El manifest identifica Daimiel, Ciudad Real, Castilla-La Mancha e INE 13039, con `schedule.enabled: false`, `geocode.jitter_missing: false` y `licencias.enabled: false`. Las llamadas a extracción de licencias fallan explícitamente porque no existe cobertura verificada.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_daimiel -v` — 4 correctas. Verifican agrupación entre inventarios, separación entre modificaciones, conservación de procedencia, exclusión de formularios/ordenanzas/emergencias, ausencia de metadatos inventados, rechazo de vacíos/paginación/URLs ajenas, escritura tras éxito completo, manifest y licencias desactivadas.

La ejecución real cargó `load_manifest('daimiel')` y `load_portal_adapter`, llamó a `backfill_proyectos(Path('evidence/proyectos.jsonl'))` y aplicó la política compartida de entidades del registro. Resultado: 7 registros. Los HTML obtenidos por el propio adaptador están en `evidence/inventory-1.html` e `inventory-2.html`. `evidence/validation.json` contiene recuentos, fuentes, limitaciones y comprobaciones documentales.

Se verificó un PDF por instrumento mediante GET con lectura parcial de 1024 bytes: los siete respondieron HTTP 200 con firma `%PDF-`. Se conservaron los prefijos en `evidence/daimiel-*-prefix.bin` y sus URLs/respuestas en validation.json. No se han descargado ni validado integralmente los 56 archivos; los planos del POM pueden ser grandes. Las capturas iniciales del descubrimiento también se conservan bajo evidence/. Toda la evidencia es local y no forma parte de los cuatro archivos fuente entregables. No se ha publicado ni accedido a servicios de despliegue o bases de datos.
