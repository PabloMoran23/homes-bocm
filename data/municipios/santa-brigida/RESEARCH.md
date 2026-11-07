# Santa Brígida — INE 35021

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://www.santabrigida.es/wp-json/wp/v2/posts?search=obras&per_page=100&page=1&orderby=date&order=desc

La portada respondió403 en una prueba, pero la API pública del mismo dominio municipal y enlaces de noticias funcionan. Se consultó la API completa:6páginas de resultados. El primer intento con máximo5 falló de forma explícita; tras revisar X-WP-TotalPages el manifest permite8. Filtro de intervención física+activo concreto en título, con exclusión de arte, ayudas, tráfico y reclamaciones. Revisión manual redujo44 a33comunicados; la corrección se incluyó en el filtro y pruebas. Ejemplos: reconstrucción del firme y muro Gamonal Alto, saneamiento Barranco Alonso/Guiniguada, asfaltado calles Los Lentiscos y Tomás Quevedo, reforma almacén Brimate. Las noticias pueden tratar varias fases de una misma obra y no son expedientes únicos.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **33 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_santa_brigida -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `santa-brigida/proyectos.jsonl` y `santa-brigida/validation.json` del orquestador.

Ejemplo extraído: **El Ayuntamiento acomete las obras de reconstrucción del firme y el muro en el Gamonal Alto**, https://www.santabrigida.es/el-ayuntamiento-acomete-las-obras-de-reconstruccion-del-firme-y-el-muro-en-el-gamonal-alto/
