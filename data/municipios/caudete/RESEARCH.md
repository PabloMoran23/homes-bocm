# Caudete — INE 02025, Albacete

Verificación en directo: 2026-11-07. Adaptador de un inventario municipal real:
las Normas Subsidiarias de Planeamiento, agrupadas en **un instrumento con seis
enlaces documentales**. Cobertura deliberadamente parcial, sin licencias
concedidas ni geometría verificada. `publication_ready=false`; programación y
jitter desactivados. No confundir con Caudete de las Fuentes (Valencia).

## Fuentes oficiales descubiertas

- https://www.caudete.org/ayuntamiento/obras-y-urbanismo-legislacion/
  — HTTP 200, inventario estático de legislación estatal, autonómica y local.
  La sección local identifica el texto NNSS de Caudete, planos y aprobación.
  Se extraen sus documentos, excluyendo leyes generales, ordenanzas fiscales,
  el documento de protección del patrimonio y formularios. El inventario
  advierte literalmente: «No incluyen modificaciones puntuales ni estudios de
  detalle». No se interpreta como inventario completo ni actualizado de todo
  el planeamiento vigente. No tiene paginación en la captura revisada.
- https://www.caudete.org/ayuntamiento/obras-y-urbanismo-presentacion/
  — página departamental con competencias y clases de expedientes; no es un
  inventario de proyectos concretos. Descubierta por búsqueda oficial.
- https://www.caudete.org/ayuntamiento/obras-y-urbanismo-tramites/
  — HTTP 200; trámites y solicitudes. No acredita licencias otorgadas. Captura
  local `evidence/source-4.bin`.
- https://caudete.sedipualba.es/transparencia
  — HTTP 200; la respuesta identifica «02025 - AYUNTAMIENTO DE CAUDETE» y
  domicilio en Caudete (Albacete). Expone categorías de transparencia y controles
  de carga, no un registro de expedientes urbanísticos en el HTML inspeccionado.
  No se afirma que el servicio carezca de información accesible por otras vías.
  Captura `evidence/source-3.bin`.
- La búsqueda oficial también devuelve un acuerdo regional sobre modificación
  nº 9, de marzo de 2026, en urbanismo.castillalamancha.es. Queda fuera de este
  adaptador del texto base; confirma que no debe presentarse esta extracción
  como totalidad del planeamiento municipal. No se extraen registros de snippets.

## Documentos y agrupación

Los seis enlaces proceden de cinco entradas del mismo índice municipal:

1. Texto normativo: https://www.caudete.org/urbanismo/TEXTO%20NNSS%2029_05_96.pdf
2. Plano de alineaciones y rasantes, alta resolución: https://www.caudete.org/urbanismo/NNSS.jpg
3. El mismo plano, baja resolución: https://www.caudete.org/urbanismo/NNSS2.jpg
4. Planos agrupados: https://www.caudete.org/urbanismo/PLANOS%20AGRUPADOS%20NNSS.pdf
5. Acuerdo de aprobación de la revisión por la Comisión Provincial:
   https://docm.jccm.es/docm/descargarDisposicionAntigua.do?ruta=1996/06/28&idDisposicion=123062364268520714
6. Publicación del texto refundido:
   https://www.caudete.org/urbanismo/PUBLICACION%20NNSS%20BOP%20CAUDETE.pdf

Son documentos y variantes de un instrumento, no seis proyectos. Se conserva el
texto descriptivo de cada entrada, el rótulo de cada enlace, su URL original y
la página de procedencia. Los enlaces municipales antiguos HTTP se solicitan por
HTTPS en el mismo host y ruta; ambas versiones quedan registradas. Las URLs de
consulta del DOCM retienen sus parámetros.

La fase «aprobación definitiva» procede del título explícito de la entrada del
texto refundido. El índice HTML no expresa fechas del instrumento. `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas: no se convierten
el nombre del PDF, la ruta del DOCM ni la fecha de captura en fechas de acuerdo.
La lectura local del PDF del BOP muestra un suplemento al nº 91 de 29 de julio de
1996 y un anuncio municipal fechado 4 de julio de 1996: son conceptos diferentes.
El adaptador no analiza fechas dentro de PDFs y no asigna ninguna de ellas como
fecha de aprobación. El DOCM descargado es un escaneo sin texto extraíble mediante
`pdftotext`; no se inventa su contenido.

Los planos no se convierten en coordenadas ni geometrías mediante suposiciones.
No se utilizan centroides municipales ni jitter. `lat`, `lon` y `geometry` son
nulos. La política compartida anota este instrumento como categoría desconocida;
se conserva ese resultado en la evidencia sin modificar la política común.

## Comportamiento y validación

Se descarga el índice con timeout y límite de 3 MB; superar ese límite falla,
sin analizar una respuesta truncada. Se exige su encabezado, un único bloque de
contenido, las cuatro categorías documentales esenciales y enlaces de hosts
oficiales revisados. El parser procesa todas las entradas de ese bloque sin tope
de filas, deduplica enlaces y agrupa el instrumento con identidad estable.
Rechaza categorías nuevas NNSS no reconocidas y señales de paginación para exigir
revisión del crawler antes de aceptar cobertura parcial inadvertida. La
actualización vuelve a leer el índice completo; no usa fechas de corte.

Validación con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_caudete -v
```

Ocho pruebas pasan: agrupación y exclusiones, procedencia y normalización de
URLs, fechas y geometría ausentes, fallo con inventario incompleto, detección de
paginación, hosts y enlaces inválidos, deduplicación, actualización completa,
licencias desactivadas y carga del manifest por el registro real.

Extracción en directo realizada con `load_manifest('caudete')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, incluida la anotación de
la política compartida: **1 registro real**. Evidencia local, fuera de los cuatro
archivos fuente entregables:

- `evidence/proyectos.jsonl`: resultado real.
- `evidence/inventory.html`: bytes del índice usados por el adaptador.
- `evidence/document-*`: capturas de los seis documentos enlazados.
- `evidence/validation.json`: cantidad, URLs, respuestas HTTP, hashes, pruebas,
  limitaciones y resultado de extracción.

No se ejecutan publicación, acceso a bases de datos, credenciales ni despliegue.
