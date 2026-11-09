# A Illa de Arousa — INE 36901, Pontevedra

Investigación y extracción en vivo: 2026-11-09.

## Fuentes oficiales y descubrimiento

- Página oficial del Concello: https://www.ailladearousa.es/urbanismo-obras-e-deportes/
  Su enlace «NORMATIVA URBANÍSTICA DO CONCELLO DE A ILLA DE AROUSA» apunta al
  inventario SIOTUGA para `idconcello=36901` en el antiguo dominio
  `www.planeamentourbanistico.xunta.es`. El adaptador usa el servicio actual
  HTTPS de la Xunta, no el portal turístico comercial `ailladearousa.com`.
- Inventario actual: https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36901
- Estado general: https://siotuga.xunta.gal/siotuga/urb?lang=es_ES
  Identifica INE 36901, «Illa de Arousa, A», PXOM aprobado el 2002-02-14.
- Funcionamiento público del inventario:
  https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0
  La interfaz consulta `assets/inventario/query_document.php` por POST, con
  `id=36901` e `idclase`; cada ficha se obtiene por POST en
  `assets/inventario/getIOTPU.php`, con `iddoc` e `idp=0`.
  Se utiliza el campo de sesión pública de la propia página; no requiere
  autenticación ni credenciales.

La página municipal contiene consultas y formularios de licencias. No son
concesiones ni expedientes y no se extraen. La propuesta genérica de elaborar
un proyecto de peatonalización tampoco constituye un proyecto documentado.

## Cobertura y agrupación

Extracción completa de las dos secciones seleccionadas del inventario actual:
`idclase=14` (planeamiento general, 4 fichas) e `idclase=13` (planeamiento de
desarrollo, 20 fichas). **24 instrumentos, 448 enlaces documentales**.

Incluye el PXOM (22846), CE PXOM (28116), las modificaciones PXOM Nº 5 (27835)
y NSP NUM 3 (26180), planes especiales de reforma interior de las áreas de
reparto y estudios de detalle. Se conservan las denominaciones literales de la
Xunta, incluso abreviaturas antiguas. No se reinterpreta NSP NUM 3 como otro
instrumento basándose en fuentes secundarias.

Cada `id` oficial identifica una ficha/instrumento; memorias, normativa,
catálogo y planos permanecen en `documentos`, con sus títulos, grupos,
identificadores, URLs y procedencia. Una corrección o modificación con ficha
propia se mantiene como instrumento separado del plan base. No se crea un
proyecto por archivo ni se fusionan todos los planes especiales.

Cuatro estudios de detalle, ids 27587, 26044, 25877 y 25876, tienen ficha y
metadatos reales pero `elementos=null`. Se conservan con `documentos=[]` y
`document_status=no_components_in_source`; no se inventan descargas.

La API devuelve arrays completos; la paginación DataTables es local al
navegador. Se recorren todos los elementos sin limitar a la primera página.
Un sobre paginado inesperado, errores HTTP, discrepancias de identidad,
municipio o fechas y un inventario completamente vacío provocan error. La
salida se escribe después de completar todas las fichas. La actualización es
una nueva instantánea completa, sin cursor temporal.

Cobertura parcial del municipio: no incluye el histórico (`idclase=16`, cuatro
fichas observadas), delimitaciones rurales (`idclase=18`, respuesta nula
observada), instrumentos territoriales supramunicipales, planes en tramitación,
el tablón de la sede, contratos, obras públicas o todas las licencias. No se
afirma que estas 24 fichas sean todos los proyectos del Concello ni que las
fechas antiguas prueben actividad reciente.

## Fechas, vigencia y geometría

`fechaaddef` se conserva en `fecha_aprob`. `fechadog`, `fechabop` y
`fechanormativabop` se conservan por separado en campos de publicación del DOG,
BOP y normativa. `fecha`, `fecha_publicacion` genérica y `fecha_acuerdo` quedan
nulas: no se transforma una publicación en acuerdo. No se deducen fechas de
los nombres de archivo. El PXOM, por ejemplo, tiene aprobación 2002-02-14,
DOG 2002-02-27 y BOP/normativa 2002-03-07. Las aprobaciones observadas abarcan
2002-02-14 a 2017-09-27.

Las incidencias jurídicas se conservan sin interpretar. La pertenencia al
inventario no certifica vigencia actual; no se inventa fase de ejecución.
El contenido de los 448 documentos no se analiza. Los planos raster no se
convierten en coordenadas. `lat`, `lon` y `geometry` son nulos,
`publication_ready=false`, `geocode.jitter_missing=false`, licencias y
programación desactivadas.

## Validación reproducible y evidencia local

Runtime usado (sin instalaciones ni cambios de dependencias):
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_a_illa_de_arousa -v` con ese
runtime: **9 pruebas correctas**. Comprueban agrupación, procedencia, fechas,
ausencia explícita de descargas, aislamiento municipal, rechazo de cambios de
API y URLs ajenas, recorrido completo de 25 fichas simuladas, carga del
manifest y licencias desactivadas. Los fragmentos del parser proceden de la
respuesta real del PXOM, reducida a tres componentes; las identidades de la
prueba de volumen son exclusivamente datos sintéticos de test.

Ejecución real de `AIllaDeArousaAyuntamientoAdapter.backfill_proyectos` con
`config={"evidence_dir": "evidence"}` y salida `evidence/proyectos.jsonl`.
`evidence/validation.json` registra conteos, limitaciones, fuentes y resultado
de pruebas. `live-class-*.json` y `live-detail-*.json` contienen las respuestas
reales de ambas secciones y de las 24 fichas; también se conservan HTML de
Urbanismo, SIOTUGA y su JavaScript público.

Comprobación documental de muestra: GET
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/ILLADEAROUSA/documents/0804no001.pdf
respondió HTTP 200, `application/pdf`, firma `%PDF-1.5`. Se conservaron solo
los primeros 8192 bytes en `evidence/document-sample.bin`. Esto verifica esa
descarga, no la disponibilidad individual de los otros 447 enlaces.

La evidencia es local y queda fuera de los cuatro archivos fuente solicitados.
No se ha accedido a bases de datos ni se ha publicado o desplegado nada.
