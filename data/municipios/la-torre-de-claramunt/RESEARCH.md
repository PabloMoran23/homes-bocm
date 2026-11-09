# La Torre de Claramunt — investigación y alcance

Verificación en vivo: 2026-11-09. Municipio INE **08286**, Barcelona,
Catalunya. Adaptador único: `LaTorreDeClaramuntAyuntamientoAdapter`.

## Fuentes oficiales e inventario actual

- [Urbanisme municipal](https://www.latorredeclaramunt.cat/ajuntament/urbanisme/):
  ofrece las NNSS vigentes y un PDF del texto refundido. La página identifica
  explícitamente el acuerdo de la Comisión de Urbanismo de Barcelona del
  **15-10-1986**. La portada del PDF confirma ese origen y advierte que incorpora
  modificaciones aprobadas definitivamente. Se obtiene **un instrumento**, no
  un registro por artículo, licencia mencionada o modificación no individualizada.
- [Inventario catalán de Urbanisme en la sede de transparencia](https://seu-e.cat/ca/web/latorredeclaramunt/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme):
  enlaza categorías de planeamiento, normativa, geografía, planes territoriales,
  estudios ambientales, la exposición pública de la Font del Camaró y DUPROCIM.
  Se descubren los enlaces directos con título EXPOSICIÓ PÚBLICA o PROJECTE;
  se exige una memoria valorada/proyecto técnico adjunto, además del título.
  La consulta actual no muestra paginación. El adaptador recorre todos los enlaces
  seleccionados sin límite de registros y falla si detecta controles de paginación,
  detalles incompletos o una respuesta sin contenido reconocible.
- [Exposición pública de renovación de la red de la Font del Camaró, primera fase](https://seu-e.cat/ca/web/latorredeclaramunt/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/exposicio-publica-renovacio-de-la-xarxa-de-la-font-del-camaro-1era-fase-226):
  **una obra física**, con dos documentos agrupados: certificado de Secretaría y
  memoria valorada. El PDF técnico tiene 43 páginas y su portada identifica la
  renovación de la red. Ambos enlaces completos y sus títulos quedan en
  `documentos`, con `source_url` que identifica la página de procedencia.
- [Categoría Planejament urbanístic](https://seu-e.cat/ca/web/latorredeclaramunt/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic):
  el HTML enlaza al buscador general antiguo del RPUC
  (`http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=load`),
  no a un inventario municipal descargable. No se afirma haber extraído RPUC.
- [DUPROCIM](https://seu-e.cat/ca/web/latorredeclaramunt/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/proteccio-civil-municipal.-duprocim-227):
  inspeccionado y excluido por ser un plan operativo de protección civil, sin obra
  física ni ordenación urbanística. No se convierten categorías, formularios,
  anuncios de contratación ni noticias en proyectos o licencias concedidas.

## Fechas y procedencia

`fecha_aprob=1986-10-15` corresponde únicamente al instrumento base NNSS.
La actualización municipal de **30.11.2020** se conserva como
`fecha_actualizacion_fuente`, sin convertirla en publicación o acuerdo. El texto
refundido no demuestra la fecha individual de cada modificación posterior.

La ficha de la obra dice `Actualització: 07/07/2026`; se conserva con ese significado.
Publicación, acuerdo y aprobación quedan nulos en el registro de la obra: este
adaptador lee HTML y conserva los PDF enlazados, pero no extrae sus fechas.
La revisión manual del certificado local identifica expediente **1405/2026**,
sesión **26/06/2026**, firmas de 01/07/2026 y emisión de 07/07/2026. Además,
el apartado de propuesta de acuerdo contiene una referencia incongruente a
actuación forestal y medioambiental. Por eso no se deduce de la etiqueta del
certificado una fase de aprobación de la obra. La fase extraída es la exposición
pública que declara la ficha. Las fechas del certificado tampoco se confunden
con publicación ni actualización del portal.

## Cobertura y limitaciones

Resultado comprobado: **2 registros reales**, NNSS y obra de Font del Camaró,
con tres documentos enlazados. Es una instantánea parcial del contenido actual
seleccionado, sin histórico completo de obras, modificaciones urbanísticas,
archivo de noticias, licencias o RPUC. Las actualizaciones vuelven a extraer la
instantánea completa con identificadores estables y escritura atómica; no
simulan un registro incremental ni eliminan duplicados por título.

No se proporcionan coordenadas, centroides o geometrías inventadas.
`publication_ready=false`; programación, licencias y jitter están desactivados.
El anotador compartido de entidades informa dos categorías desconocidas; no se
cambian las políticas compartidas ni se afirma preparación para publicación.

## Validación reproducible y evidencia local

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_la_torre_de_claramunt -v` usando ese
runtime, **8 pruebas correctas**. Cubren identificación municipal, fechas,
agrupación de documentos, exclusión de formularios y DUPROCIM, rechazo de
certificados/anuncios sin memoria técnica, cambios de estructura, paginación,
actualización sin duplicados y conservación de salida ante fallo.

Extracción real realizada cargando el manifiesto con `load_manifest`, resolviendo
el adaptador con `load_portal_adapter` y ejecutando `backfill_proyectos` hacia
`evidence/proyectos.jsonl`. `evidence/validation.json` contiene `live_records=2`,
URLs de páginas y documentos, limitaciones, fecha de consulta y resultado del
anotador de entidades. `evidence/live-sources/` conserva el HTML obtenido por el
propio adaptador. También se guardaron las páginas de investigación, `nnss.pdf`,
`camaro-0.pdf` (certificado), `camaro-1.pdf` (memoria) y extractos de texto para
inspección. La evidencia es local y no forma parte de los cuatro archivos fuente.
