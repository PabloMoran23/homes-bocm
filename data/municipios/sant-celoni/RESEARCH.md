# Sant Celoni — INE 08202

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente y cobertura

Fuente: https://santceloni.cat/11437

La sección municipal Projectes de gestió urbanística en tràmit enlazada desde https://santceloni.cat/area.php?id=8 enumera proyectos bajo encabezados strong. Se agrupan PDFs bajo cada encabezado que empieza por Projecte; se excluyen estatutos/constitución de asociaciones de cooperación. Cuatro proyectos: finca Pl. dels Estudis16, conexión de aguas residuales Batllòria/Riells, reparcelación P10 Cementiri e itinerario Ruta de la Tordera. La etiqueta de trámite es de la página; no se inventan fases individuales. Inventario sin paginación.

Cada ejecución vuelve a consultar la fuente publicada; no devuelve registros literales precargados. Se observaron **4 registros reales**. No se afirma cobertura completa de todos los instrumentos o actuaciones municipales.

## Semántica y límites

No se inventan fechas, fases ni coordenadas. Las noticias conservan únicamente `fecha_publicacion` cuando existe en la API; en inventarios no se interpreta una fecha genérica de actualización como aprobación. Todos los registros indican `publication_ready: false` y `geometry_status: unavailable`. `schedule.enabled: false` y `geocode.jitter_missing: false`; licencias desactivadas por no verificar un registro público de concesiones. Formularios, manuales y páginas de búsqueda no se transforman en licencias/proyectos.

Las respuestas vacías o un cambio de estructura provocan error. Los scrapers de noticias fallan si el límite de páginas impide completar el historial consultado. Los inventarios de esta implementación son páginas completas sin paginación observada. Los IDs derivan del ID oficial de noticia, URL del expediente/documento, o título del instrumento según la estructura de la fuente. No se ejecutan geocodificación, ingestión Supabase ni publicación.

## Evidencia

Pruebas: `python3 -m unittest municipio.adapters.test_sant_celoni -v`, correctas. Ejecución real directa de `backfill_proyectos`, con JSONL y métricas en el directorio externo `sant-celoni/proyectos.jsonl` y `sant-celoni/validation.json` del orquestador.

Ejemplo extraído: **Projecte tècnic de consolidació i condicionament com a espai visitable d’una finca a l’àmbit de la Força a la Pl. dels Estudis, 16 de Sant Celoni**, https://santceloni.cat/11437

Verificación puntual de destino: HTTP 200, tipo `application/pdf`, firma PDF `True` en https://santceloni.cat/ARXIUS/documents/arees/Entorn/Projecte_consolidacio_i_condicionament_Pl._Estudis__16.pdf. Solo se leyó un fragmento inicial de muestra; no se descargó todo el archivo masivamente.
