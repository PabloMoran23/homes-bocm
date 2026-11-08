# Nájera — INE 26102, La Rioja

Verificado el 2026-11-08 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifiestos,
el registro de adaptadores y los ejemplos de Hernani y Manlleu antes de implementar.

La página municipal de información urbanística:
https://najera.es/najera/cartografia/informacion-urbanistica-siu/
responde HTTP 200 y remite al SIU nacional antiguo. La búsqueda del inventario
regional localizó https://siu.larioja.org/mapa_municipio.php?cod_ine=102 . Este último
ofrece en el índice del buscador planeamiento general, modificaciones y desarrollo,
pero las peticiones HTTP reales desde el runtime devolvieron 403 (Cloudflare).
No se incorporaron esos resultados del buscador como registros extraídos.
El catálogo de https://najera.sedelectronica.es/ ofrece solicitudes de autorización;
no acredita concesiones. No se extraen licencias.

La API pública municipal WordPress permitió descubrir páginas de obras físicas.
La consulta exploratoria `https://najera.es/wp-json/wp/v2/pages?search=plan&per_page=100`
identificó fichas bajo `/obras-eu/`. La búsqueda textual inicial NO se usa como
inventario de producción: omitía, por ejemplo, la ficha de alumbrado monumental.
La página padre https://najera.es/obras-eu/ existe pero su HTML no enumera sus hijos.
La jerarquía publicada de WordPress es el inventario utilizado:

- https://najera.es/wp-json/wp/v2/pages?slug=obras-eu&per_page=100&page=1
- https://najera.es/wp-json/wp/v2/pages?parent=4316&orderby=id&order=asc&per_page=100&page=1

El padre se resuelve por slug e identidad URL, sin fijar el ID en el scraper.
La consulta de hijos retornó `X-WP-Total: 6`, `X-WP-TotalPages: 1`. El adaptador
recorre todas las páginas anunciadas; comprueba que el total y el número de páginas
no cambien entre peticiones y que los IDs sean únicos y completen el total.
Los errores HTTP, respuesta sin cabeceras, inventarios vacíos, identidad inesperada
o fichas sin narrativa verificable abortan antes de reemplazar la salida.

## Registros reales y unidad de extracción

Se extrajeron seis fichas municipales, verificadas también en sus páginas HTML:

| WP ID | Obra / ficha | Publicación de ficha |
| --- | --- | --- |
| 4318 | [Ruta Cicloturista y Parque Natural](https://najera.es/obras-eu/ruta-cicloturista-parque-natural/) | 2026-11-01 |
| 4388 | [Alumbrado del Casco Histórico](https://najera.es/obras-eu/alumbrado-casco-historico/) | 2026-11-03 |
| 4389 | [Alumbrado monumental](https://najera.es/obras-eu/alumbrado-monumental/) | 2026-11-03 |
| 4392 | [Plaza de España](https://najera.es/obras-eu/plaza-de-espana/) | 2026-11-03 |
| 4394 | [Placas solares en Albergue Municipal](https://najera.es/obras-eu/placas-solares-albergue-municipal/) | 2026-11-03 |
| 4396 | [Placas solares en Pabellón Multiusos](https://najera.es/obras-eu/placas-solares-en-pabellon-multiusos/) | 2026-11-03 |

Son descripciones oficiales de intervenciones físicas iniciadas o ejecutadas, con
narrativa de instalación, renovación, repavimentación o ejecución. No son anuncios
de contratación ni meras noticias de financiación. Se exige objeto físico y una
afirmación de ejecución en el contenido, además de procedencia municipal y jerarquía.
Las páginas generales, agenda, noticias culturales y trámites quedan fuera de la
consulta. Una nueva ficha sin narrativa reconocida exige revisar el alcance.

Un registro corresponde a una ficha; 4318 agrupa explícitamente dos actuaciones:
ruta cicloturista y conservación del Parque Natural. Se conserva como dossier conjunto,
sin inventar identificadores de expediente ni repartir importes entre actuaciones.
Las dos fichas de alumbrado se mantienen diferenciadas tal como las publica el
Ayuntamiento. No se convierten fotografías, planos o documentos en proyectos extra.
`documentos` retiene la ficha fuente y cualquier PDF municipal enlazado, deduplicado
por URL. En las seis fichas actuales no hay PDFs adjuntos: las imágenes ilustrativas
y enlaces generales a entidades no se presentan como documentos de expediente.

## Fechas, calidad y límites

`fecha_publicacion` procede exclusivamente de `date` en WordPress (fecha local de
publicación de la ficha); `modified` se conserva aparte en `provenance`. Ninguna de
ellas se usa como aprobación, acuerdo, adjudicación o finalización. Los campos
`fecha`, `fecha_acuerdo` y `fecha_aprob` permanecen nulos. Los periodos aproximados
y fechas de ejecución se conservan en la descripción, sin normalizarlos a una fecha
ficticia. Las fichas contienen fragmentos editoriales truncados, paréntesis y una
adjudicataria del albergue sin completar; no se rellenan esos datos. Tampoco se
convierten los importes narrados de distinta naturaleza en un presupuesto único.

Cobertura parcial de obras de financiación europea publicadas bajo Obras EU.
No es inventario completo de obras municipales, proyectos privados, planeamiento
vigente, licencias ni histórico de contratación. El bloqueo del SIU impide incorporar
su inventario. Las actualizaciones refrescan toda la colección pública; no representan
un histórico persistente de fichas retiradas. No se publica ni se sincroniza nada.

`geometry_status: unavailable`. La página municipal describe visores SIU/cartografía,
pero no se verificó una geometría vectorial por ficha de obra. No se extraen puntos
del centro municipal ni coordenadas de mapas generales; lat/lon/geometry son nulos.
`publication_ready: false`, `schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`.

## Validación reproducible

`python -m unittest municipio.test_najera -v`: **7 pruebas pasan**, sin red.
Cubren procedencia, fechas, enlaces agrupados, IDs estables, exclusión de solicitudes
y licitaciones, todas las páginas, totales cambiantes/incompletos/duplicados, salida
previa intacta ante errores, licencias deshabilitadas y carga desde manifiesto/registro.

Extracción real mediante `load_manifest('najera')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **6 registros**.
Se activó `capture_dir: evidence` únicamente en memoria para guardar las respuestas.
Las seis páginas HTML se descargaron además con HTTP 200 y se verificaron sus títulos.
La anotación compartida del registro informa 6 categorías desconocidas; no se fuerza
una categoría ni se interpreta esa anotación como aprobación para publicación.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, respuestas API, HTML de fichas, página municipal SIU y
respuesta 403 regional. El informe incluye URLs exactas, limitaciones y comprobaciones.
