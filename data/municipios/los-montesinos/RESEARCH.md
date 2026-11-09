# Los Montesinos — INE 03903, Alicante

Investigación y extracción real: 9 de noviembre de 2026. Runtime:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

La página municipal de [Urbanismo](https://www.losmontesinos.es/el-ayuntamiento/areas/urbanismo/)
enlaza expresamente el [inventario de planeamiento](https://www.losmontesinos.es/el-ayuntamiento/areas/urbanismo/planeamiento-urbanistico-de-los-montesinos/).
Ambas respondieron HTTP 200. El inventario tiene once documentos distintos:
seis PDF y cinco planos TIFF, sin paginación observada. El primer PDF aparece
en dos enlaces consecutivos, con el texto separado como «N» y «ORMAS…»;
se normaliza la URL relativa y se deduplica antes de agrupar.

Los seis PDF se descargaron completos (HTTP 200, firma `%PDF-`) y se revisaron
mediante `pdftotext -layout`, sin instalar herramientas. Son documentos reales
de instrumentos de planeamiento, no formularios ni anuncios de contratación:

| Instrumento representado | Documentación conservada |
| --- | --- |
| Normas Subsidiarias de Los Montesinos | Partes 1 y 2, un único registro |
| Plan Parcial Loma de las Lagunas | Texto refundido de normas urbanísticas |
| Plan Parcial RES-1 | Texto refundido de normas urbanísticas |
| Plan Parcial Ciudad Jardín (RES-2) | Texto refundido de normas urbanísticas |
| Plan Parcial Polígono Industrial Levante IND-2 | Ordenanzas reguladoras; el inventario lo llama Levante II |

El scraper conserva los títulos de inventario para los sectores, las URL
individuales y la página de procedencia de cada documento. El resultado son
**cinco instrumentos**, no seis proyectos independientes. Los cinco TIFF de
clasificación norte/sur, sistemas generales, ordenación/edificación y unidades
de ejecución/alineaciones no identifican explícitamente un instrumento en el
listado: se conservan en `unassigned_documents` del informe, sin inventar esa
relación ni convertir cada plano en proyecto. Los TIFF no se descargan ni se
vectorizan. No se presentan como geometrías verificadas.

## Inventarios alternativos y límites

Urbanismo también enlaza `https://www.ayuntamientolosmontesinos.es/` como
«Web Plan General». El intento real falló por resolución DNS; queda fuera de
la extracción. La página de Urbanismo contiene noticias con cuatro páginas,
entre ellas obras del cementerio, subvenciones, bandos y actividades. Esa
hemeroteca no forma parte de la fuente seleccionada: no se extrae su primera
página como si fuera un histórico completo. Tampoco se han tratado trámites,
formularios o noticias como concesiones de licencia. La cobertura es parcial
respecto al municipio: solo el inventario documental de planeamiento indicado.

El adaptador recorre enlaces de paginación reconocidos dentro del inventario,
deduplica páginas y documentos y agrupa partes por identidad del instrumento.
Una paginación hacia otro origen/ruta, documentos desconocidos, un inventario
vacío, un PDF inaccesible o sin firma PDF provocan error antes de escribir
resultados. El límite de seguridad de cien páginas falla explícitamente en vez
de devolver un subconjunto. No se establecen fechas por los directorios
`2018/07` de WordPress. Los meses/años de portada (2002/2003 en varios PDF)
son referencias documentales, no fechas de aprobación ni publicación.
Todos los campos de fechas, fase y coordenadas quedan nulos; no se afirma
vigencia jurídica. `publication_ready=false`, licencias, programación y
jitter desactivados.

## Validación reproducible y evidencia local

`python -m unittest municipio.test_los_montesinos -v`: ocho tests correctos.
Cubren agrupación y deduplicación, separación entre instrumentos, fechas y
geometrías ausentes, rechazo de fuentes incorrectas/desconocidas, exclusión
de enlaces fuera del inventario, paginación completa con ciclos y ausencia
de salida parcial si falla un documento. Se prueba también carga del manifest
y del adaptador por el registro compartido y licencias desactivadas.

Se ejecutó `load_portal_adapter(load_manifest('los-montesinos')).backfill_proyectos`
contra la web real, habilitando únicamente `capture_dir` local. Resultado:
cinco registros y seis PDF verificados. Evidencia no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML y PDF
bajo `evidence/live/`, capturas de descubrimiento y textos extraídos bajo
`evidence/`. El informe incluye `live_records`, `source_urls`, limitaciones,
los cinco enlaces cartográficos no atribuidos y resultado de la política de
entidades aplicada por el registro compartido. No se ejecutaron operaciones
de publicación, base de datos ni geocodificación.
