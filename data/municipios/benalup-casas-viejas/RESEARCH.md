# Benalup-Casas Viejas — INE 11901, Cádiz, Andalucía

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único del municipio, limitado al inventario documental de planeamiento publicado por el ayuntamiento.

## Inventario oficial actual

La portada municipal https://www.benalupcasasviejas.es/es/ expone dos enlaces específicos en el menú Ayuntamiento, repetidos en la navegación móvil. El parser deduplica esas repeticiones y exige un único destino oficial por instrumento:

- **PGOU vigente**: https://www.benalupcasasviejas.es/images/documentos/PGOU%20VIGENTE.pdf . Un registro de documento de planeamiento, conservando literalmente la denominación municipal sin afirmar vigencia jurídica ni aprobación. HTTP 200, application/pdf, 19.844.054 bytes. Las primeras cuatro páginas no proporcionaron texto extraíble mediante pdftotext; no se realizó OCR.
- **AVANCE PBOM**: https://www.benalupcasasviejas.es/es/ayuntamiento/avance-pbom . Categoría Phoca Download titulada PBOM, con dos documentos agrupados en un solo instrumento: [Documento urbanístico](https://www.benalupcasasviejas.es/es/ayuntamiento/avance-pbom?download=4:documento-urbanistico), HTTP 200, application/pdf, 18.220.023 bytes, y [Documento inicial estratégico](https://www.benalupcasasviejas.es/es/ayuntamiento/avance-pbom?download=5:documento-inicial-estrategico), HTTP 200, application/pdf, 7.942.714 bytes. La memoria del primer PDF identifica PBOM, Benalup–Casas Viejas y «documento de avance»; describe su contenido urbanístico y la evaluación ambiental simultánea. La extracción de texto del segundo PDF presenta codificación defectuosa; se retiene su título del catálogo y el enlace, sin derivar datos administrativos de ese texto.

El catálogo observado contiene dos entradas con límite seleccionado de 20 y ningún enlace a otra página. El adaptador recorre todos los enlaces de paginación expuestos, deduplica documentos y falla si encuentra una página llena sin navegación, un destino ajeno, una categoría vacía o una estructura inesperada. Su límite de seguridad de 100 páginas provoca error explícito y no escritura parcial. Los adjuntos con títulos desconocidos exigen revisar la agrupación: no se convierten automáticamente formularios nuevos en documentos de un plan.

La vista superior `https://www.benalupcasasviejas.es/es/ayuntamiento/avance-pbom?view=categories` también se consultó: enumera Deportes, Ordenanzas, PBOM, Guías, Horarios y Documentos; no constituye un inventario de expedientes urbanísticos. No se extraen esos enlaces como proyectos.

## Alcance y semántica

Resultado vivo: **2 registros, 3 enlaces documentales, 1 página de catálogo PBOM**. El PGOU rotulado y el avance PBOM se mantienen separados; los dos adjuntos PBOM pertenecen a un solo instrumento. Cada adjunto conserva título, URL y página de procedencia. Los identificadores representan estos dos instrumentos locales, no expedientes oficiales inventados.

Cobertura parcial: inventario actual de estos dos instrumentos, sin histórico de modificaciones, sin registro completo de obras físicas, sin noticias ni anuncios de contratación convertidos en actuaciones. La sede electrónica encontrada en la búsqueda ofrece trámites de obras: no se verificó un registro público de licencias concedidas. `licencias.enabled=false`; las funciones de licencias devuelven cero registros.

El tooltip de ambos archivos PBOM muestra «30 Enero 2026», una fecha del CMS sin significado administrativo probado. No se usa como fecha de publicación oficial, acuerdo o aprobación: `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son null. No se infiere aprobación definitiva del avance. No hay coordenadas ni geometría verificadas; `publication_ready=false`, `schedule.enabled=false` y `geocode.jitter_missing=false`.

Como contraste de investigación se encontró la publicación oficial de las Normas Subsidiarias en https://www.juntadeandalucia.es/boja/2020/188/64 . No se mezcla su fecha de resolución, publicación o aprobación histórica con el PDF rotulado PGOU: no se demostró identidad documental. Esa publicación no se añade como tercer instrumento duplicado.

## Verificación y evidencia local

Se inspeccionaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro dinámico y los ejemplos Chipiona y Manlleu. No se modificó código compartido ni dependencias.

Runtime empleado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_benalup_casas_viejas -v`: **7 correctas**. Cubren agrupación documental y procedencia, fechas y geometría vacías, navegación de varias páginas mediante respuestas simuladas, detección de truncamiento, rechazo de fuentes vacías/ajenas, formulario en posición de adjunto y carga del manifest.

La ejecución real cargó el manifest con `load_manifest`, resolvió el adaptador con `load_portal_adapter` y llamó a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, sin pipeline de publicación. La política compartida identifica el PGOU como documento y mantiene el PBOM pendiente por falta de referencia de expediente; ninguno es elegible como actividad ni licencia concedida. Se conserva esa clasificación sin falsear identidades para eludirla.

Evidencia local, no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (live_records, source_urls, limitaciones, páginas recorridas, verificaciones HTTP y pruebas), `evidence/tests.txt`, capturas HTML, prefijos PDF capturados durante la ejecución y tres PDF completos descargados durante la investigación con sus extracciones de las primeras páginas. El adaptador comprueba las firmas PDF en cada ejecución; no analiza automáticamente el contenido completo de los PDF.
