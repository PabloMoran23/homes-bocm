# Foz — Lugo — INE 27019

Verificación en vivo: 2026-11-07. Un único adaptador municipal, con cobertura
parcial del inventario de planeamiento que el Concello delega en la Xunta.

## Descubrimiento y fuentes oficiales

- Documentación municipal: https://concellodefoz.gal/urbanismo/documentacion/
- Planeamento urbanístico: https://concellodefoz.gal/urbanismo/normativa/
  declara que la normativa aplicable está en SIOTUGA y enlaza directamente
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=27019
- El inventario identifica el código 27019 como Foz. Su JavaScript público
  `assets/inventario/controls.min.js?2.5.0` revela las consultas utilizadas por
  la propia interfaz: POST `assets/inventario/query_document.php`, con
  `id=27019` e `idclase=14` (general) o `13` (desarrollo). Las respuestas son
  arrays completos: DataTables ordena y pagina en el cliente. El adaptador
  consume todos los elementos, sin topes, y rechaza envoltorios desconocidos.
- Las fichas se obtienen mediante POST `assets/inventario/getIOTPU.php`,
  `iddoc=<id descubierto>`, `idp=0`, `lang=gl_ES`. El valor público del
  formulario se obtiene de cada sesión y no se guarda. Los enlaces se
  construyen exactamente como la interfaz a partir de `filesroot`, `folder`
  y `pathesperado`. Se verifica identidad de ficha y carpeta FOZ.

Se inspeccionaron además las consultas histórico (16: dos instrumentos) y
núcleos rurales (18: null). Se excluyen expresamente de la extracción, al igual
que el inventario de ordenación territorial. La sección municipal de movilidad
https://concellodefoz.gal/urbanismo/plan-de-mobilidade-sostible/ remite a la sede
https://concellodefoz.sedelectronica.es/transparency/dd578735-81ab-4994-91af-e4b4d294f9c9/;
no se ha extraído ni verificado su contenido. Documentación general contiene
«Bases», que no se convierte en proyecto. No se extraen noticias, contratación,
formularios ni licencias concedidas. La primera petición sin User-Agent al
portal municipal dio 403; las peticiones posteriores con navegador dieron 200.
La extracción del inventario Xunta finalizó con HTTP 200.

## Resultado y semántica

40 paquetes fuente: 10 de planeamiento general y 30 de desarrollo. Se producen
**39 instrumentos**, con **945 enlaces documentales**, incluidos planos y ZIP.
Los paquetes SIOTUGA 28131 (PXOM de 2018) y 28708 (ámbitos suspendidos de ese
mismo PXOM) se agrupan en un solo registro, conservando sus títulos, IDs,
fechas y documentos por paquete. Modificaciones puntuales y estudios de detalle
con IDs distintos siguen siendo instrumentos distintos; una calle coincidente
no demuestra que sean el mismo expediente. Los IDs de salida derivan de IDs
oficiales; no se inventan números administrativos de expediente.

26 fichas de estudios de detalle devuelven `elementos: null`: se mantienen como
instrumentos identificados en el inventario, con documentos vacíos y
`documents_status: unavailable_in_source`. Sus IDs se enumeran en validation.json.
No se excluyen silenciosamente. Se falla ante ficha ausente, identidad incorrecta,
respuesta de consulta inesperada o inventario total vacío. Las escrituras son
atómicas; update repite la instantánea completa y no usa watermark de fecha.

Las fechas `fechaaddef`, `fechabop`, `fechadog` y `fechanormativabop` se conservan
por paquete en `fechas_fuente`. Las publicaciones BOP/DOG se distinguen de
`fecha_aprob`; no existe fecha genérica del registro ni fecha de concesión.
El paquete 28708 etiqueta `fechaaddef=2025-04-21`, pero su documento
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/FOZ/documents/28708nu001.pdf
es una resolución de 21/04/2025 publicada en DOG de 05/05/2025 que hace pública
la orden de aprobación de **10/04/2025** (expediente PTU-LU-06/003). Se comprobó
el PDF y su texto en evidencia; el adaptador conserva el campo crudo con una
advertencia, sin normalizarlo como aprobación. El paquete 27728 muestra
aprobación 29/12/2012 y BOP 25/01/2012: conserva ambas y advierte la incoherencia,
sin inferir una corrección. No se interpreta cada PDF para resolver otros errores.

La consulta actual del inventario no acredita vigencia jurídica individual de
cada instrumento antiguo. No se fuerza una fase «vigente» o «aprobado» para toda
la colección. `publication_ready=false`. La política compartida de entidades
anota los 39 registros como pendientes (`insufficient_identity_evidence`) y
reporta `adapter_incident/unknown_entity_spike`: requiere revisión independiente;
no se rellena `expte` con un ID de documento para eludir ese control.

## Geometría

`geometry_status: unavailable`. SIOTUGA ofrece visor y su JavaScript referencia
WMS `https://siotuga.xunta.gal/siotuga/ws?codine=27019&SERVICE=WMS&REQUEST=GetCapabilities`.
No se ha validado una capa vectorial enlazable a cada instrumento de salida.
Los planos documentales no se convierten en puntos. No se generan coordenadas,
centroides ni jitter. `geocode.jitter_missing=false`.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Comando de pruebas: `python -m unittest municipio.test_foz -v`: **5 pasan**.
Cubren arrays completos de más de una página visual, duplicados, rechazo de
paginación desconocida, identidad y URLs documentales, falta explícita de
documentos, agrupación del PXOM, separación de fechas y anomalías cronológicas,
y carga del manifiesto/adaptador por el registro compartido.

Extracción real ejecutada con `load_manifest('foz')`, `load_portal_adapter(...)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`; config local
`capture_dir=evidence` para guardar respuestas oficiales. Evidencias locales:
`evidence/proyectos.jsonl`, `evidence/validation.json`, arrays de inventario,
40 fichas JSON, páginas municipales, JavaScript público y PDF representativo.
Los enlaces de los otros PDFs/ZIP se conservan completos, sin verificar su
contenido ni descargar los 945 ficheros. La captura HTML del inventario elimina
el valor efímero del formulario. Las evidencias no forman parte de los fuentes.

Manifiesto: calendario deshabilitado y licencias deshabilitadas. Los métodos de
licencias producen salida vacía explícita. Sin cambios compartidos, dependencias,
publicación, sincronización, despliegues ni acceso a servicios privados.
