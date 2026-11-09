# Soutomaior — INE 36053, Pontevedra, Galicia

Verificación en vivo: 2026-11-09. Adaptador exclusivo para Soutomaior.

## Descubrimiento y fuentes oficiales

La portada https://soutomaior.gal/ enlaza a
https://soutomaior.gal/urbanismo/. En esta última, «Consulta aquí o PXOM de
Soutomaior» remite al inventario de la Xunta de Galicia:
https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36053
(el enlace municipal usa HTTP; se consulta mediante HTTPS).
La tabla oficial https://siotuga.xunta.gal/siotuga/urb identifica igualmente
36053, Soutomaior y PXOM de 2017-03-13. No se usa una noticia como semilla.

El JavaScript público `assets/inventario/controls.min.js?2.5.0` documenta las
consultas POST a `assets/inventario/query_document.php` con `id=36053` e
`idclase` 14 (general), 13 (desarrollo), 16 (histórico) y 18 (núcleos rurales).
Se utiliza únicamente el nonce del formulario público, sin autenticación.
Las cuatro respuestas son arrays completos (o null); la paginación DataTables
ocurre en el cliente sobre esos arrays. Se recorre todo el array, sin límites de
filas. Un cambio a un objeto paginado provoca error y exige revisar el recorrido.

Cada ID descubierto se consulta en `assets/inventario/getIOTPU.php`, POST
`iddoc=<id>&idp=0&lang=gl_ES`. La ficha debe confirmar ID, Soutomaior y carpeta
SOUTOMAIOR. Los parámetros se guardan en `provenance`, sin nonce.
Las URLs de documentos se reconstruyen exactamente como lo hace el portal:
`filesroot + folder + /documents/ + pathesperado`, relativas a SIOTUGA.

## Cobertura y semántica

Extracción real: **20 instrumentos y 219 enlaces documentales**: 6 de planeamiento general, 9 de desarrollo,
5 históricos y ninguno en delimitación de núcleos rurales (respuesta null).
Incluye el PXOM 28065, el PEID de un centro de salud 28493, planes especiales,
estudios de detalle y modificaciones. Los planos, memorias y normativa de cada
ID se agrupan en `documentos` con título, grupo, ID y enlace; no generan proyectos
adicionales. Las modificaciones con ID propio se conservan como instrumentos.
Seis fichas tienen `elementos=null` (24860, 24741, 24661, 24662, 26605 y
27076). Las fichas con `elementos=null` se conservan como instrumentos documentados por
el inventario oficial, marcando los documentos como no disponibles.

`fecha_aprob` procede de `fechaaddef` (aprobación definitiva); las fechas DOG,
BOP y normativa BOP se conservan por separado. `fecha` y `fecha_publicacion`
quedan nulas para no elegir arbitrariamente una publicación. No se inventa una
fecha de acuerdo distinta. Se retienen incidencias jurídicas del inventario y
la ficha; la aprobación histórica no implica vigencia actual. La clase 16 se
marca histórica; para las demás no se infiere vigencia.

Cobertura parcial: excluye el bloque de instrumentos de ordenación territorial
que el mismo visor consulta separadamente mediante `assets/iot/queryIotInv.php`,
los expedientes en tramitación de otros portales y el registro de licencias.
No se extraen noticias municipales, anuncios de contratación ni formularios.
No se afirma que el inventario contenga todos los proyectos u obras municipales.
Actualizar vuelve a leer la instantánea completa; no registra bajas ni un historial
de cambios. Se falla ante respuestas inválidas, conflictos de ID, discrepancias
de fechas o municipio y listas de documentos vacías inesperadas.

## Geometría

geometry_status: unavailable

SIOTUGA ofrece visor y acceso WMS en su tabla de urbanismo, pero no se ha
verificado geometría vectorial por instrumento. Los planos JPG/PDF se conservan
como enlaces, sin vectorizarlos ni asignarles centroides. Coordenadas y geometry
nulas, publication_ready false y geocode.jitter_missing false.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `python -m unittest municipio.test_soutomaior -v` (4 pasan).
Verifican agrupación, deduplicación, fechas, procedencia, identidad municipal,
rechazo de sobres paginados, arrays de más de una página, documentos ausentes,
histórico, integración del manifest y licencias deshabilitadas sin red.

Extracción: instanciar `SoutomaiorAyuntamientoAdapter('soutomaior',
{'capture_dir': 'evidence'})` y llamar a
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
`evidence/validation.json` contiene conteo, enlaces, limitaciones y comprobaciones
de documentos. Capturas HTML, JS y JSON originales y dos PDF de muestra quedan
en evidence/. No se descargan todos los documentos. Evidencia local, no fuente
ni parte del commit. schedule.enabled=false y licencias.enabled=false.
