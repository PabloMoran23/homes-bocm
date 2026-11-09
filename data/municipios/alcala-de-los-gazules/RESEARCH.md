# Alcalá de los Gazules — Cádiz — INE 11001

Investigación y extracción real: 9 de noviembre de 2026.

## Fuente oficial y alcance

El inventario municipal accesible está en:
https://www.alcaladelosgazules.es/index.php/urbanismo/pgou

La página Phoca Download identifica expresamente el «AVANCE Y DOCUMENTO INICIAL ESTRATEGICO PGOU ALCALA DE LOS GAZULES. FEBRERO 2020». Contiene una portada y ocho categorías de volúmenes: presentación, memoria, planos de información, planos de ordenación, documento inicial estratégico, valoración de impacto en salud, patrimonio y estudio acústico. Se extrae **un instrumento real con 25 documentos**, no 25 proyectos independientes. Cada documento conserva título, identificador de descarga, URL, volumen y página de procedencia. El identificador del instrumento depende de la URL del inventario y permanece estable al cambiar el orden de documentos.

El inventario se consulta con `?limit=0` (opción All). El parser exige que esa opción figure seleccionada y rechaza enlaces de paginación restantes. Se visitan todas las categorías enlazadas, se compara su título y el número de documentos con el recuento del índice; cualquier discrepancia, categoría anidada inesperada, duplicación entre volúmenes o cambio de instrumento provoca error antes de escribir la salida. En la ejecución real los recuentos fueron: VI=1, V=1, IV=1, III=1, IIB=16, IIA=2, I=1, 0=1, más la portada. El inventario raíz y todos los volúmenes respondieron correctamente.

También se localizaron la sede electrónica oficial https://alcaladelosgazules.sedelectronica.es/info.0 y publicaciones históricas de planeamiento en BOJA, por ejemplo https://www.juntadeandalucia.es/boja/2018/223/71 (anuncio relativo a aprobación inicial de 2018). No se mezclan estos antecedentes con el avance de 2020 ni se presume que describan el mismo estado administrativo. El scraper cubre únicamente el inventario municipal identificado, no todas las modificaciones históricas, obras públicas o expedientes municipales. No se verificó un inventario público de licencias concedidas; los formularios y los anuncios de contratación no se convierten en licencias o proyectos.

## Semántica y límites

`fase` procede del título documental: avance y documento inicial estratégico. «Febrero 2020» se conserva como `periodo_documentacion`, sin convertirlo en fecha exacta de acuerdo, aprobación o publicación. Los tooltips del CMS muestran fechas de archivo de octubre/noviembre de 2025; no acreditan acuerdos ni se emplean como fechas de aprobación. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. No se afirma aprobación definitiva ni vigencia legal actual. No se inventan coordenadas o geometrías; `geometry_status: unavailable` y `publication_ready: false`.

Las páginas HTML son el origen de los metadatos extraídos. Se comprobó además la descarga municipal de PORTADA (`?download=7:portada`): HTTP 200, `application/pdf` y firma `%PDF-`. Se conservan solo los primeros 1024 bytes como muestra; no se han descargado e interpretado todos los PDF ni se han extraído geometrías de los planos.

El manifest desactiva programación automática, jitter y licencias. Las actualizaciones regeneran la instantánea completa, sin filtrar documentos por fechas del CMS. Los fallos de extracción preservan la salida anterior. No hay cambios en fuentes compartidas ni dependencias.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_alcala_de_los_gazules -v`: **8 pruebas correctas**. Cubren agrupación y procedencia, metadatos desconocidos, recuentos incompletos, paginación, enlaces externos, cambios de instrumento, duplicados, conservación de salida ante errores y licencias desactivadas.

Extracción real mediante `load_manifest('alcala-de-los-gazules')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `portal.config['capture_dir']='evidence/source-captures'` solo en memoria. Resultado: **1 registro, 25 documentos, 9 páginas de inventario**. La política compartida anota el registro como entidad desconocida; no impide la extracción ni permite publicación automática.

Evidencia local, excluida del commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (recuento, URLs, límites, muestra PDF y resultado del adaptador), `evidence/source-captures/*.html` y `evidence/portada-first-1024.bin`. No se han usado bases de datos, credenciales ni herramientas de publicación.
