# Burlada / Burlata — INE 31060

Verificado 2026-11-07. Integración como código, deshabilitada para refresco.

## Fuentes oficiales

- https://www.burlada.es/wp-json/wp/v2/noticias?search=plan%20especial&per_page=100 — API municipal HTTP 200, una página en la prueba.
- https://www.burlada.es/ordenanzas-municipales-de-urbanismo/ — índice urbanístico HTTP 200.
- https://www.burlada.es/wp-json/wp/v2/types — confirma `noticias` como colección pública.

Se obtienen anuncios iniciales de participación de planes especiales reales. La
búsqueda completa se pagina (máximo 20 páginas, fallo si se supera). El título debe
identificar plan especial/PEAU y el cuerpo debe declarar el inicio de participación
y enlazar documentos PDF. Se excluyen noticias no urbanísticas, reuniones de retorno,
formularios y conclusiones posteriores. El encabezado del cuerpo identifica el
expediente cuando el título solo dice «Infórmate y participa».

Prueba directa: **5 proyectos/anuncios iniciales, 0 licencias**. Incluyen Landazábal,
Gure Kabia parcela 86, cambios a residencial en plantas bajas, accesibilidad en
varias comunidades y APD-R2/Embutidos Ciganda. Los IDs usan el identificador municipal
estable; las fechas son las de publicación del artículo, no aprobación ni concesión.
No se afirma cobertura de todos los instrumentos ni se descargan los PDFs.

## Geometría / visor

geometry_status: unavailable

El índice oficial enlaza el SIUN de Navarra:
https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/instrumento/19357
(plan general municipal) y su índice de instrumentos. No se ha verificado una API
vectorial ni una correspondencia inequívoca de geometría con estos anuncios.
Se conservan los documentos; no se fabrican polígonos o puntos municipales.
No se afirma que no exista cartografía en SIUN, solo que no está integrada.

## Validación y límites

2 pruebas pasan: selección de anuncio inicial, exclusión de reunión posterior,
fecha de publicación y uso de título real en encabezado. Extracción directa con
HTTP timeout 25 s, sin orquestador ni DB. JSONL e informe guardados en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/burlada/`.
`licencias.enabled: false`, `schedule.enabled: false`, `geocode.jitter_missing: false`.
El sitio de trámites no acredita concesiones; el método de licencias devuelve vacío.
Pendiente geometría para satisfacer controles de publicación con coordenadas.
