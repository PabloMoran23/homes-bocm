# Lora del Río — INE 41055

Investigación: 7 de noviembre de 2026.

## Fuente y extracción

Inventario: https://nuevoplangeneraldeloradelrio.es/

Delegación verificada en la noticia oficial https://loradelrio.es/presentada-la-web-del-nuevo-pgom-de-lora-del-rio-en-la-que-se-podran-realizar-aportaciones-y-propuestas-vecinales-al-documento-urbanistico/ : contiene el enlace explícito www.nuevoplangeneraldeloradelrio.es . El micrositio tiene el título PGOM Lora del Río y enlaza el Diagnóstico previo técnico (Libro Fase2,2025). Se extrae un plan con ese documento. Se excluyen el manual participativo y un enlace residual a un PDF de Peñaflor de otro dominio. La antigua página de Urbanismo enlaza una carpeta Google Drive del PGOU vigente, que no se incorpora. Cobertura parcial del nuevo PGOM, sin afirmar aprobación ni vigencia.

El scraper lee el índice actual en cada ejecución y descubre documentos técnicos enlazados; no devuelve una lista literal de expedientes. Resultado real: 1 registros. Los nombres y enlaces proceden de la fuente. Inventario sin paginación observada; no se reclama cobertura de otros catálogos del municipio.

## Semántica y controles

Sin fechas, fases, centroides o coordenadas inventadas. `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false`, `geocode.jitter_missing: false`. Licencias desactivadas porque no se verificó un registro público de concesiones. La falta de título, contenedor o documentos produce error explícito. Los IDs de estos instrumentos derivan del título; un cambio editorial del título podría cambiar el ID.

## Validación

Ejecución real de `backfill_proyectos`; evidencia externa `lora-del-rio/proyectos.jsonl` y `lora-del-rio/validation.json`. Dos pruebas pasan: `python3 -m unittest municipio.adapters.test_lora_del_rio -v`; comprueban plan concreto, exclusión de documentos ajenos/formularios, ausencia de geometría/fechas y fallo sin documentos.

Una muestra documental se comprobó en vivo con HTTP200, tipo `application/pdf` y firma PDF válida: https://nuevoplangeneraldeloradelrio.es/wp-content/uploads/2025/10/Libro-Fase-2_Diagnostico-previo_Lora-del-Rio_2025_E2_compressed.pdf . Solo se leyó el fragmento inicial para verificar el tipo. No se ejecutó publicación, sincronización ni escritura en bases de datos.
