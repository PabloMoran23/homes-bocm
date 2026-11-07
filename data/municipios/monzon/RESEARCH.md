# Monzón — INE 22158

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://www.xn--monzn-3ta.es/estudios-y-planes-propios

El dominio municipal https://www.monzon.es/ enlaza Urbanismo y Obras en el dominio internacionalizado https://www.xn--monzn-3ta.es/entidades-y-asociaciones . Su navegación enlaza Estudios y Planes Propios. Se descubren tres documentos de planes concretos: índice del Plan Director del Castillo, Plan Director del río Sosa y PMUS febrero2019. El documento Plan de Acción2022 es genérico y se excluye. Cobertura documental parcial; el índice del castillo no se presenta como todo el expediente. No hay scraping de noticias, licencias o el resto del archivo.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **3 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_monzon -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `monzon/proyectos.jsonl` y `monzon/validation.json` del orquestador.

Ejemplo extraído: **PLAN DIRECTOR DEL CASTILLO DE MONZÓN - ÍNDICE**, https://www.xn--monzn-3ta.es/documents/5482479/0c9697ba-fd9b-3e1e-6688-60a5b5567292?download=true

Verificación puntual de destino: HTTP 200, tipo `application/pdf`, firma PDF `True` en https://www.xn--monzn-3ta.es/documents/5482479/0c9697ba-fd9b-3e1e-6688-60a5b5567292?download=true. Solo se leyó un fragmento inicial de muestra; no se descargó todo el archivo masivamente.
