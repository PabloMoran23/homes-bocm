# Huelma — INE 23044, Jaén

Consulta y ejecución real: 2026-11-09. Municipio Huelma, incluidos sus ámbitos
municipales; no confundir con Ventas de Huelma (Granada).

## Fuentes descubiertas

- Sede oficial: https://aytohuelma.sedelectronica.es/info.0 y
  https://aytohuelma.sedelectronica.es/transparency/ . Ofrece catálogo de
  trámites y una categoría de urbanismo con 25 elementos, mediante navegación
  dinámica Wicket. No se ha verificado un registro público de licencias
  concedidas. Los formularios no son concesiones y no se extraen.
- https://www.aytohuelma.es : la petición directa falló por certificado TLS;
  no se desactiva su verificación ni se usa como fuente de registros.
- Inventario oficial de Diputación Provincial de Jaén:
  https://www.dipujaen.es/diputacion/dipujaen/conoce-diputacion/areas-organismos-empresas/areaF/urbanismo/planeamiento/
  Enlaza un único «Desarrollo del Planeamiento de la Provincia». El adaptador
  descubre ese enlace en cada ejecución, sin fijar el nombre de la edición.
- Documento observado:
  https://www.dipujaen.es/export/sites/default/galerias/galeriaDescargas/diputacion/dipujaen/infraestructuras-municipales/Urbanismo/DESARROLLO-ACTUAL_OCTUBRE-25.pdf
  HTTP 200, firma PDF comprobada. Aunque el nombre contiene OCTUBRE-25, el
  pie del informe muestra 10/09/2026 13:17. Ninguno se trata como fecha de
  publicación de un instrumento. La sección municipal contiene actuaciones
  históricas y llega a acuerdos de 2025.

## Alcance y semántica

**29 registros**: estudios de detalle y proyectos de urbanización,
reparcelación y compensación con ámbito explícito. Ejemplos: Los Lavaderos,
Solana del Santo, Camino de Salceda, UE-12, terrenos de la Cooperativa San
Isidro Labrador, nuevo vial del Polígono Industrial Los Retiros y reparcelación
de las fincas 26, 27, 28, 41, 42 y 43 de su manzana C. Los dos últimos aparecen
bajo la figura NN.SS., pero su ámbito identifica expresamente los proyectos.
También se incluye la fila expresamente identificada como modificación de
proyecto de urbanización.

Es una cobertura parcial por categorías del inventario provincial disponible
actualmente, no de todos los instrumentos municipales ni de todas las obras.
No se extraen ordenanzas, estatutos, tasas, anuncios de contratación, noticias,
modificaciones generales de planeamiento ni formularios. No se afirma que los
instrumentos históricos estén vigentes o que sus obras estén ejecutadas.

Se lee el PDF completo con el ejecutable preinstalado `pdftotext -layout`.
Se exige una única cabecera «044. HUELMA» y el límite siguiente «045. HUESA»;
se recorre la sección completa, incluidas las páginas impresas 90 a 93.
No hay paginación web que truncar. La ausencia del enlace, límites o registros
provoca error. La cobertura seleccionada incluye todas sus filas explícitas;
no hay máximo de resultados ni muestra precargada.

Cada registro conserva `texto_fuente` con sus filas y continuaciones y
`documentos` con el enlace al inventario y la administración responsable.
Las filas de idéntico tipo y ámbito literal normalizado se agrupan; los
acuerdos sucesivos de una misma fila quedan juntos. No se deduce equivalencia
entre UA/UE ni entre las distintas denominaciones de Sector I / Los Retiros:
pueden existir referencias relacionadas cuya identidad requeriría cotejo de
expedientes. No se fusionan instrumentos distintos por compartir un ámbito.
La continuación «Reparcelacion finca nº40» sin figura propia se conserva en
el texto del estudio de Los Retiros, sin convertirla en otro proyecto ni
renombrar el estudio.

Las columnas del original distinguen «Fecha BOP» y «Fecha acuerdo». No se
normalizan: hay acuerdos multilínea, fechas ausentes y erratas evidentes
(como 25/3725). `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan
nulas; el texto conserva los datos tal como están para revisión. Tampoco se
asigna una fase actual a partir de acuerdos históricos. Sin coordenadas,
geometría ni geocodificación; `publication_ready=false`.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Sin instalación de paquetes ni cambios de dependencias. Requiere `pdftotext`
en PATH (disponible en este entorno).

- `python -m unittest municipio.test_huelma -v`: cuatro pruebas correctas,
  cubriendo límites municipales, saltos de página, agrupación de documentos,
  ámbitos multilínea, exclusión de ordenanzas, fechas nulas, descubrimiento
  del PDF actual y rechazo de enlaces ambiguos o externos.
- Ejecución real de `backfill_proyectos`, también mediante el cargador del
  manifest: 29 registros. Ningún acceso a base de datos ni publicación.
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/source.html`, `evidence/source.pdf`
  y `evidence/source.txt`, además de capturas de descubrimiento.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`. La fuente del portal es la Diputación; el valor
`proyectos.source=ayuntamiento` mantiene la ruta municipal admitida por el
esquema compartido y cada registro declara `source=diputacion`.
