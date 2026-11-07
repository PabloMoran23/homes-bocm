# Monforte de Lemos — INE 27031

Investigación y extracción directa: 7 de noviembre de 2026.

Fuente municipal oficial de inventario de planeamiento: https://www.monfortedelemos.es/gl/urbanismo/planespecialcascohistorico/gl

El adaptador vuelve a consultar este inventario en cada ejecución. Extrae el título del plan y los documentos enlazados desde el contenido específico (`article .field-name-body`). La cobertura es un plan actual y sus documentos, no un catálogo completo de todas las modificaciones o nuevos proyectos del municipio. Las modificaciones enlazadas se conservan como documentos del plan.

Ejecución real: 1 registros; se comprobó HTTP 200 y firma PDF real en una muestra: https://www.monfortedelemos.es/sites/default/files/pdf/articulos_urbanismo_obras/Certificado_de_acordos_CERTIFICADO%202026-0001.pdf . El resto de enlaces se descubre dinámicamente en HTML, sin descargarlos de forma masiva.

No se deducen fechas de aprobación de las fechas de actualización de la web, ni se inventan fases o geometrías. `publication_ready: false`, `geometry_status: unavailable`; no centroides. `schedule.enabled: false`, `geocode.jitter_missing: false`. Licencias desactivadas: no se ha verificado registro público de concesiones; formularios no se extraen.

La extracción falla si desaparece el contenedor, faltan títulos o no quedan documentos. No hay paginación en el inventario inspeccionado; actualización mediante snapshot de la página completa. Los IDs derivan del título del instrumento; un cambio de título puede cambiar el ID. No se reclama cobertura de información pública o licencias fuera de este inventario.

Validación: `python3 -m unittest municipio.adapters.test_monforte_de_lemos -v` y ejecución directa `backfill_proyectos`. Evidencias en el directorio externo del orquestador `monforte-de-lemos/proyectos.jsonl` y `monforte-de-lemos/validation.json`. No se ejecuta ingestión ni publicación.
