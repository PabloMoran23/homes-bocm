# Jódar — Jaén — INE 23053

Consulta y ejecución real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

- Web municipal: https://www.jodar.es/ y sección de áreas
  https://www.jodar.es/ayuntamiento/areas/ . El buscador público WordPress
  `/wp-json/wp/v2/search?search=urbanismo&per_page=100` permitió localizar
  https://www.jodar.es/ayuntamiento/urbanismo/ . Esta última responde HTTP 200
  pero declara **«No hay publicaciones de Urbanismo»**. No se convierte en
  instrumento sintético ni se toma su navegación como inventario.
- https://jodar.sedelectronica.es/info.0 muestra trámites, tablón y transparencia.
  https://jodar.sedelectronica.es/transparency/ muestra «7. URBANISMO, OBRAS
  PÚBLICAS Y MEDIO AMBIENTE (1)». Una petición de expansión Wicket no devolvió
  contenido documental utilizable; no se afirma que la categoría esté vacía.
  Los trámites para solicitar licencia no prueban concesiones.
- Se revisó también el índice provincial
  https://www.dipujaen.es/conoce-diputacion/areas-organismos-empresas/areaF/urbanismo/planeamiento/ .
  Es un índice general, con enlace a un PDF de desarrollo provincial de octubre
  de 2025; no se extrajo un proyecto municipal ficticio a partir de él.
- Inventario utilizado: https://www.jodar.es/wp-json/wp/v2/posts . Consulta real
  con `per_page=100&page=1`: **22 publicaciones, una página**, según las cabeceras
  `X-WP-Total` y `X-WP-TotalPages`. El adaptador recorre todas las páginas,
  comprueba estabilidad de ambas cabeceras, número total e identificadores
  únicos y falla ante una instantánea incompleta o cambiante. No usa búsquedas
  limitadas ni una primera página truncada.

## Resultado y alcance

**Un proyecto físico real**, extraído del contenido servido actualmente:
«RESTITUCIÓN DE CÉSPED DE CAMPO DE FÚTBOL MUNICIPAL FRANCISCO HERRERA CUEVA».
La publicación municipal describe expresamente esa obra proyectada, una
subvención ministerial de 128.627,02 euros y otra aportación provincial de
64.313,51 euros para el mismo proyecto. Se genera **un solo registro**, sin
desdoblar financiadores en proyectos diferentes.

Fuente de detalle, comprobada además mediante HTTP 200 en HTML:
https://www.jodar.es/blog/2026/01/29/anuncio-concesion-de-subvencion-ministerio-de-politica-territorial-y-memoria-democratica/

El parser exige una mención al Ayuntamiento de Jódar, un proyecto nombrado
expresamente entre comillas en la narrativa de financiación y un término de
obra física en su nombre. Obtiene el título del texto, no de un registro
precargado. Agrupa menciones por nombre normalizado y conserva publicaciones y
enlaces documentales en `documentos`. Se excluyen subvenciones de empleo,
actividades deportivas, actividades culturales, equipamiento informático,
formularios y anuncios de contratación sin proyecto documentado.

La cobertura es **parcial y conservadora**: proyectos físicos explícitos en
anuncios municipales de financiación. No es el inventario íntegro de obras,
planeamiento, licencias ni ejecución. Las publicaciones sobre planes de empleo
2024-2025 y 2025-2026, y el plan provincial de cooperación, no individualizan
en su propio texto una obra; sus BOP enlazados no se han parseado. Se excluyen
sin afirmar que carezcan de proyectos.

## Fechas, procedencia y límites

`fecha_publicacion=2026-01-29` procede del campo `date` del CMS de la publicación
10866, sin inferir hora UTC. No se confunde con la publicación en BOE del
14 de enero de 2026 ni con la resolución de financiación de 29 de diciembre
de 2025 mencionadas en otro párrafo. Esas fechas no acreditan aprobación del
proyecto: `fecha_acuerdo` y `fecha_aprob` permanecen nulas. Tampoco se infieren
fase, adjudicación, licencia concedida, inicio o terminación de obra.

Sin coordenadas ni geometría verificadas; `publication_ready=false`,
`geometry_status=unavailable`. Licencias, ejecución programada y jitter de
geocodificación están desactivados. La política compartida aplicada por el
registro de adaptadores clasificó la entidad como `pendiente`, con
`insufficient_identity_evidence`, `activity_eligible=false` y
`grant_evidenced=false`; se conserva este resultado sin alterar fuentes
compartidas ni atribuirle una concesión de licencia.

## Validación reproducible y evidencia local

`python -m unittest municipio.test_jodar -v`: **7 pruebas correctas**. Cubren
extracción del nombre, semántica de fechas, ausencia de geometría, agrupación
e independencia documental, exclusiones, procedencia, manifiesto, recorrido
de páginas y rechazo de duplicados o cambios del inventario.

Ejecución real mediante `load_manifest('jodar')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`config['capture_dir']` apuntando a `evidence/`. Resultado: **22 publicaciones
leídas, 1 registro escrito**, sin base de datos, publicación ni geocodificación.

Evidencia local, fuera de los cuatro archivos fuente:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/posts-1.json`,
`evidence/proyecto-campo-futbol.html`, `evidence/areas.html`,
`evidence/urbanismo.html`, `evidence/sede.html`, `evidence/transparencia.html`,
`evidence/transparency-urbanismo.xml` y `evidence/diputacion.html`.
El JSON de validación incluye cantidad real, URLs, runtime y limitaciones.
