# Cabra — INE 14013

Investigación y ejecución real: 7 de noviembre de 2026.

## Fuente y cobertura

https://cabra.eu/plan-general-de-ordenacion-urbanistica/

La portada municipal https://cabra.eu/ enlaza el PGOU y Planeamiento Desarrollo. El segundo no presenta documentos en el HTML inspeccionado. El índice del PGOU sí publica cinco PDFs: planos de ordenación, normas/fichas, memoria, diagnóstico territorial y catálogo de elementos protegidos. Se produce un único registro del plan con los cinco documentos, no cinco proyectos independientes. Se consulta el índice actualizado cada vez; no se reclaman nuevas licencias ni noticias o todo el planeamiento de desarrollo.

Resultado: **1 registros** extraídos del inventario actual. No se devuelve un expediente literal precargado ni una página genérica como actuación sintética. La desaparición del contenedor/listado o ausencia de instrumentos/documentos provoca error.

## Semántica

Sin fechas de aprobación deducidas, sin coordenadas inventadas y sin inferir fases. Las fechas de actualización del CMS no son fechas de acuerdo. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`. Los manifests desactivan `schedule.enabled` y `geocode.jitter_missing`. Licencias desactivadas: no se ha verificado un registro público de concesiones.

## Comprobaciones

`python3 -m unittest municipio.adapters.test_cabra -v`: correcto. Tests de contenido específico, rechazo de vacíos y ausencia de metadatos inventados; Tolosa prueba también aislamiento de documentos entre modificaciones.

Ejecución directa de `backfill_proyectos`, sin base de datos, publicación o geocodificación. Evidencia externa: `cabra/proyectos.jsonl` y `cabra/validation.json` del directorio del orquestador. Muestra documental: HTTP200, `application/pdf`, firma PDF válida en https://cabra.eu/wp-content/uploads/2023/03/TR_PLANOS-ORDENACION.pdf. Solo se leyó el inicio del archivo; no se descargó todo el inventario masivamente.
