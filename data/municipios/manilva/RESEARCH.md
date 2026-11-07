# Manilva — INE 29068

Investigación: 7 de noviembre de 2026.

## Fuente y extracción

Inventario: https://manilva.es/documentos/

La pestaña GEUMA contiene el PGOU aprobado en1994 y la adaptación parcial LOUA de octubre2011, con13 y14 documentos respectivamente. Se agrupan documentos de /archivos/ bajo los encabezados h4 del contenedor GEUMA. Solicitudes de VPO, padrón, animales, formación y bolsa de empleo quedan fuera. Dos registros de instrumentos, no27 proyectos ficticios. El año conservado en el título procede de la fuente; no se transforma en fecha exacta de aprobación.

El scraper lee el índice actual en cada ejecución y descubre documentos técnicos enlazados; no devuelve una lista literal de expedientes. Resultado real: 2 registros. Los nombres y enlaces proceden de la fuente. Inventario sin paginación observada; no se reclama cobertura de otros catálogos del municipio.

## Semántica y controles

Sin fechas, fases, centroides o coordenadas inventadas. `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false`, `geocode.jitter_missing: false`. Licencias desactivadas porque no se verificó un registro público de concesiones. La falta de título, contenedor o documentos produce error explícito. Los IDs de estos instrumentos derivan del título; un cambio editorial del título podría cambiar el ID.

## Validación

Ejecución real de `backfill_proyectos`; evidencia externa `manilva/proyectos.jsonl` y `manilva/validation.json`. Dos pruebas pasan: `python3 -m unittest municipio.adapters.test_manilva -v`; comprueban plan concreto, exclusión de documentos ajenos/formularios, ausencia de geometría/fechas y fallo sin documentos.

Una muestra documental se comprobó en vivo con HTTP200, tipo `application/pdf` y firma PDF válida: https://manilva.es/archivos/PGOU%201994/Normativa%20Urban%C2%B0stica%20General%20diligenciada.pdf . Solo se leyó el fragmento inicial para verificar el tipo. No se ejecutó publicación, sincronización ni escritura en bases de datos.
