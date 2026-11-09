# Malpartida de Cáceres — INE 10115, provincia de Cáceres

Consulta y extracción real: 9 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, el cargador de manifiestos, el registro de
adaptadores y los ejemplos Manlleu y Chipiona. No se cambian fuentes compartidas
ni dependencias.

## Descubrimiento y fuentes oficiales

- Web del Ayuntamiento: https://www.malpartidadecaceres.es/ . Enlaza su oficina
  virtual y sede; la portada no es un inventario de actuaciones.
- Portal de transparencia municipal:
  https://malpartidadecaceres.sedelectronica.es/transparency . La sección
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» muestra cero documentos en la
  consulta anónima observada. No se interpreta como inexistencia de proyectos.
- Consulta oficial de planeamiento de la Junta de Extremadura:
  https://sitex.juntaex.es/SITEX/planeamiento . Su selector identifica
  `368 = Malpartida de Cáceres`, distinto de Malpartida de Plasencia (369) y
  Malpartida de la Serena (110). 368 es un identificador interno, no el INE.
- Inventario que utiliza esa interfaz:
  https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat . Petición POST
  de consulta, con `municipioseleccionado=368` y cabeceras AJAX de la interfaz.
  No requiere credenciales, sesión autenticada ni envío de formularios de trámites.

El árbol completo recibido contiene **48 fichas**: cinco vigentes municipales,
42 no vigentes y un Plan Territorial Tajo-Salor en trámite. Se seleccionan todas
las fichas municipales etiquetadas `Vigente`, descubriendo sus identificadores
desde el árbol, sin una lista fija de expedientes. El refundido raster es otra
representación del planeamiento, no un sexto instrumento. No hay controles de
paginación en esta respuesta; el parser rechaza expresamente la aparición de
paginación para evitar resultados silenciosamente incompletos.

## Resultado de la extracción viva

| Ficha oficial | Referencia | Documentos enlazados | Aprobación según SITEX | Publicación AD según SITEX |
| --- | --- | ---: | --- | --- |
| https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37118 | PGM | 49 | 30/07/2020 | 28/10/2020 |
| https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40495 | PGM.M-003 | 3 | 13/10/2023 | 24/10/2023 |
| https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40484 | PGM.M-001 | 5 | 30/11/2023 | 29/01/2025 |
| https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40485 | PGM.M-002 | 2 | 30/11/2023 | 28/07/2026 |
| https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40938 | PGM.PPO-001 | 2 | 18/09/2026, discrepante | 19/10/2026 |

Son **cinco registros y 61 enlaces**: el Plan General Municipal, tres
modificaciones (retranqueos industriales, unidad UA-SU-10.1 de Las Arenas y usos
hoteleros) y el plan parcial del sector 4.1 AR/SUB-4 UA/SUB-4.1.1. No se extraen
noticias, modelos de licencia ni anuncios de contratación como proyectos.

Cada instrumento conserva su referencia, título descriptivo de la ficha,
trámites con fecha y enlaces agrupados en `documentos`, con la URL de procedencia
de cada enlace. Se conservan publicaciones DOE de distintas fases y documentos
técnicos, sin crear registros separados por plano o memoria. El PGM tiene 46
documentos técnicos y tres publicaciones DOE; las modificaciones M-002 y el
plan parcial solo ofrecen aquí enlaces DOE. Esto no equivale a disponer de toda
la documentación técnica aprobada. Las URL originales HTTP del DOE se retienen
como las publica SITEX.

## Fechas y limitaciones

`fecha_publicacion` procede de «Fecha de publicación AD», no de la fecha de
acuerdo. `fecha_aprob` procede de «Fecha AD». `fechas_sitex` conserva ambas con
procedencia explícita; `tramites` conserva además el historial. `fecha` genérica
queda nula y no se infiere una fase a partir del tipo de instrumento.

**Discrepancia verificada:** para PGM.PPO-001, SITEX indica 18/09/2026, mientras
el anuncio municipal publicado en el DOE indica acuerdo plenario de
18/09/2025. Fuente de contraste consultada y capturada:
https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=2010o&xml=2026081727 .
El registro mantiene el valor literal de SITEX en `fechas_sitex`, deja
`fecha_aprob=null` e incorpora `date_warning` y la URL del contraste. No se
resuelve silenciosamente el año ni se atribuye al acuerdo la fecha del anuncio
(8/10/2026). No se realizó contraste independiente de todas las demás fechas.

Cobertura temática parcial: instrumentos municipales vigentes del catálogo
autonómico, excluyendo históricos y supramunicipales. No representa un histórico
exhaustivo de proyectos ni un registro de obras ejecutadas o licencias concedidas.
El manifiesto usa el canal de proyectos `ayuntamiento` compatible con el cargador,
pero cada registro declara `source=junta_extremadura` y su procedencia SITEX.
No se infieren ejecución material, concesión de licencia, vigencia jurídica
independiente del estado del catálogo, coordenadas ni geometría. Todos los
registros tienen `publication_ready=false`, geometría no disponible y coordenadas
nulas. `licencias.enabled=false`, `schedule.enabled=false` y
`geocode.jitter_missing=false`.

## Validación reproducible y evidencia local

Runtime utilizado, sin instalación de software:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas offline:
`-m unittest municipio.test_malpartida_de_caceres -v` — **10 pruebas correctas**.
Cubren filtrado por municipio/estado, fechas distintas y ausentes, discrepancia,
agrupación y aislamiento documental, cambios de HTML, fechas inválidas,
paginación inesperada, manifiesto y fallo de una ficha sin reemplazar el snapshot
anterior. No dependen de capturas locales ni de acceso a red.

Extracción real mediante `load_manifest('malpartida-de-caceres')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
La configuración temporal `capture_dir='evidence/live'` guarda las respuestas que
procesa el adaptador. El refresco incremental vuelve a leer el árbol completo;
no usa fechas ni cursores para omitir expedientes.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: cinco registros reales, pasando por el cargador y
  su anotación de política de entidades (cinco categorías desconocidas; no se
  convierten automáticamente en oportunidades publicables).
- `evidence/validation.json`: conteo, URLs, consulta de inventario, limitaciones,
  resultados de pruebas, hora UTC y hashes SHA-256 de las capturas vivas.
- `evidence/live/inventory.html` y cinco `figure-*.html`: respuestas utilizadas.
- `evidence/home.html`, `sede.html`, `planeamiento.html` y
  `doe-plan-parcial.html`: capturas de descubrimiento y contraste.
- `evidence/document-sample.bin`: primeros 1024 bytes de la memoria informativa
  https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/14339 . Consulta Range
  con HTTP 206, Content-Type application/octet-stream y firma `%PDF-` válida.
  Solo se comprueba esta muestra; no se afirma haber leído todos los PDF.

No se ejecutaron publicación, bases de datos, sincronización, despliegue ni
geocodificación. Los únicos archivos fuente añadidos son los cuatro solicitados.
