# Arnedo — INE 26018, La Rioja

Investigación y extracción en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y descubrimiento

Se revisaron el contrato `municipio/adapters/portal.py`, el cargador y esquema
`municipio/manifest.py`, el registro de adaptadores y los ejemplos Manlleu,
Hernani y Chipiona antes de implementar el adaptador.

La web municipal actual es https://www.arnedo.com/ y enlaza la sede electrónica
https://sede.arnedo.es. Se consultaron la portada, el área Ayuntamiento y la API
WordPress para descubrir inventarios. Las búsquedas de urbanismo/planeamiento
no proporcionaron allí un inventario documental utilizable. La antigua dirección
https://conecta.arnedo.com redirige a la sección actual de servicios Conecta.
No se usa la noticia de aprobación inicial de 2020 como estado actual del plan,
ni órdenes del día, formularios o anuncios de contratación como proyectos.

Fuente implementada, pública y sin identificación:

https://sede.arnedo.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TRANSPAR_PLANGENURB

El apartado municipal «PLAN GENERAL DE ORDENACIÓN URBANA» muestra Normativa,
Planos y «Todos los documentos». Esos controles ejecutan eventos STA; el GET
inicial no contiene las fichas. El adaptador conserva una sesión pública,
extrae los campos ocultos del formulario `webAppPageForm` y reproduce el POST a
https://sede.arnedo.es/sta/CarpetaPublic/submitAjax.aa con
`eventScreenId=TR_PLAN_GENURB`, `eventObject=LISTATABLON`,
`eventAction=LISTATABLON`, `eventArguments=KEY=all`.

## Cobertura y documentos

El resultado observado contiene **32 entradas**, una «Normativa PGM» y 31
planos, en `dataset_TR_PLAN_GENURB`. La tabla DataTables muestra diez filas por
página, pero toda la colección está en el HTML: se procesa el array completo,
sin limitarse a la página visible. Se cotejan los recuentos por tablón con
`numOpenResolutions` (1 Normativa y 31 Planos). Un array incompleto, un cambio a
paginación de servidor, duplicados o categorías desconocidas provocan error.

Las 32 entradas pertenecen al mismo Plan General Municipal: se produce **un
instrumento**, no 32 proyectos independientes. Incluye normativa y planos de
ordenación y gestión, categorías de suelo no urbanizable, sistemas generales,
energía, abastecimiento, saneamiento, inundabilidad, zonificación acústica y
fuera de alineación.

Cada ficha se obtiene con el evento `ACCION_DETALLE`, objeto vacío y
`eventArguments=KEY=<dboid>`, siguiendo el comportamiento del JavaScript oficial
de DataTables. Se exige que identifique el documento solicitado y contenga un
enlace público `/sta/docs/GetDocumentServlet?CUD=...&HASH_CUD=...&APP_CODE=STA`.
Se conservan título original, categoría, ID de publicación, procedencia,
fecha de publicación, texto del enlace, URL documental y evento de procedencia.
Los identificadores CUD y HASH_CUD son localizadores públicos descubiertos en
las fichas, no credenciales. Se vuelven a descubrir en cada actualización.

## Fechas, estado y límites

La sede etiqueta la fecha visible como «Fecha Publicación»: 19/04/2024 en las
32 entradas observadas. Se registra como `fecha_publicacion` de los documentos
y del instrumento mientras todos compartan la fecha; si difieren, la fecha del
instrumento queda vacía. No se interpreta `resolutionDate` como fecha de acuerdo
ni se deduce aprobación de la etiqueta genérica «Acuerdo» del enlace PDF.
`fecha`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos.

Cobertura municipal parcial: este adaptador representa el paquete documental
publicado del PGM, sin certificar vigencia, historial completo, modificaciones
posteriores, todas las obras ni licencias concedidas. Los planos PDF se enlazan;
no se extraen geometrías. No hay coordenadas verificadas: geometría y coordenadas
nulas, `publication_ready=false`. No se aplican centroides ni jitter.
`licencias.enabled=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false`. Las actualizaciones refrescan la colección
completa y solo reemplazan la salida tras validar todas las fichas.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_arnedo -v`

Siete pruebas correctas: agrupación y procedencia, fechas de publicación
separadas de aprobación, más de diez filas, recuentos incompletos, contenido
ajeno/vacío, documentos ausentes o externos, preservación de la salida ante
fallos y configuración del municipio.

Ejecución real a través de `load_manifest('arnedo')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 32 entradas
y 32 enlaces documentales**. El wrapper del registro añade la anotación de
política de entidades; esta no atribuye promotor ni altera el contenido fuente.
Se verificaron normativa, un plano de ordenación y el último plano acústico:
HTTP 200, tipo `application/pdf` y firma `%PDF-`. Solo se capturaron los primeros
512 bytes de cada uno; no se afirma haber interpretado todos los PDF.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `pgm-home.html`, `pgm-inventory.html`, las 32 capturas
`pgm-detail-<dboid>.html` y tres prefijos PDF. Las capturas de descubrimiento se
conservan también bajo `evidence/`. `validation.json` informa `live_records`,
fuentes, limitaciones, pruebas y verificaciones documentales. No se utiliza
base de datos, publicación, despliegue ni geocodificación.
