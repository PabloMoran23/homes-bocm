# A Rúa — INE 32072, Ourense, Galicia

Investigación y extracción real: 2026-11-09. Un único adaptador municipal,
sin cambios en fuentes compartidas ni dependencias.

## Descubrimiento y procedencia

La web oficial https://arua.es/ identifica el Concello y su dirección en
A Rúa, Ourense. Su sección https://arua.es/es/transparencia-2/ no muestra
un inventario de proyectos. La sección de impresos
https://arua.es/servizos/impresos-oficiais/ ofrece solicitudes de licencias:
no son concesiones y no se extraen. Tampoco se usan anuncios de contratación
como proyectos ni se clasifican noticias generales como actuaciones.

Fuente utilizada: inventario oficial autonómico SIOTUGA de la Xunta de Galicia,
https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=32072 .
La ayuda https://siotuga.xunta.gal/siotuga/axuda describe su cobertura y acceso
municipal por INE. El selector publica 32072 = Rúa, A; todas las fichas
extraídas verifican además `menutitle=Rúa, A` y `folder=ARUA`.
`proyectos.source=ayuntamiento` es el modo del pipeline existente; cada registro
declara la procedencia efectiva `source=siotuga_xunta` y el organismo Xunta.

El JavaScript oficial `assets/inventario/controls.min.js?2.5.0`, capturado
localmente, muestra las consultas públicas POST a
`assets/inventario/query_document.php` (`id=32072`, `idclase`) y
`assets/inventario/getIOTPU.php` (`iddoc`, `idp=0`, `lang=gl_ES`).
Se obtiene el token anónimo del formulario público, sin autenticación.
Los parámetros de consulta y el identificador documental quedan en cada registro.

## Cobertura y agrupación

Se descargan íntegramente las cuatro categorías de planeamiento municipal:
14 general (4 entradas), 13 desarrollo (5), 16 histórico (2), 18 delimitaciones
de núcleo rural (0, respuesta JSON null). Resultado: **11 registros y 260 enlaces
documentales**. Las respuestas son arrays completos; el frontend recorre todos
los elementos y aplica DataTables en cliente. No hay límite de resultados ni
corte de páginas en el adaptador. Un envelope inesperado, un cambio de identidad,
una respuesta inválida o un inventario totalmente vacío causan error antes de
reemplazar el resultado anterior. Update vuelve a obtener el snapshot completo.

Una fila por ficha documental oficial, identificada por ID SIOTUGA, con todos sus
planos, memorias, anexos y normas agrupados en `documentos`, conservando títulos,
grupos y enlaces. No se producen proyectos individuales a partir de cada PDF.
Se incluyen el PXOM 27982, NSP Nº 5 (27605), Rampa de Fontei (22649), NSP NUM 2,3
(22700), As Pedreiras (25561), estudio de detalle de Rúa Pireira (28523), OU-533
(27865), Piñeira (26134), Fondo da Rúa (25272), revisión NSP (22699) y normas
subsidiarias históricas (26443). La ficha 22700 agrupa modificaciones 2 y 3 en
una sola ficha original; se mantiene esa unidad documental y la incidencia
que deniega la modificación 1 incluida en ese mismo documento.

Tres fichas (22649, 26134, 25272) tienen `elementos=null`: se conserva la entrada
real del inventario con `documentos=[]` y disponibilidad explícita, sin inventar
enlaces. Las otras ocho tienen componentes. Se comprobó una muestra real de
memoria del PXOM:
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/ARUA/documents/27982me003.pdf
HTTP 200, application/pdf, firma %PDF. Solo se capturaron los primeros 4096 bytes;
no se verificó el contenido de los otros 259 archivos.

## Semántica y límites

Son instrumentos de planeamiento e inventarios documentales, no licencias
concedidas ni evidencia de ejecución física. `source_entity_type=documento`
permite que la política compartida los clasifique como recursos documentales,
sin actividad elegible. No se inventa un número de expediente a partir del ID
de catálogo. `publication_ready=false`, sin geometría ni coordenadas.

`fechaaddef` se conserva como `fecha_aprob`; BOP, DOG y normativa BOP tienen
campos separados. No se deducen fechas de acuerdo ni una fecha genérica de
publicación. Los valores originales y la fecha de texto refundido se guardan en
`fechas_fuente`. El PXOM contiene BOP/normativa 2016-02-03 anterior a aprobación
2016-02-25: aparente inconsistencia de origen conservada, sin corregirla.
Se mantienen las incidencias jurídicas. La presencia en el inventario no acredita
vigencia; se incluyen históricos y no se asignan fases por tipo documental.

Cobertura parcial del municipio: solo estas categorías de planeamiento; no incluye
ordenación territorial supramunicipal, registro de obras, noticias, contratación
ni un registro de concesiones. Licencias, programación y jitter de geocodificación
desactivados. No hay publicación, base de datos ni geocodificación en la ejecución.

## Verificación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `-m unittest municipio.test_a_rua -v` (9 correctas). Comprueban agrupación,
aislamiento, semántica de fechas, incidencias, documentos ausentes, no truncar
arrays de 150 entradas, rechazo de envelopes, identidad municipal, duplicados,
fechas inválidas, procedencia documental, manifest y licencias sin red, además
de conservar el resultado anterior ante fallos.

Extracción real con `load_manifest('a-rua')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando
`manifest.portal.config['evidence_dir']` para capturar las respuestas de esa
ejecución. Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, cuatro respuestas de categorías, once fichas JSON,
HTML del inventario, JavaScript oficial y muestra binaria PDF. La validación
incluye recuentos, URLs, limitaciones y clasificación de la política compartida.
