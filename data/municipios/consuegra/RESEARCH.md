# Consuegra — Toledo — INE 45053

Verificación: 2026-11-07. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente implementada

La página oficial del área de [Urbanismo y Actividades Económicas](https://aytoconsuegra.es/urbanismo-y-actividades-economicas/)
enlaza «Normas Subsidiarias (NNSS) / ACCEDER» con el
[inventario municipal de Normas Subsidiarias](https://aytoconsuegra.es/normas-subsidiarias/).
Ambas páginas respondieron HTTP 200. Se ha implementado exclusivamente este
inventario documental, no una noticia prefijada ni formularios administrativos.

El inventario contiene seis entradas documentales de un único instrumento:

1. Normas Subsidiarias Consuegra (Texto Refundido 9/2014).
2. Plano de Alineaciones B1, B2, B3, C1, C2, C3.
3. Plano de Zonificación B1, B2, B3, C1, C2, C3.
4. Plano de Zonificación P. Industrial.
5. Plano entorno no urbanizable casco urbano.
6. Plano Termino Municipal.

Los seis enlaces de texto apuntan a visores públicos Google Drive publicados por
el Ayuntamiento. Se verificaron HTTP 200 y títulos PDF correspondientes en los seis
visores, sin sesión ni credenciales. Esto verifica acceso al visor y su título,
no una lectura íntegra del PDF. Cada documento conserva su URL exacta y la página
municipal que lo enlaza como procedencia. Los enlaces duplicados de icono y texto
se deduplican; el icono del último plano apunta a Dropbox y se conserva como
alternativa de la misma entrada, sin afirmar que ambos ficheros sean idénticos.
El enlace alternativo Dropbox no se ha comprobado. No se generan siete proyectos:
el resultado es **un instrumento con seis documentos y siete URLs documentales**.

## Semántica y límites

Las NNSS son un instrumento de planeamiento normativo, clasificado explícitamente
como `source_entity_type: normativa`. No se atribuye identidad de expediente ni
se presenta como una obra reciente o licencia concedida. «9/2014» se conserva
en el título como versión documental, sin convertirla en fecha. La página no
expone fechas de publicación, acuerdo o aprobación del instrumento; los campos
correspondientes quedan nulos. No se usa la fecha de subida ni la de actualización
de WordPress como aprobación. La vigencia jurídica y la integración de todas las
modificaciones posteriores no se han comprobado.

Cobertura deliberadamente parcial: únicamente la lista documental NNSS. Se
inspeccionó también el [archivo Noticias Urbanismo](https://aytoconsuegra.es/category/areas-municipales/urbanismo/noticias-urbanismo/),
que contiene otras actuaciones y anuncios de PAU. No se recorre ese archivo ni
se afirma cubrir sus páginas, modificaciones, PAU u obras municipales. La
[tramitación de obras](https://aytoconsuegra.es/obras-y-urbanismo-tramitacion/)
ofrece solicitudes de licencia, no evidencia de concesión, y queda excluida.
No se ha verificado un registro público de licencias concedidas. Sus métodos
devuelven vacío con estado `disabled`.

El inventario implementado es una página única sin controles de paginación
observados. Se procesan todas sus entradas, sin límite de registros. Si aparecen
controles de paginación, otra lista NNSS ambigua, documentos sin título, tipos o
hosts no revisados, o desaparecen el texto o todos los planos, el parser falla
explícitamente antes de escribir una extracción nueva. El refresco es una
instantánea completa; no utiliza una fecha incremental ni borra datos remotos.

## Geometría

`geometry_status: unavailable`. La fuente enlaza planos documentales de
alineaciones, zonificación y término municipal. No se ha verificado una capa
vectorial o servicio GIS asociable al instrumento, ni se han georreferenciado
o vectorizado los PDF. Coordenadas y geometría nulas; `publication_ready: false`.
No se atribuye al instrumento la coordenada del centro del municipio.

## Validación y evidencias locales

`python -m unittest municipio.test_consuegra -v`: tres pruebas, con subcasos
de rechazo de cambios de fuente/paginación, agrupación y deduplicación documental,
procedencia, fechas nulas, carga del manifest, anotación semántica, refresco
estable y licencias deshabilitadas. Todas pasan.

Extracción real mediante `load_manifest` y `load_portal_adapter`, invocando
`backfill_proyectos`: **1 registro**, seis entradas documentales. Se conserva
la anotación de la política compartida, sin modificarla. Evidencias locales:
`evidence/proyectos.jsonl`, `evidence/validation.json`, HTML municipal utilizado
por el adaptador, páginas de descubrimiento y capturas de los seis visores con
sus resultados HTTP en `evidence/document-checks.json`. Las evidencias no forman
parte de los cuatro archivos fuente entregados.

Manifest con planificación y licencias deshabilitadas, y sin jitter geográfico.
No se ha ejecutado publicación, despliegue, sincronización ni acceso a bases de datos.
