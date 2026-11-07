# La Zubia — INE 18193

Verificado 2026-11-07. Alcance limitado al catálogo patrimonial municipal documentado.

## Fuentes y cobertura

https://lazubia.es/urbanismo/planeamiento-de-desarrollo/ — HTTP 200.
Inventario municipal actual de planeamiento de desarrollo: identifica expresamente
el Catálogo de Bienes y Espacios Protegidos y enlaza su memoria y planos PDF.
Se descubrió mediante la búsqueda pública WordPress
https://lazubia.es/wp-json/wp/v2/search?search=planeamiento&per_page=100

El adapter lee el contenido central de ese inventario, verifica la identidad del
instrumento y recoge sus documentos actuales. **1 instrumento, 2 documentos, 0
licencias** en extracción directa. No genera un proyecto por plano ni por documento.
No toma documentos del menú general (revista de fiestas, deportes, etc.). Fechas
nulas porque la página no acredita fecha de publicación/acuerdo del instrumento.
No se copia el título como descripción. No se afirma cobertura de modificaciones,
expedientes o licencias que no están publicados en esta página.

La página general https://lazubia.es/urbanismo/planeamiento/ enlaza un iframe OneDrive
público. La respuesta HTTP200 del embed no proporciona un inventario utilizable en
HTML; no se aceptó ese enlace genérico como un proyecto. Los documentos del catálogo
sí están alojados directamente en el dominio municipal:
- https://lazubia.es/wp-content/uploads/CATÁLOGO-APROBACION-DEFINITIVA.pdf
- https://lazubia.es/wp-content/uploads/PLANOS-APROB-DEFINITIVA.pdf

## Geometría / visor

geometry_status: unavailable

Se inspeccionaron las páginas municipales de Urbanismo, Planeamiento y Planeamiento
de desarrollo, incluidos iframe y enlaces. Exponen planos PDF y carpeta OneDrive;
no se obtuvo API vectorial o polígono verificable del catálogo. No se vectorizaron
planos ni fabricaron puntos. Falta una fuente GIS ligada a sus bienes/ámbitos.

## Validación

2 pruebas pasan: agrupación de memoria/planos, exclusión de navegación y fallo ante
pérdida de título/documentos. Prueba directa HTTP timeout25s con JSONL/validation.json
en `/home/pablo/homes/artifacts/municipio-local-batches-20261107/la-zubia/`.
Sin orquestador/DB/cola/publicación. `schedule.enabled: false`, licencias deshabilitadas,
`geocode.jitter_missing: false`. Integración de código no equivale a aptitud geográfica
para publicar. El extractor acota explícitamente este instrumento; ampliar cobertura
requiere resolver el inventario general de OneDrive u otra fuente del ayuntamiento.
