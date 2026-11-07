# Palamós — INE 17118

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://www.palamos.cat/POUM/index.html

La portada municipal https://www.palamos.cat/ enlaza POUM; la pantalla https://www.palamos.cat/poum enlaza este índice. Su title identifica expresamente el POUM de Palamós. Se extrae un único plan con dos PDFs normativos enlazados, incluyendo texto consolidado no normativo, que se etiqueta según el título original. No se presentan normas como nuevos proyectos. Cobertura parcial: el visor y documentos de planos que requieren subnavegación quedan fuera. El índice se vuelve a leer en cada ejecución.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **1 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_palamos -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `palamos/proyectos.jsonl` y `palamos/validation.json` del orquestador.

Ejemplo extraído: **PLA D'ORDENACIÓ URBANÍSTICA MUNICIPAL DE PALAMÓS**, https://www.palamos.cat/POUM/index.html

Verificación puntual de destino: HTTP 200, tipo `application/pdf`, firma PDF `True` en https://www.palamos.cat/POUM/planols/pdf/NORMES/TEXT/03. 1 Text.pdf. Solo se leyó un fragmento inicial de muestra; no se descargó todo el archivo masivamente.
