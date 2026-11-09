# Toro — INE 49219, provincia de Zamora

Investigación y extracción real: 8 de noviembre de 2026. El campo de entrada «Toro (Zamora)» identifica el municipio; la provincia normalizada del manifest es **Zamora**, comunidad de Castilla y León.

## Fuentes oficiales descubiertas

- Urbanismo municipal: https://www.toroayto.es/urbanismo.php
- Concejalía de Urbanismo y Obras: https://www.toroayto.es/entidades.php?i=12
- Archivo PLAU enlazado por ambas páginas, limitado expresamente a provincia 49 y municipio 219: https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion&pager.sortindex=-3&provincia=49&municipio=219

La página municipal también publica avisos, ITE, ayudas y publicidad de alumbrado. Esos documentos no se convierten en proyectos ni licencias. La sede electrónica ofrece solicitudes, que tampoco acreditan concesiones. Se utiliza el inventario documental urbanístico oficial PLAU, no noticias ni anuncios de contratación. El adaptador comprueba en cada ejecución que el Ayuntamiento sigue enlazando el inventario correcto y que este muestra Código INE 49219. El archivo declaraba actualización a 06-nov-2026.

## Cobertura obtenida

El inventario vigente (`bInfoPublica=N`, sin activar históricos) contiene **29 entradas**: resultados 1–15 y 16–29. Se recorren todos los rangos hasta alcanzar el total declarado, comprobando continuidad, total estable e identidades únicas. Una página repetida, un cambio de estructura o un listado incompleto provoca error antes de sustituir el archivo de salida. Las fechas no se usan como corte incremental: `update_proyectos` refresca el inventario completo.

Se excluyen cuatro entradas tituladas SENTENCIA y un convenio urbanístico. Las otras 24 publicaciones se agrupan en **23 instrumentos**, conservando **291 enlaces a ficheros**. Incluyen la revisión del PGOU, modificaciones del PGOU y del conjunto histórico, estudios de detalle, planes parciales, proyectos de actuación/normalización/urbanización y el Plan Regional del nuevo acuartelamiento Monte la Reina. No se agregan actuaciones distintas por compartir sector: el Plan Parcial, el Proyecto de Actuación y el Proyecto de Urbanización de El Palo conservan su identidad propia.

La modificación del PGOU de Rejadorada n.º 30 (PLAU 299041) y su corrección de errores (299383) forman un registro. Se comparan instrumento, fecha de acuerdo y título normalizado, retirando únicamente el prefijo de corrección y diferencias tipográficas. Las publicaciones originales y sus documentos permanecen en `publicaciones`; sus enlaces se reúnen en `documentos`. El PGOU (289318) tiene 208 ficheros, todos conservados como documentos del mismo instrumento, no como 208 proyectos.

Cinco instrumentos aparecen sin listado de ficheros en PLAU: normalización de Corredera 36/Tinta de Toro, urbanización de El Palo, actuación de El Palo, modificación PECH de San Francisco 7 y estudio de detalle de Tagarabuena. Se retienen las referencias oficiales y sus enlaces de boletín, sin inventar anexos. Los listados de ficheros observados no tienen paginación; si aparece una, se exige revisar el parser en vez de devolver una fracción.

## Semántica y límites

`fecha_publicacion` y `fecha_acuerdo` proceden de columnas diferentes del inventario. Por ejemplo, Canto 1 figura publicado el 27/11/2025 con acuerdo del 04/07/2025. En Rejadorada se conservan tanto la publicación inicial del 15/05/2023 como la corrección del 25/10/2023, ambas con acuerdo del 31/03/2023. No se crea `fecha_aprob`, no se deduce una fase de `instrumento` ni se afirma concesión de licencia, ejecución física o vigencia jurídica actual por la mera presencia en el archivo.

Cada registro representa un instrumento documentado; `source_entity_type: documento` refleja esa evidencia ante la política común, con la identidad real PLAU en `id_origen`. `source: ayuntamiento` indica la vía municipal de descubrimiento; `organismo_fuente` identifica expresamente a la Junta de Castilla y León. Se retienen las URL del inventario, de la página municipal, del boletín y de los listados de ficheros. Se eliminan identificadores temporales `jsessionid` de los enlaces permanentes.

Cobertura parcial: no incluye documentos históricos ocultos, información pública en trámite, todas las obras municipales ni registros de licencias. No se han interpretado todos los PDF ni sus geometrías. Sin coordenadas ni geocodificación artificial: `geometry_status: unavailable`, `publication_ready: false`, `geocode.jitter_missing: false`. Licencias y programación están desactivadas.

## Verificación y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_toro -v` — **7 pruebas correctas**. Comprueban fechas diferenciadas, agrupación y aislamiento documental, exclusiones, detección de estructura/municipio/rango incorrectos, enlaces sin sesión, paginación completa y rechazo de páginas repetidas sin sobrescribir una salida anterior, manifest y licencias desactivadas. Los fixtures son sintéticos, internos a las pruebas; no alimentan la extracción real.

La ejecución real usa `load_manifest('toro')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['evidence_dir']` apuntando al directorio local de evidencia. Resultado: **23 registros**, política de entidades `status: ok`, cero entidades desconocidas. Evidencias locales no destinadas al commit:

- `evidence/proyectos.jsonl`: extracción real anotada por el registro común de adaptadores.
- `evidence/validation.json`: recuentos, URLs efectivamente consultadas, correspondencia de capturas, límites, runtime y comprobación de muestra PDF.
- Capturas HTML de la página municipal, ambas páginas del inventario y los listados de ficheros consultados, nombradas por hash de URL.
- `evidence/rejadorada-pdf-prefix.bin`: primeros 4096 bytes del fichero 151167; respuesta HTTP 200, `application/pdf`, firma `%PDF-`. El enlace oficial redirige a http://www.jcyl.es/plaupdf/49/49219/299041/DOCUMENTO.pdf. Esta comprobación puntual no afirma que todos los enlaces se hayan descargado o validado.

Solo se añaden el manifest, esta investigación, el adaptador y sus pruebas. No se modifican fuentes compartidas ni dependencias, ni se ejecutan publicación, bases de datos o despliegues.
