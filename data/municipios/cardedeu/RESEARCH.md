# Cardedeu — INE 08046

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://www.cardedeu.cat/temes/planejament-i-gestio-urbanistica/poum-pla-dordenacio-urbanistica-municipal-de-cardedeu

La sección https://www.cardedeu.cat/temes/planejament-i-gestio-urbanistica enlaza este inventario. Se descubren vínculos RPUC de expedientes concretos con título municipal, combinando el texto de la lista para conservar Modificació POUM y su ámbito. Deduplicación por URL de expediente, no por noticia. Se excluyen búsquedas genéricas, SITMUN, manuales y trámites. Veintiséis entradas reales incluyen PMU Can Montells, PMU26 Can Boixadera y modificaciones22–24. Los destinos RPUC redirigen a una aplicación JavaScript: se verifica HTTP200 del shell, no se declara que se hayan descargado sus documentos. Los metadatos proceden del inventario municipal explícito, sin ejecutar RPUC ni inferir aprobación. La carpeta Google Drive del POUM se deja fuera.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **26 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_cardedeu -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `cardedeu/proyectos.jsonl` y `cardedeu/validation.json` del orquestador.

Ejemplo extraído: **Pla de millora urbana - xamfrà c. J. C. I Busquets i av. Aviació catalana**, https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/239478

Verificación puntual de destino: HTTP 200, tipo `text/html; charset=UTF-8`, firma PDF `False` en https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/239478. Solo se leyó un fragmento inicial de muestra; no se descargó todo el archivo masivamente.
