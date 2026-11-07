# Parets del Vallès — INE 08159

Investigación y extracción directa: 7 de noviembre de 2026.

Fuente municipal oficial de inventario de planeamiento: https://www.parets.cat/ajuntament/informacio-oficial/urbanisme/planejament-urbanistic-derivat.html

El adaptador vuelve a consultar este inventario en cada ejecución. Extrae el título del plan y los documentos enlazados desde el contenido específico (`.ddbbtext`). Agrupa los documentos bajo los encabezados de cada instrumento; los encabezados de familias no se convierten en proyectos. Se identificaron 25 instrumentos, incluyendo PE4, Can Serra, Torre de Cellers, UP-7 el Cementiri y UP5 Sector Circuit.

Ejecución real: 25 registros; se comprobó HTTP 200 y firma PDF real en una muestra: https://www.parets.cat/media/repository/ajuntament/Informacio_oficial/Normativa_urbanistica/Pla_de_millora_de_l_Eixample/bop_pmu_eixample.pdf . El resto de enlaces se descubre dinámicamente en HTML, sin descargarlos de forma masiva.

No se deducen fechas de aprobación de las fechas de actualización de la web, ni se inventan fases o geometrías. `publication_ready: false`, `geometry_status: unavailable`; no centroides. `schedule.enabled: false`, `geocode.jitter_missing: false`. Licencias desactivadas: no se ha verificado registro público de concesiones; formularios no se extraen.

La extracción falla si desaparece el contenedor, faltan títulos o no quedan documentos. No hay paginación en el inventario inspeccionado; actualización mediante snapshot de la página completa. Los IDs derivan del título del instrumento; un cambio de título puede cambiar el ID. No se reclama cobertura de información pública o licencias fuera de este inventario.

Validación: `python3 -m unittest municipio.adapters.test_parets_del_valles -v` y ejecución directa `backfill_proyectos`. Evidencias en el directorio externo del orquestador `parets-del-valles/proyectos.jsonl` y `parets-del-valles/validation.json`. No se ejecuta ingestión ni publicación.
