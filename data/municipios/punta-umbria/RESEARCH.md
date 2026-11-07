# Punta Umbría — Huelva — INE 21060

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- Portal municipal de transparencia: https://umbria.sedelectronica.es/transparency
- Sección 7, Urbanismo, Obras Públicas y Medio Ambiente: https://umbria.sedelectronica.es/transparency/93e27a44-0f50-4d5b-9014-a32fefea84e4/
- Inventario utilizado, sección 7.1, Planeamiento Urbanístico: https://umbria.sedelectronica.es/transparency/fd6042f5-c1a2-4aa0-af1b-92906ac0cb95/

El portal raíz anuncia 93 documentos en sección 7 y 16 en sección 9 (inversiones hidráulicas). La sección 7 distingue planeamiento (51 documentos), planes medioambientales (27), normativa (1), obras e infraestructuras (6), indicadores (0) y registro administrativo (4), además de cuatro documentos sueltos sobre zonificación lumínica/alumbrado y acuerdos. Estos recuentos son observaciones de la sesión, no constantes del scraper. El adaptador cubre exclusivamente 7.1; no pretende agotar todas las obras o el histórico municipal.

También se localizaron https://www.puntaumbria.es/urbanismo-y-medio-ambiente y https://www.puntaumbria.es/portal-de-transparencia mediante búsqueda. El acceso directo desde Python a www.puntaumbria.es falló por verificación de certificado; el host sin www falló por DNS. No se desactivó TLS. La sede municipal respondió con verificación TLS normal. El catálogo de trámites https://umbria.sedelectronica.es/info.0 ofrece solicitudes y declaraciones, que no se usan como licencias otorgadas. Se encontraron publicaciones históricas oficiales BOJA (por ejemplo https://www.juntadeandalucia.es/boja/2014/5/20), pero no se usan como sustituto de un inventario municipal actual ni se mezclan con los registros extraídos.

## Cobertura y agrupación

Resultado de `backfill_proyectos`: **10 instrumentos/proyectos, 47 enlaces documentales**:

| Instrumento o proyecto publicado | Documentos |
| --- | ---: |
| Estudio de detalle parcela equipamental SAPU 3-4 Co-housing | 8 |
| Proyecto de urbanización Camping Sindical | 5 |
| Proyecto de actuación refugio de animales Puntanimals | 3 |
| Proyecto de actuación actividad turística La Burrita María | 4 |
| Estudio de detalle parcela 5.4 ED2 | 1 |
| Actuación de transformación urbanística Puntamar | 5 |
| Reordenación parcelas dotacionales ED1-ED2 PERI Eucaliptal | 4 |
| Estudio de detalle calle Lepanto | 13 |
| Estudio de detalle calle Bellavista | 2 |
| Modificación puntual nº 16 del PGOU | 2 |

Las nueve carpetas tienen identidad estable por UUID, y cada registro conserva todos sus documentos, incluyendo versiones, planos, certificados y anuncios procedimentales. La modificación 16 agrupa dos documentos sueltos identificados por su título o descripción explícita; usa como identidad estable el menor URL documental del grupo. Los cuatro documentos restantes de 7.1 pertenecen a servicios de temporada de playas 2023 y se excluyen del alcance de proyectos físicos/planeamiento. Así se contabilizan los 51 documentos observados: 47 retenidos y cuatro excluidos.

Un registro representa un instrumento concreto documentado; no cada anuncio, ni una supuesta licencia. La carpeta de parcela 5.4 ED2 solo contiene anuncio de participación y su cobertura documental es parcial. Los títulos de carpeta que dicen «aprobación» se conservan como texto de fuente, sin inferir una fase estructurada. La agrupación respeta la clasificación municipal: por ejemplo, Co-housing incluye un decreto cuyo título menciona Camping Sindical; no se corrige ni reasigna por conjetura. Dos anuncios Co-housing con igual título y distinto UUID se retienen ambos.

## Navegación y límites

La sede usa Wicket. El adaptador lee la URL del argumento literal de `wicketAjaxGet` y hace un GET normal, sin ejecutar JavaScript. Las carpetas redirigen a URL pública estable `/transparency/<uuid>/`. No se fijan tokens de sesión en código. Los documentos usan `/preview-document/<uuid>`; no se guardan tokens temporales PDF en los registros.

La primera página de 7.1 contiene diez entradas, y «Mostrar más» devuelve cinco entradas adicionales como componentes HTML dentro de XML. Calle Lepanto también exige «Mostrar más» para obtener los tres últimos de sus trece documentos. Se recorre hasta agotar la continuación y se verifica el número de documentos anunciado en cada carpeta. Páginas vacías/repetidas, enlaces ajenos a la sede, carpetas nuevas de tipo no revisado, documentos sueltos desconocidos, subcarpetas no soportadas y discrepancias de recuento producen error antes de sustituir el JSONL. El límite de 100 páginas produce error, nunca truncado silencioso. `update_proyectos` renueva la instantánea completa: no existe cursor temporal fiable verificado.

No se extraen fechas: el título de un anuncio BOP no equivale a fecha de acuerdo, y la «Fecha de creación» de la previsualización es metadato documental, no fecha de publicación o aprobación. No se afirma vigencia actual, ejecución material ni concesión de licencia. No se inventan coordenadas. `publication_ready=false`, `geometry_status=unavailable`; programación, licencias y jitter desactivados.

## Pruebas y evidencia local

Comando ejecutado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_punta_umbria -v` — **8 pruebas correctas**. Cubren HTML/XML, continuación y procedencia estable, páginas repetidas, vacíos, dominio de fuente, agrupación/aislamiento de documentos, exclusión de servicios de playa, ausencia de fechas/coordenadas inferidas, conservación de salida previa ante cobertura incompleta, rechazo de material nuevo no revisado y manifest/licencias desactivadas.

La ejecución real instanció `PuntaUmbriaAyuntamientoAdapter` con el manifest y llamó únicamente a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando `evidence_dir` para capturar las respuestas. `evidence/validation.json` contiene recuentos, URLs, limitaciones y capturas `live-*.html` (las respuestas incrementales son XML aunque lleven esa extensión). La evidencia es local y no forma parte de los cuatro archivos fuente.

Muestra documental verificada: https://umbria.sedelectronica.es/preview-document/682bcedd-32e6-4cbf-8794-28185d5a38ae (Estudio de Detalle de Bellavista). La previsualización contiene iframe PDF; se descargó el documento completo con HTTP 200, `application/pdf`, firma `%PDF-`, 964574 bytes y SHA-256 `28cbb1d87c12655b64904005076db8af6b8e921f67c7d5ebbebe4f017faf53e3`. Capturas: `evidence/document-preview.html`, `evidence/bellavista.pdf` y `evidence/document-validation.json`. Esta comprobación no implica inspección o descarga de todos los PDF del inventario.
