# Cee — INE 15023, A Coruña

Verificación: 2026-11-08. Adaptador de la ficha oficial de Urbanismo del Concello.
Se revisaron antes de implementarlo `municipio/manifest.py`, el contrato
`municipio/adapters/portal.py`, los ejemplos Hernani y Manlleu y sus manifiestos.

## Fuentes e inventarios descubiertos

- https://cee.gal/gl/servizos/urbanismo-obras-publicas/ — HTTP 200, página
  temática de Urbanismo con secciones Normas subsidiarias y PXOM. Fuente de la
  extracción. No se utiliza una noticia aislada como inventario.
- https://sede.cee.gal/sxc/es/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
  — HTTP 200. «Plan de Urbanismo» remite al antiguo dominio de SIOTUGA.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15023
  — enlace actual de Normas subsidiarias en la página municipal. HTTP 200, pero
  el HTML recibido contiene el buscador de municipios sin expedientes. No se
  infiere que Cee carezca de planeamiento ni se extrae una ficha vacía.

## Extracción y semántica

La ejecución real produce **1 instrumento: Plan Xeral de Ordenación Municipal do
concello de Cee**, con **4 documentos** del expediente ambiental AAE 2476,
identificado en sus enlaces. Ese número no se presenta como número del expediente
municipal. Se retienen las URLs originales completas y su procedencia municipal.
La fase «en elaboración» procede de la narrativa de la ficha consultada, sin
interpretarla como aprobación ni comprobar un avance posterior de tramitación.

Los anexos son Documento de consultas (03/02/2022), Borrador do plan y Documento
inicial estratéxico (14/01/2022), y Documento de alcance (04/04/2022). Estas fechas
se guardan exclusivamente como `fecha_documento`, con su semántica de fecha
rotulada por el inventario. Publicación, acuerdo y aprobación del instrumento
permanecen nulos: la ficha no acredita esas fechas. Los cuatro anexos no generan
cuatro proyectos. Enlaces duplicados se agrupan por URL.

Los enlaces de cmatv.xunta.gal redirigen a medioambiente.xunta.gal. Su descarga
falló por validación del certificado TLS en este entorno. No se desactivó TLS;
`contenido_verificado: false` distingue el enlace publicado de un documento cuyo
contenido se haya descargado y examinado. La ficha municipal sigue siendo una
fuente usable del instrumento y su inventario documental.

Cobertura **parcial**: únicamente el PXOM descrito en esta página municipal.
No abarca el inventario histórico de Normas subsidiarias, modificaciones,
planeamiento de desarrollo ni el conjunto de obras públicas. Noticias,
licitaciones, ordenanzas y formularios no se convierten en proyectos o licencias.
No se ha verificado un registro público de licencias concedidas; los métodos de
licencias escriben cero registros y devuelven estado `disabled`.

## Paginación, actualización y geometría

La página temática no muestra paginación. Se lee la sección completa del PXOM,
incluyendo todos sus enlaces, hasta el siguiente encabezado. La actualización
relee la ficha íntegra; no filtra por fechas ni aplica límites de registros.
El extractor falla ante paginación reconocible, ausencia del instrumento,
documentación mínima incompleta, mezcla de identificadores, procedencia no
revisada o cambio de narrativa de fase. Un cambio estructural requiere revisión.

`geometry_status: unavailable`. La ficha enlaza documentos y SIOTUGA, sin geometría
vectorial verificada vinculada al PXOM. No se descargó o vectorizó cartografía del
ZIP ni se asignó un punto al municipio como ubicación del instrumento. Geometría,
latitud y longitud nulas; `publication_ready: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_cee -v`: cinco pruebas offline de agrupación,
fechas, procedencia, cambios de estructura/fase, paginación, manifiesto y métodos.
Extracción live con `load_manifest('cee')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, captura de
la ficha `urbanismo.html`, `siotuga.html`, `sede.html` y `source_checks.json` con
resultados HTTP y errores de los documentos. La configuración opcional
`portal.config.evidence_dir` permite guardar la captura desde el propio adaptador.
Evidencia fuera de los cuatro archivos fuente solicitados y sin commit.

`schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Sin publicación, despliegue ni acceso a bases de datos.
