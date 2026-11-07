# Mungia — INE 48069

Investigación: 7 de noviembre de 2026.

## Fuente y extracción

Inventario: http://mungiaplanorokorra.eus/

La web municipal https://www.mungia.eus/es/hapo y su versión /eu/hapo enlazan expresamente http://mungiaplanorokorra.eus . Verificado en HTML200 con User-Agent Mozilla/5.0; el cliente sin ese encabezado recibió403 en una prueba. El micrositio dedicado al Plan Orokorra devuelve200 por HTTP tal como lo enlaza el ayuntamiento; HTTPS falla con TLSV1_ALERT_INTERNAL_ERROR. No se desactiva la validación TLS. Se recoge un único plan y cinco documentos técnicos de avance, memoria, documento estratégico y criterios, descubiertos por título y no por URL fija. Se excluyen manuales participativos, carteles y formularios. El contenido en euskera se conserva literalmente. Cobertura de este plan en elaboración, no del planeamiento vigente completo.

El scraper lee el índice actual en cada ejecución y descubre documentos técnicos enlazados; no devuelve una lista literal de expedientes. Resultado real: 1 registros. Los nombres y enlaces proceden de la fuente. Inventario sin paginación observada; no se reclama cobertura de otros catálogos del municipio.

## Semántica y controles

Sin fechas, fases, centroides o coordenadas inventadas. `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false`, `geocode.jitter_missing: false`. Licencias desactivadas porque no se verificó un registro público de concesiones. La falta de título, contenedor o documentos produce error explícito. Los IDs de estos instrumentos derivan del título; un cambio editorial del título podría cambiar el ID.

## Validación

Ejecución real de `backfill_proyectos`; evidencia externa `mungia/proyectos.jsonl` y `mungia/validation.json`. Dos pruebas pasan: `python3 -m unittest municipio.adapters.test_mungia -v`; comprueban plan concreto, exclusión de documentos ajenos/formularios, ausencia de geometría/fechas y fallo sin documentos.

Una muestra documental se comprobó en vivo con HTTP200, tipo `application/pdf` y firma PDF válida: http://mungiaplanorokorra.eus/wp-content/uploads/2023/02/01-Aurrerapena_HI_IM_FDO_compressed.pdf . Solo se leyó el fragmento inicial para verificar el tipo. No se ejecutó publicación, sincronización ni escritura en bases de datos.
