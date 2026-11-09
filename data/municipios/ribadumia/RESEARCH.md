# Ribadumia — INE 36046, Pontevedra, Galicia

## Fuentes oficiales y descubrimiento

Revisión y extracción en vivo: 2026-11-09. La página municipal de
[Obras, Servizos e Urbanismo](https://www.ribadumia.org/obras-servizos-urbanismo.aspx)
enlaza la plataforma municipal y, en su navegación de transparencia, «Información
pública» (`https://omeuconcello.ribadumia.org/enlace/seccion/94`). El inventario
canónico consultado es:

https://omeuconcello.ribadumia.org/seccion/94/informacion-publica

HTTP 200, sin autenticación. No se usan noticias individuales como semillas.
Se revisó también el enlace oficial de la sede electrónica
https://ribadumia.sedelectronica.gal/info.0 como alternativa de descubrimiento;
no se integra ese tablón ni se afirma cobertura de sus expedientes.
La página de servicios remite a formularios: no es un registro de concesiones.

## Cobertura comprobada

Inventario de **51 entradas**, **3 páginas** (20, 20, 11). El extractor lee el
selector de páginas, tamaño y total, envía los campos ocultos WebForms de cada
respuesta con el evento público `lbSiguiente` y verifica página seleccionada,
conteos y ausencia de entradas repetidas. Cambios de inventario durante el recorrido,
respuestas repetidas, pérdida de marcado, documentos ausentes o superación del límite
de seguridad de 100 páginas causan error antes de sustituir la salida. No hay corte
silencioso. La actualización vuelve a recorrer la instantánea completa, sin usar
la fecha publicada como cursor.

Se extraen únicamente modificaciones numeradas del PXOM y planes de accesibilidad
del núcleo urbano de Barrantes con edición identificada y documentos adjuntos.
Resultado real:

- **Modificación puntual número 5 del PXOM**: 18 documentos de cuatro entradas
  municipales (planos de ordenación, planos de información, memoria justificativa,
  anuncio y documento ambiental). Se agrupan por número de modificación,
  conservando títulos originales —incluida la errata «MODIFICACACIÓN»—,
  procedencia de cada entrada, fechas y enlaces íntegros de los adjuntos.
- **Plan de accesibilidade do núcleo urbano de Barrantes, Ribadumia (2025)**:
  memoria y planos, dos documentos. La memoria contiene un plan de actuación
  sobre el núcleo urbano; no es una convocatoria ni un formulario.

Total: **2 instrumentos, 20 documentos**. Todos los enlaces adjuntos se descargaron
con HTTP satisfactorio y firma `%PDF-`; están capturados con tamaño y SHA-256 en
`evidence/validation.json`. No se crean veinte proyectos independientes.

Quedan fuera ordenanzas, subvenciones, anuncios de contratación, solicitudes de
licencias o autorizaciones, informes generales, renumeración de inmuebles y
planes ambientales regionales o de incendios. El anuncio de aparcamientos de 2022
con enlace abreviado tampoco forma parte de esta cobertura. Esto es una selección
explícita de instrumentos documentados, no el histórico completo de urbanismo ni
el inventario completo de obras físicas del municipio.

## Fechas y estado

El plan de accesibilidad se publica en el inventario el **2025-11-03**. Su memoria
está firmada el 2025-10-31: la firma no demuestra aprobación y no se usa como tal.
Las cuatro entradas de la modificación se publican el **2024-06-14**.

El PDF «Anuncio de exposición.pdf» reproduce DOG núm. 111, de **2024-06-10**:
identifica el acuerdo de aprobación inicial del Pleno del **2024-05-02**, destinado
a ampliación y regularización del suelo industrial de Cabanelas, y la firma del
anuncio del **2024-05-09**. Son cuatro fechas con significados distintos. El parser
HTML solo extrae la publicación municipal; los campos `fecha_acuerdo` y
`fecha_aprob` quedan nulos porque el adaptador no interpreta el texto de los PDF.
El anuncio íntegro sigue enlazado y capturado. La existencia de este documento
histórico no prueba el estado jurídico actual. No se asigna una fase actual.
Si un instrumento reúne publicaciones de fechas diferentes, se conservan todas
las fechas por publicación y documento; la fecha única del instrumento queda nula.

## Geometría

`geometry_status: unavailable`. El portal enlaza el Punto de Información Catastral
y ofrece planos PDF de ámbito, topografía, servicios y ordenación. No se verificó
una capa vectorial municipal vinculada por identificador a estos instrumentos.
No se vectorizan planos, no se consultan datos catastrales particulares y no se
asignan centroides, CRS ni coordenadas inventadas. `publication_ready: false`.

## Implementación y validación local

Manifest con identidad INE/provincia exacta, proyectos habilitados,
`schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`. Los métodos de licencias escriben salida vacía
con estado `disabled`. Sin cambios de dependencias ni código compartido.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_ribadumia -v`, **4 pasan**:
agrupación, títulos de documentos, exclusiones, semántica de fechas, rechazo de
páginas incompletas/documentos ausentes, recorrido WebForms con estado renovado,
rechazo de página repetida sin sustituir salida, licencias y carga del manifest.

La extracción real se ejecutó con
`RibadumiaAyuntamientoAdapter('ribadumia', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Salida y validación en `evidence/proyectos.jsonl` y `evidence/validation.json`.
Capturas HTML de las tres páginas, los 20 PDF y texto de comprobación del anuncio
y primeras páginas de la memoria se conservan en `evidence/`. Evidencias locales,
fuera de los cuatro archivos fuente. Sin publicación ni acceso a bases de datos.
