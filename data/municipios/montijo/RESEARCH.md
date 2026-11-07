# Montijo — Badajoz — INE 06088

Investigación y extracción real: 7 de noviembre de 2026. Municipio español,
no el municipio homónimo portugués.

## Descubrimiento y fuentes oficiales

La [concejalía municipal de Urbanismo](https://ayuntamientomontijo.es/seguridad-ciudadana-y-urbanismo/)
enlaza expresamente «PLANEAMIENTO MUNICIPAL» a la antigua dirección
`http://sitex.gobex.es/SITEX/planeamiento`. La fuente regional actual accesible es
[SITEX, Junta de Extremadura](https://sitex.juntaex.es/SITEX/planeamiento).
La página municipal también contiene un paquete de reparación de la calle
Joaquín Costa; no se incorpora porque se ha elegido cubrir el inventario de
planeamiento, no mezclar documentación aislada de obras con ese registro.
No se ha verificado ningún inventario de licencias concedidas.

El selector de SITEX identifica Montijo con **id interno 123**, distinto del
código INE. La interfaz usa `Ajax.Updater` para solicitar, mediante POST,
`https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat`, con el
parámetro `municipioseleccionado=123`. Un GET sin el parámetro correcto no
representa el inventario municipal. El adaptador valida la opción seleccionada
y también el ámbito territorial y la referencia en cada ficha.

## Cobertura real

El árbol completo observado devuelve **89 instrumentos**: 50 «Vigente»,
1 «Vigente transitorio», 22 «No vigente» y 16 «En trámite». Incluye normas
subsidiarias y revisiones, modificaciones, planes parciales, estudios de detalle,
plan especial y proyecto de delimitación de suelo urbano. Estos son instrumentos
urbanísticos identificados, no formularios, licitaciones ni noticias.

Se recorren todos los nodos de ambas ramas del árbol (LSOTEX y anterior),
incluidos los descendientes. No hay paginación observada ni límite artificial
al número de fichas. La aparición de controles de paginación reconocibles
provoca un error para evitar aceptar una extracción parcial. Un cambio de
estructura, ficha ausente o municipio/referencia incorrectos también provoca
error; solo se reemplaza el JSONL después de completar todas las fichas.

Cada id de figura SITEX genera un único registro estable. La referencia oficial
se conserva como `referencia` y `expediente`. Todos los documentos de la ficha
se agrupan en `documentos`, deduplicados por URL, con título, origen y
`source_url`. Se conservan asimismo las fechas y enlaces de cada trámite.
Resultado: **247 enlaces documentales**, 84 instrumentos con documentos
enlazados y 5 con metadatos solamente. Las fichas y los enlaces se extraen en
vivo: no hay una lista fija de actuaciones ni registros precargados.

Ejemplos comprobados:

- [NNSS.R-002](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/34499):
  revisión de normas subsidiarias, con memoria justificativa y publicaciones.
- [NNSS.R-002.M-049](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40866):
  modificación 1/2025; aprobación definitiva municipal 17/12/2025 y primera
  publicación de aprobación definitiva indicada en la ficha, BOP 19/02/2026.
  Su publicación posterior en DOE, 25/02/2026, se conserva como otro trámite.
- [NNSS.R-002.M-050](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/41023):
  modificación 2/2025 de la SU-29 y traslado de zona verde, aprobación
  30/04/2026 y publicación 02/07/2026, según la ficha actual.
- [NNSS.R-002.ED-014](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/41241):
  estudio de detalle de la parcela P1 del SAU-6A Las Dehesillas, sin fechas de
  aprobación/publicación final verificadas en los campos correspondientes.

## Semántica y límites

`fecha_aprob` procede exclusivamente de «Fecha AD», y `fecha_publicacion` de
«Fecha de publicación AD», con su diario en `diario_publicacion`. No se toma
la fecha de consulta o impresión como acuerdo ni se deduce una fecha del título.
Las fechas de los trámites conservan su etiqueta original dentro de `tramites`;
no se extrapolan a concesiones de licencias. El título y estado son los de la
ficha, no una interpretación de la fase de ejecución de una obra.

SITEX advierte del carácter informativo de sus datos: el estado se conserva como
`estado_fuente`, sin certificar vigencia legal. La cobertura es completa para el
árbol devuelto en esta consulta, **parcial para el conjunto de actuaciones de
Montijo**. No abarca todas las obras, licencias, programas de ejecución u otras
secciones de SITEX. No se leen masivamente los PDF ni se verifica cada enlace
histórico. Los cinco instrumentos sin enlaces se declaran `metadata_only`.

No se generan coordenadas, geometrías ni fechas ausentes. Todos los registros
llevan `publication_ready: false` y `geometry_status: unavailable`.
El manifest desactiva licencias, programación y jitter de geocodificación.
`proyectos.source: ayuntamiento` selecciona el cauce del adaptador en el esquema
existente; la procedencia real de cada registro es explícitamente
`junta_extremadura_sitex`.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_montijo -v`.
Cubren árbol anidado, documentos agrupados/deduplicados y aislados entre fichas,
fechas separadas y ausentes, identidad territorial, rechazo de paginación,
metadatos sin documentos, manifest, licencias desactivadas y conservación de la
salida anterior ante una ficha fallida.

La ejecución real carga `load_manifest('montijo')` y
`load_portal_adapter(manifest)`, añade solo para evidencia
`manifest.portal.config['evidence_dir']='evidence'` y ejecuta
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Así se verifica también el clasificador compartido de entidades: resultado
`ok`, 87 expedientes y 2 pendientes. Las referencias oficiales NNSS y PDSU
carecen de componente numérico y el clasificador compartido las deja pendientes;
se conservan literalmente, sin fabricar números para eludir esa regla.
Las siete pruebas pasan.

Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, captura municipal
`evidence/discovery-1.html`, página de entrada `evidence/discovery-0.html`,
árbol de la ejecución `evidence/sitex-inventory.html` y las 89 capturas
`evidence/sitex-<id>.html`. La validación registra URL, parámetro POST,
conteos, limitaciones, prueba y comprobación documental.
Se comprueba una muestra de descarga, la memoria 11371 enlazada desde NNSS.R-002,
con HTTP 200, Content-Type `application/octet-stream` y firma `%PDF-`
verificada en los 65.536 bytes iniciales capturados. Se guarda solo el prefijo
y los metadatos de respuesta; no equivale a una
revisión del contenido íntegro ni del resto del archivo documental.

No se ejecutan publicación, geocodificación, base de datos ni pasos globales.
