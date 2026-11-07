# Guardamar del Segura — INE 03076

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://www.guardamardelsegura.es/wp-json/wp/v2/posts?search=obras&per_page=100&page=1&orderby=date&order=desc

La sección municipal https://www.guardamardelsegura.es/urbanismo-y-obras-publicas/ está vacía de documentos en HTML. La API WordPress pública sí devuelve un catálogo actualizable: una página completa, dos actuaciones reales retenidas: restauración y puesta en valor del castillo (ID39039) y rehabilitación/musealización de casa-museo del ingeniero Mira (ID39036). Se excluyen empleo público, subvenciones y eventos. Las fuentes son noticias oficiales; no se califican como licencias concedidas ni aprobaciones urbanísticas. La baja cantidad es cobertura real de la consulta obras, no un dato sintético.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **2 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_guardamar_del_segura -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `guardamar-del-segura/proyectos.jsonl` y `guardamar-del-segura/validation.json` del orquestador.

Ejemplo extraído: **Obras de restauración y puesta en valor del castillo de guardamar del segura**, https://www.guardamardelsegura.es/2021/03/05/obras-de-restauracion-y-puesta-en-valor-del-castillo-de-guardamar-del-segura/
