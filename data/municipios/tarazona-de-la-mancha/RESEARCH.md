# Tarazona de la Mancha — Albacete — INE 02073

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

La portada https://tarazonadelamancha.es/ enlaza el inventario
https://tarazonadelamancha.es/normativa-municipal/ y la sede
https://tarazonadelamancha.sedipualba.es/tablondeanuncios/ . No confundir con
Tarazona (Zaragoza), cuyo dominio tarazona.es no corresponde a este municipio.
La sede identifica al Ayuntamiento como P0207300E, Tarazona de la Mancha (02100).

El inventario municipal publica 16 referencias a PDF, 15 URL distintas, que se
agrupan en tres instrumentos documentales:

- Modificación puntual de la revisión NNSS de 1998: dos planos, clasificación
  del suelo y alineaciones/rasantes, publicados a título informativo.
- Modificación puntual de 1999: un plano informativo y el documento de revisión.
- Revisión de Normas Subsidiarias de Planeamiento, volumen IV: once PDF únicos
  de capítulos, partes e índice. Es cobertura documental parcial del instrumento.

Todos proceden del contenido de la página oficial, sin filas precargadas.
Se retienen URL originales HTTP, texto del enlace y rótulos del inventario.
El rótulo «Capítulo VIII. Parte III» enlaza el mismo archivo que «Capítulo III»;
se conserva como rótulo alternativo de ese documento, sin inventar otra URL.
El identificador de cada instrumento es estable e independiente del orden de
sus documentos. No se crea un proyecto por capítulo ni una licencia por formulario.

La página completa es estática, sin paginación observada. El adaptador rechaza
controles o enlaces de paginación, redirecciones inesperadas, documentos de otro
host, agrupaciones desconocidas y fuentes vacías; no recorta páginas en silencio.
La actualización relee este inventario completo y no modifica el estado recibido.

## Límites y semántica

Se extrae exclusivamente el inventario de Normativa Municipal. No se afirma
cobertura completa de todos los planes, obras o expedientes históricos.
El tablón actual muestra, entre otros anuncios ajenos a proyectos, «Resolución
Aprobación inicial del Proyecto de Obras Remodelación de Calle Gallegos y Calle
Bronce», expuesto desde 02/10/2026 hasta 30/11/2026. Es otra fuente y queda fuera
de esta implementación; sus fechas de exposición no prueban la fecha del acuerdo.
https://tarazonadelamancha.es/descargas/ solo ofrecía una ficha de terceros.
La sede ofrece trámites de solicitud urbanística; no se verificó un registro
público de licencias concedidas, por lo que licencias permanece desactivado.

No se interpretan los años de modificación como fechas completas de aprobación.
Tampoco las rutas uploads/2024/03 acreditan fecha de publicación ni acuerdo.
Fechas, fase y coordenadas quedan nulas. No se verifica vigencia jurídica ni se
interpreta el texto de los PDF. Los registros declaran publication_ready=false y
geometry_status=unavailable. Schedule y jitter están desactivados.

## Validación reproducible y evidencia local

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_tarazona_de_la_mancha -v`: **5 pruebas correctas**.
Cubren agrupación por instrumento, separación de modificaciones, retención de
rótulos contradictorios, fechas/coordenadas ausentes, rechazo de formularios,
fuentes cambiadas, paginación y documentos externos, además de escritura y carga
del manifest. No requieren red.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **3 registros**.
La anotación compartida de entidad clasifica los tres como unknown sin impedir
la extracción: son instrumentos de planeamiento, sin clasificar como promociones
residenciales verificadas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML íntegro del inventario y Descargas, y muestras
binarias de 1024 bytes de un PDF por instrumento. Las tres muestras responden
HTTP 200, application/pdf y firma %PDF- por HTTPS; se conserva también el enlace
HTTP original. Esta comprobación parcial no valida todos los documentos ni su
contenido jurídico. validation.json incluye URLs, limitaciones y resultados.
