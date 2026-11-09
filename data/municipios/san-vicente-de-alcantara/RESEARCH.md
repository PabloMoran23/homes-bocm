# San Vicente de Alcántara — INE 06123

Provincia: Badajoz. Comunidad autónoma: Extremadura. Revisión: 2026-11-09.

## Descubrimiento y fuentes oficiales

La web del Ayuntamiento, https://sanvicentedealcantara.es/, enlaza en su
navegación «Plan General Municipal» a:
https://sanvicentedealcantara.es/plantilla.php?enlace=plangeneral

Este inventario municipal responde HTTP 200 y publica normas urbanísticas,
memoria informativa, memoria justificativa y planos del PGM. Se extraen las
40 filas documentales del bloque principal `.contenidop`, sin recoger los
PDF de los banners laterales. Los enlaces se descubren en cada ejecución;
no se mantiene una lista fija de documentos. Se agrupan en **un único
instrumento**, con ID estable `san-vicente-de-alcantara-pgm`. Las hojas de
planos y las memorias no son proyectos independientes. Cada documento conserva
título, descripción (incluida referencia de hoja), URL, fuente y fecha de alta.

También se inspeccionaron directamente:

- https://sanvicentedealcantara.es/plantilla.php?enlace=Urbanismo — contacto del arquitecto técnico, sin inventario de expedientes.
- https://sanvicentedealcantara.es/plantilla.php?enlace=Obras — encabezado «AREA DE OBRAS PÚBLICAS», sin proyectos detallados.

La búsqueda oficial de planeamiento regional devuelve, entre otros:
https://sitex.juntaex.es/SITEX/planeamiento?ptofigura=37204 (PGM) y
https://sitex.juntaex.es/SITEX/planeamiento?ptofigura=40797 (modificación 003).
El DOE también publica la modificación 003:
https://doe.juntaex.es/otrosFormatos/html.php?anio=2025&doe=1470o&xml=2025081252
Estas fuentes prueban que hay modificaciones posteriores fuera del alcance del
inventario municipal analizado. No se incorporan sus fechas al registro municipal:
la ficha regional de la modificación 003 y el anuncio del DOE presentan fechas
diferentes para la aprobación definitiva, que exigirían conciliación documental.
No se usa una búsqueda web como supuesto inventario exhaustivo de modificaciones.

## Semántica y límites de cobertura

Cobertura **parcial**, restringida al PGM documental publicado actualmente en esa
página municipal. No pretende cubrir todos los instrumentos históricos, sus
modificaciones, obras públicas ni expedientes de licencia. La existencia del
inventario acredita el instrumento y sus documentos; no se infiere su fase
administrativa ni una aprobación de la mera presencia de PDFs.

«Fecha de Alta» se almacena como `documentos[].fecha_alta`. Las fechas observadas
abarcan 2021-04-18 a 2021-08-13. No son necesariamente fechas de publicación
oficial, acuerdos ni aprobaciones. `fecha`, `fecha_publicacion`, `fecha_acuerdo`
y `fecha_aprob` quedan nulas a nivel del instrumento. No se interpreta el nombre
numérico de los PDFs como fecha. No se generan licencias a partir de formularios,
contrataciones o noticias. Los métodos de licencias escriben cero registros y
están deshabilitados en manifest.

La página examinada no tiene paginación en su inventario. Se recorren todas sus
filas sin límite de registros. Si aparecen controles de paginación, formularios,
enlaces siguiente/anterior, números de página o parámetros de página reconocidos,
el adaptador falla explícitamente: requiere ampliar el recorrido antes de aceptar
una salida. También falla ante inventario ausente, filas malformadas, PDFs fuera de
las filas reconocidas, destinos inesperados o falta de normas/memorias esenciales.
La actualización vuelve a leer la instantánea completa; no simula un incremental.

## Geometría

`geometry_status: unavailable`. Hay planos PDF (clasificación, ordenación, redes,
catálogo), pero no se ha verificado geometría vectorial asociable al instrumento.
No se vectorizan los PDFs ni se inventan coordenadas o CRS. Latitud, longitud y
geometría son nulas. `publication_ready: false`, ejecución programada desactivada
y `geocode.jitter_missing: false`.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`python -m unittest municipio.test_san_vicente_de_alcantara -v` — **5 pasan**.
Cubren agrupación y deduplicación por URL, fechas de alta sin convertirlas en
aprobaciones, metadatos de planos, exclusión de banners, rechazo de cambios de
estructura/paginación/URLs ajenas y contrato backfill/update mediante el cargador
real del manifest.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 40 documentos**.
Se aplica también la política compartida del cargador; su clasificación resulta
`unknown`, conservada sin forzar una categoría ni modificar código compartido.
El acceso HTML tiene timeout de 35 segundos y comprueba los errores HTTP.

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: salida real del adaptador.
- `evidence/validation.json`: recuento, fuentes, límites y validación.
- `evidence/plangeneral.html`: HTML exacto capturado por la extracción real.
- `evidence/Urbanismo.html` y `evidence/Obras.html`: páginas auxiliares revisadas.
- `evidence/normas-urbanisticas.pdf`: PDF municipal HTTP 200, tipo application/pdf,
  1.620.270 bytes, cabecera `%PDF-1.6`, descargado desde
  https://sanvicentedealcantara.es/documentos/20210421144522.pdf.

Se conserva el enlace de los 40 documentos; solo el PDF de normas se descargó
para verificar el documento, sin afirmar que se hayan descargado o validado
todos los planos. No se ha ejecutado publicación, base de datos ni despliegue.
