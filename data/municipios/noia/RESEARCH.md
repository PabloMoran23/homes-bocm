# Noia — INE 15057, A Coruña, Galicia

Verificación en vivo: 2026-11-07. Un único adaptador municipal. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y procedencia

La página municipal de Obras e Urbanismo
https://concellodenoia.gal/concelleria-de-obras-e-urbanismo/
responde HTTP 403 al cliente directo; se conserva la respuesta en evidencia.
No se extraen noticias, formularios, anuncios de contratación ni supuestas licencias.

El inventario oficial autonómico SIOTUGA identifica Noia con código 15057:
https://siotuga.xunta.gal/siotuga/urb?lang=es_ES
Su fila enlaza el inventario municipal. Fuente empleada:
https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15057&lang=es_ES

La interfaz pública utiliza `assets/inventario/controls.min.js` y consultas anónimas:

* POST `assets/inventario/query_document.php`: `id=15057`, `idclase=14`
  (planeamiento general, incluidas modificaciones) y `idclase=13` (desarrollo).
* POST `assets/inventario/getIOTPU.php`: `iddoc=<id descubierto>`, `idp=0`,
  `lang=es_ES` para cada instrumento.

Ambas rutas se resuelven contra https://siotuga.xunta.gal/siotuga/.
Se utiliza el nonce público del formulario de la sesión anónima; no se necesitan
credenciales. Cada ficha debe coincidir en ID, denominación, fechas, municipio
`Noia` y carpeta `NOIA`. Los parámetros reproducibles se guardan en cada registro,
sin persistir el nonce como identidad del instrumento.

## Cobertura y semántica

Extracción real: **23 instrumentos**, 13 de planeamiento general y 10 de desarrollo,
con **394 enlaces documentales** agrupados por ID de instrumento. Ejemplos:
Normas Subsidiarias de Planeamento (22412), modificación NSP para la EDAR de Barro
(22413), Plan Parcial SAU-1 Augalevada (23651), Plan Especial de Protección y Reforma
Interior del Núcleo Histórico (23650). Los documentos no generan registros propios.
Los IDs `noia-siotuga-<id>` derivan del catálogo oficial, no de números de expediente
supuestos. No se deduplican modificaciones diferentes por compartir el plan matriz.

La categoría histórica 16 contiene un PXOM de 1974 y se excluye expresamente.
La consulta exploratoria de delimitaciones rurales, categoría 18, devuelve null.
No se cubren ordenación territorial, todos los expedientes en tramitación, obras
públicas ni licencias concedidas. El inventario es una consulta actual de instrumentos
catalogados, muchos antiguos; no se presenta como una relación de obras nuevas ni
se deduce vigencia individual de la mera presencia en el catálogo. Se retienen las
incidencias jurídicas de la ficha cuando existen.

`fechaaddef` se conserva como `fecha_aprob` (aprobación definitiva), sin inventar
fecha de acuerdo. `fechabop`, `fechadog` y `fechanormativabop` se conservan como
`fecha_bop`, `fecha_dog` y `fecha_normativa_bop`. `fecha_publicacion` queda null:
no hay una única fecha de publicación municipal conocida. Algunas fechas oficiales
preceden la aprobación (p. ej. IDs 23107, 23109, 23654); se retienen literalmente,
con advertencia, sin corregirlas por inferencia.

Ocho instrumentos carecen de documentos enlazados: 25346, 23654, 23655, 23658,
23656, 23653, 23657 y 23652. Siguen siendo instrumentos reales del inventario;
se marcan `documentos_status=unavailable`, con lista vacía y advertencia explícita.
Para los restantes se conservan todos los componentes de todas las secciones,
incluidos JPG de planos y PDF de memoria, normativa y publicaciones. Los enlaces
se construyen exactamente como el cliente oficial (`filesroot/folder/documents/`).
Se ha descargado y verificado la firma PDF de `0252no001.pdf`, normativa del plan
matriz; no se afirma haber descargado ni comprobado individualmente los 394 enlaces.

## Paginación, actualización y errores

La aplicación devuelve arrays JSON completos; DataTables pagina en el navegador,
sin parámetros de límite, offset ni paginación del servidor en estas consultas.
Se recorren todas las filas de ambas categorías y todos sus componentes, sin corte
por cantidad ni fecha. Un objeto/envelope nuevo se rechaza para evitar aceptar una
página parcial. `null` significa categoría sin resultados; ambas categorías vacías
provocan error. También se rechazan IDs duplicados conflictivos, fechas inválidas,
fichas que cambian de identidad y rutas documentales fuera del origen esperado.
La salida se escribe de forma atómica solo después de terminar todas las consultas.
Update repite la instantánea completa y no utiliza marcas temporales que puedan
omitir revisiones del catálogo.

## Geometría y guardas

geometry_status: unavailable

La tabla de urbanismo ofrece WMS para 15057. Se comprobó HTTP 200 XML en:
https://siotuga.xunta.gal/siotuga/ws?codine=15057&SERVICE=WMS&REQUEST=GetCapabilities
Se conserva la respuesta. Es un servicio de visualización; no se ha establecido una
geometría vectorial por ID de instrumento. No se convierten imágenes de planos en
polígonos ni se usan centroides municipales. Coordenadas y geometry quedan null,
`publication_ready=false`, `geocode.jitter_missing=false`, `schedule.enabled=false`
y `licencias.enabled=false`.

La política compartida de entidades marca los 23 registros como `pendiente` por
`insufficient_identity_evidence`, e informa `adapter_incident/unknown_entity_spike`:
no reconoce `siotuga_id` como referencia de expediente. Se conserva este resultado
en la evidencia; no se inventan números de expediente ni se modifica la política
compartida para evitarlo. Esta incidencia limita cualquier ingestión posterior.

## Validación y evidencia local

Cinco pruebas offline pasan con:
`PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_noia -v`

Cubren agrupación de documentos, deduplicación, separación de fechas, rechazo de
schema/paginación nuevo, validación municipal, documentos ausentes, inconsistencias
de fechas y licencias deshabilitadas. La extracción live se ejecutó mediante
`load_manifest('noia')`, `load_portal_adapter` y `backfill_proyectos`, sin publicar.

`evidence/proyectos.jsonl`: 23 registros reales; `evidence/validation.json`: conteo,
fuentes, limitaciones y resultado de la política. Se guardan inventarios JSON,
fichas JSON, formulario HTML, muestra PDF y capacidades WMS. Evidencia local sin
commit. Durante la preparación el disco estuvo lleno; recuperó espacio y los
cuatro archivos y toda la evidencia requerida se escribieron en el workspace.
