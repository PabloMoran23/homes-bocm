# Rianxo — INE 15072, A Coruña, Galicia

Revisión y extracción real: 2026-11-07. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

La sección municipal https://concelloderianxo.gal/urbanismo enlaza el PXOM desde
su anuncio de exposición y enlaza también el inventario autonómico SIOTUGA con
`idconcello=15072`. Se inspeccionó esta sección, pero no se utiliza su blog
paginado como inventario exhaustivo ni se convierten sus noticias en proyectos.

Fuente principal: https://concelloderianxo.gal/pxom (HTTP 200).
Es un inventario documental específico del Plan Xeral de Ordenación de Rianxo,
no una noticia aislada ni un formulario. Su sección de documentos anteriores
permite descubrir https://concelloderianxo.gal/pxom-aprobacion-inicial (HTTP 200).
Ambas páginas se consultan en cada extracción; la segunda no es opcional.

Resultado observado: **1 instrumento con 31 enlaces documentales únicos**:
6 de la fase provisional (normativa, cuatro planos y ZIP completo) y 25 de la
fase inicial (anuncio, resumen, memorias, normativa, catálogo, núcleos, informe
ambiental y planos). Los enlaces de planos A3 sin texto visible también se
retienen, con título de respaldo tomado del nombre de fichero publicado.
Cada documento conserva URL original, página de procedencia y fase documental.
Los parámetros de descarga se conservan; se excluyen de la clave de deduplicación.
No se crean proyectos separados por documento, parroquia, escala o fase.

## Semántica y cobertura parcial

El acuerdo provisional del Pleno se fecha explícitamente en la página municipal:
**2023-05-11**. Se extrae como `fecha_acuerdo`; no se asigna fecha genérica,
fecha de publicación ni aprobación definitiva. La indicación «maio 2014» del
paquete inicial no se convierte en un día de acuerdo. El título del anuncio DOGA
identifica una publicación de 2014, pero esa fecha tampoco se atribuye al PXOM.

La fase provisional describe el documento ofrecido por el Ayuntamiento y su
remisión a la Xunta, no una certificación de su situación jurídica actual.
No se ha verificado aquí una aprobación definitiva ni se afirma que el PXOM sea
el planeamiento vigente. La cobertura se limita a este instrumento y sus fases
documentales enlazadas; no abarca todas las obras, planes ni actuaciones del
municipio. SIOTUGA se identifica como fuente adicional, sin extraer su inventario.
No se usa contratación, formularios o anuncios genéricos como licencias concedidas.
Los métodos de licencias producen un fichero vacío y declaran su deshabilitación.

No hay paginación en las dos páginas documentales inspeccionadas. El parser
rechaza controles de continuación si aparecen, en lugar de aceptar una extracción
parcial. También falla si desaparece el artículo esperado, sus adjuntos, el
texto del acuerdo o el enlace a la fase inicial; cualquier fallo al obtener la
fase histórica evita reemplazar la salida anterior. La actualización hace una
lectura completa de este pequeño inventario, sin simular un incremental por fecha.

## Geometría y documentos

`geometry_status: unavailable`, `publication_ready: false`.
Los planos se retienen como documentos, sin vectorizarlos ni asignar coordenadas,
centroides municipales, CRS o desplazamientos artificiales. SIOTUGA es el visor
urbanístico enlazado por el portal; no se ha verificado una geometría vectorial
asociable a este expediente. El ZIP anunciado ocupa 556,6 MB y el conjunto inicial
contiene PDF de gran tamaño: se conservan todos sus enlaces sin descargarlos todos.
La disponibilidad individual de los 31 enlaces no está validada exhaustivamente.
Se descargó y comprobó la firma PDF de la normativa provisional como muestra;
su tamaño, hash y URL quedan registrados en la validación local.

## Validación reproducible y evidencias locales

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_rianxo -v`

Seis pruebas pasan: documentos y duplicados, agrupación de fases y fechas,
rechazo de paginación, cambios de estructura, fallo de fase histórica sin
sobrescribir salida, carga del manifest y licencias deshabilitadas.

La extracción real se ejecutó mediante
`RianxoAyuntamientoAdapter('rianxo', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas
HTML de Urbanismo y ambas páginas del PXOM, y `evidence/normativa-provisional.pdf`.
La validación registra `live_records: 1`, fuentes, recuento documental y limitaciones.
Las evidencias no forman parte de los cuatro archivos fuente entregados.

Manifest: `codigo_ine: '15072'`, provincia A Coruña, `schedule.enabled: false`,
`licencias.enabled: false`, `geocode.jitter_missing: false`. No se modifican fuentes
compartidas ni dependencias; no se ejecuta publicación ni sincronización externa.
