# Caldes de Montbui — INE 08033

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://seu-e.cat/ca/web/caldesdemontbui/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic

La web https://www.caldesdemontbui.cat/temes/urbanisme-i-habitatge delega la normativa en seu-e.cat. La tabla publicada contiene un registro concreto con Tema Pla d’ordenació urbanística municipal, expediente2003/007926/B, enlace RPUC207531 y PDF POUM. El parser descubre filas por cabeceras, no por ID fijo de fila. El título se toma de Tema; no se corrige la inconsistencia del campo Instrument que dice Pla director urbanístic. No se infieren fechas ni fases. La variante www redirige a seu-e.cat:443; el adaptador usa la canónica sin www. Inventario parcial de una fila, no todas las modificaciones del POUM.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **1 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_caldes_de_montbui -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `caldes-de-montbui/proyectos.jsonl` y `caldes-de-montbui/validation.json` del orquestador.

Ejemplo extraído: **Pla d'ordenació urbanística municipal**, https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/207531/documents

Verificación puntual de destino: HTTP 200, tipo `application/pdf`, firma PDF `True` en https://seu-e.cat/documents/29428/18298858/POUM/091caa86-59f3-4a66-b98e-135d162a55a7. Solo se leyó un fragmento inicial de muestra; no se descargó todo el archivo masivamente.
