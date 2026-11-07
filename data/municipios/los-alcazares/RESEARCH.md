# Los Alcázares — INE 30902

Verificado 2026-11-07. Alcance: anuncios municipales de inicio de obras de edificios.

## Fuente oficial y alcance

https://losalcazares.es/wp-json/wp/v2/posts?search=obra&per_page=100
API HTTP 200, **3 páginas recorridas** en prueba directa. Descubre nuevos anuncios
sin fijar una noticia concreta. Solo títulos «Comienzan las obras de/del/para...»
y edificios/centros/colegios/aulas/oficinas/pabellones, con descripción fuente
sustantiva. Excluye licitaciones, adjudicaciones, actos y noticias de fin de obra
para no duplicar cada hito como proyecto. Los cinco casos obtenidos son distintos.
IDs estables por artículo; si el portal republica el mismo inicio con otro ID se
necesitará reconciliación adicional. Fecha de publicación del post, no fecha de
concesión ni fecha contractual. No calcula estado vigente desde noticias históricas.

Resultado: **5 proyectos documentados, 0 licencias**:
- Oficina de turismo flexible.
- Rehabilitación del Edificio Alcázar.
- Remodelación del Centro Cívico Los Narejos.
- Nuevo Pabellón Deportivo.
- Cuatro aulas nuevas en Colegio Petra Sánchez Rollán.

La fuente contiene el texto real de cada obra. No constituye inventario completo
de planeamiento ni todas las actuaciones municipales. La API de páginas/áreas y
búsqueda de tablón no proporcionó inventario urbanístico usable. La sección
https://losalcazares.es/negociado/urbanismo/ contiene solicitudes/declaraciones,
que no acreditan concesiones y quedan excluidas.

## Geometría / visor

geometry_status: unavailable

Búsqueda oficial `site:losalcazares.es visor urbanismo GIS`: referencias a visores
SNCZI/CHS en documentos de inundabilidad, no geometrías identificadas de estas obras.
Los posts extraídos no aportan geometrías verificadas. No se usa el centro municipal
ni direcciones inferidas para fabricar coordenadas. Queda pendiente enriquecimiento
con una fuente de parcelas/edificios y correspondencia inequívoca.

## Validación

Dos tests pasan: reconocimiento acotado de inicios de edificios, exclusión de fin
de obra/asfaltado/trámites/teatro, falta de texto detectada, fechas de publicación.
Límite20 páginas con error explícito al superarlo; timeout25s y pausa0,35s.
JSONL/validation.json: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/los-alcazares/`.
`schedule.enabled: false`, licencias deshabilitadas y `geocode.jitter_missing: false`.
Sin DB, publicación ni orquestador. Geografía pendiente para publicar.
