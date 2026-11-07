# Tolosa — INE 20071

Investigación y ejecución real: 7 de noviembre de 2026.

## Fuente y cobertura

https://udala.tolosa.eus/es/servicios/urbanismo-e-infraestructuras/plan-general-ordenación-urbana

Índice municipal de PGOU y modificaciones. En el contenido .field-name-body, los párrafos numerados 2.1,2.2,2.3 identifican San Esteban, Iurre y Polígono Industrial Usabal2. Se agrupan14,8 y3 documentos respectivos hasta el siguiente encabezado; no se mezclan documentos entre ámbitos. El enlace genérico al PGOU y archivos adjuntos externos al cuerpo se excluyen de esta cobertura. Los títulos de los documentos conservan si dicen avance/aprobación inicial/provisional/definitiva, pero no se inventa una fase actual por la mera presencia de varias versiones. El índice no tiene paginación observada. Cobertura parcial: tres modificaciones de este índice, no todos los planes especiales enlazados desde los menús globales.

Resultado: **3 registros** extraídos del inventario actual. No se devuelve un expediente literal precargado ni una página genérica como actuación sintética. La desaparición del contenedor/listado o ausencia de instrumentos/documentos provoca error.

## Semántica

Sin fechas de aprobación deducidas, sin coordenadas inventadas y sin inferir fases. Las fechas de actualización del CMS no son fechas de acuerdo. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`. Los manifests desactivan `schedule.enabled` y `geocode.jitter_missing`. Licencias desactivadas: no se ha verificado un registro público de concesiones.

## Comprobaciones

`python3 -m unittest municipio.adapters.test_tolosa -v`: correcto. Tests de contenido específico, rechazo de vacíos y ausencia de metadatos inventados; Tolosa prueba también aislamiento de documentos entre modificaciones.

Ejecución directa de `backfill_proyectos`, sin base de datos, publicación o geocodificación. Evidencia externa: `tolosa/proyectos.jsonl` y `tolosa/validation.json` del directorio del orquestador. Muestra documental: HTTP200, `application/pdf`, firma PDF válida en https://udala.tolosa.eus/sites/default/files/Informaci%C3%B3n%20y%20diagnostico.pdf. Solo se leyó el inicio del archivo; no se descargó todo el inventario masivamente.
