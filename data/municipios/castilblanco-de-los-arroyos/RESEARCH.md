# Castilblanco de los Arroyos — INE 41027, Sevilla, Andalucía

Investigación y extracción real: 9 de noviembre de 2026. Un único adaptador municipal, con cobertura documental parcial de planeamiento. No se trata del municipio de Castilblanco (Badajoz).

## Descubrimiento y fuentes oficiales actuales

La sección municipal https://www.castilblancodelosarroyos.es/es/obrasyurbanismo/ enlaza el nuevo PBOM, su avance y la adaptación parcial a la LOUA. Las páginas puente de avance y adaptación enlazan el portal municipal de transparencia (se emplea HTTPS en lugar de los enlaces HTTP publicados):

- https://www.castilblancodelosarroyos.es/es/obrasyurbanismo/avance-pan-basico-de-ordenacion-municipal/
- https://www.castilblancodelosarroyos.es/es/obrasyurbanismo/Adaptacion-Parcial-a-la-Loua-de-Normas-Subisdiarias/

El adaptador lee tres inventarios vivos en cada ejecución:

1. https://www.castilblancodelosarroyos.es/es/obrasyurbanismo/nuevo-plan-basico-de-ordenacion-municipal/ — tabla con la consulta pública previa del PBOM: un PDF.
2. https://transparencia.castilblancodelosarroyos.es/es/transparencia/indicadores-de-transparencia/indicador/Avance-del-Plan-Basico-de-Ordenacion-Municipal./ — artículo de transparencia con 18 documentos: memorias, resumen, planos de información y ordenación, catálogo, documento inicial estratégico, resolución del avance y publicación del avance en BOP.
3. https://transparencia.castilblancodelosarroyos.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00065/ — galerías de adaptación parcial LOUA y modificación nº1 para ampliación del cementerio.

Resultado real: **3 instrumentos, 26 enlaces documentales únicos**. Un registro PBOM agrupa consulta previa y avance (19 documentos); otro agrupa adaptación LOUA (6 documentos únicos); otro corresponde a la modificación nº1 del PGOU-AdP para ampliación del cementerio (1 documento). Se conserva título, URL absoluta y página de procedencia de cada documento. El plano de clasificación repetido en tabla y galería se deduplica. Los registros se generan a partir del HTML descargado; no se precargan registros de ejemplo.

La galería de adaptación incluye un boletín denominado «BOP 271 23_11_2011 TASAS VEHICULOS_PRECIOS PISCINA MCPAL». Se excluye expresamente por materia ajena al planeamiento, aunque esté publicado dentro de esa galería. Modelos y solicitudes tampoco son licencias concedidas.

## Cobertura y semántica

Cobertura parcial de documentos publicados, sin pretensión de registro exhaustivo histórico. El enlace al antiguo PGOU provisional no se sigue y no se confunde con la adaptación LOUA o el PBOM. No se extrae el listado de noticias de obras ni contratación. Una noticia sobre un plan, el encargo de su redacción o un anuncio de licitación no acredita la aprobación del instrumento ni una licencia.

No se infiere vigencia, ejecución ni fase jurídica por los nombres de documentos. La resolución del **avance** del PBOM no significa aprobación definitiva del PBOM. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas: no se interpretan fechas en nombres de archivos ni fechas del CMS como acuerdos. No se han leído íntegramente las resoluciones para extraer fechas. Sin coordenadas o geometrías verificadas; los mapas se conservan como documentos sin inventar ubicación. `publication_ready=false` y `geometry_status=unavailable`.

Los tres inventarios observados son páginas documentales finitas sin paginación visible. La tabla OpenCMS declara `resultSize: 6` y contiene seis filas antes de excluir el boletín de tasas. Se inspeccionan todas las galerías y bloques, sin limitar resultados. El adaptador rechaza paginación nueva o totales del colector superiores a filas servidas; no devuelve una primera página silenciosamente. También rechaza fuentes redirigidas, ausencia de contenedores/documentos, galerías desconocidas y enlaces PDF fuera de los dominios oficiales esperados. Una actualización sustituye el inventario completo y no acumula duplicados. Los errores de parseo ocurren antes de escribir la salida.

Licencias desactivadas al no haberse verificado un registro público de concesiones. Manifest: `codigo_ine: '41027'`, `provincia: Sevilla`, `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

## Validación y evidencias locales

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_castilblanco_de_los_arroyos -v`: seis pruebas correctas sobre agrupación, procedencia, separación entre instrumentos, rechazo de noticias/formularios, paginación/colectores incompletos, cambios de galerías, dominios documentales, actualización de snapshot y carga dinámica del adaptador desde el manifest.

Ejecución real: `CastilblancoDeLosArroyosAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`. Se obtuvieron tres registros. `evidence/validation.json` incluye `live_records`, `source_urls`, conteos documentales, limitaciones y comprobaciones HTTP. `consulta.html`, `avance.html` y `pgou.html` son capturas de las respuestas de esa ejecución. `discovery-*.html` documentan la navegación de investigación.

Se verificó una muestra por instrumento (resolución del avance PBOM, aprobación de adaptación y aprobación de modificación del cementerio): HTTP 200, `application/pdf` y firma `%PDF-`. Se guardaron únicamente los primeros 1024 bytes de cada PDF en archivos `*-sample.pdf.part`; no son PDFs completos ni una validación de todo su contenido. No se descargaron masivamente los planos. Evidencias locales sin incluir en los cuatro archivos fuente entregables. Sin base de datos, publicación, despliegue ni cambios compartidos.
