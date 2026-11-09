# Valencia de Alcántara — INE 10203, Cáceres, Extremadura

Consulta y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes descubiertas y selección

- Web municipal oficial: https://www.valenciadealcantara.es/ . Identifica el ayuntamiento, su sede, transparencia y perfil del contratante. No ofrece en la portada un inventario estructurado de licencias concedidas; formularios, eventos y noticias generales no se convierten en proyectos.
- Sede enlazada: https://valenciadealcantara.sedelectronica.es/info.0 . El resultado de búsqueda muestra trámites urbanísticos, no evidencia de concesiones. No se implementa extracción de licencias.
- Inventario oficial autonómico: https://sitex.juntaex.es/SITEX/planeamiento . El selector identifica **Valencia de Alcántara con identificador interno 491**, que no es el código INE. El INE 10203 corresponde al municipio de Cáceres y figura también en el enlace AEMET municipal de la web del ayuntamiento. No confundir con Alcántara, Valencia capital ni otros municipios llamados Valencia.
- El HTML público del selector usa un observador Ajax que envía `municipioseleccionado=491` mediante **POST** a https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat con cabeceras `X-Requested-With: XMLHttpRequest` y `X-Update: planeamientosindex`. GET no reproduce la selección y devuelve una lista vacía. Es una consulta pública, sin autenticación ni cambios en el servicio.
- Cada entrada enlaza mediante `addTab` a `/SITEX/ptofiguras/viewsigcat/<id>`. El adaptador interpreta el identificador, sin ejecutar JavaScript. Captura el inventario y verifica en cada ficha el ámbito municipal y el estado.

El inventario vivo observado contiene **66 entradas**, incluida una figura territorial supramunicipal. Se extraen **las 31 figuras municipales marcadas Vigente**, con todas sus fichas: revisión de Normas Subsidiarias, 27 modificaciones, dos planes parciales (SR-5 y SR-1) y Estudio de Detalle UE-23. Ejemplos concretos:

- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/34967 — revisión NNSS.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/33400 — modificación relativa a recalificación y creación de U.E. SR-8; referencia NNSS.R-001.M-036, con denominación municipal nº 26. Se mantienen los dos identificadores tal como aparecen, sin corregir la numeración.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39717 — ampliación de suelo urbano, nueva UA-25.
- https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/32111 — estudio de detalle UE-23.

Se excluyen de forma expresa las entradas En trámite, No vigente y los planes territoriales. Por ejemplo, la ficha 40023 de la modificación nº 39 tiene estado No vigente y un trámite de caducidad; no se presenta como instrumento aprobado vigente. El PGM en trámite tampoco se infiere como aprobado a partir de la contratación de su redacción. La fuente efectiva es la Junta de Extremadura (`source: junta_extremadura` en registros); el manifest usa el canal `ayuntamiento` del contrato existente, no `bocm_legacy`.

## Cobertura, documentos y fechas

La cobertura es parcial: planeamiento vigente según SITEX al consultar, no todas las obras, todo el histórico ni todas las actuaciones municipales. Se recorren **todas** las fichas del subconjunto vigente, sin límite de filas ni selección de primeras páginas. El árbol viene completo en una respuesta; no se ha observado paginación. Si aparece un paginador o enlace de siguiente página, el parser falla en lugar de entregar una extracción parcial silenciosa. Una ficha fallida o incoherente impide reemplazar la salida anterior.

Un registro por identificador de figura SITEX. `referencia` y `expediente_grupo` conservan la referencia de instrumento del inventario (no un número de licencia municipal). Los documentos del contenedor específico `archivosplaneamiento<id>` se agrupan en `documentos`, con URL, título de descarga, tipo `documento_tecnico` y procedencia de la ficha. No se toman formularios de la navegación. Los enlaces a boletines asociados a trámites se conservan como `publicacion_tramite`; algunos son enlaces al número completo del diario, no a un anuncio individual. Los trámites mantienen sus fechas, denominaciones y URLs en `tramites`. No se confunden recursos administrativos con archivos técnicos.

Resultado real: **31 registros, 24 enlaces técnicos y 85 enlaces de publicaciones de trámites**. Varias fichas no ofrecen archivos técnicos, pero sí identidad de instrumento y datos de tramitación. Se conservan así, sin fabricar documentos faltantes. No se descargan ni interpretan masivamente los PDF. Comprobación puntual de https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/1730 (Memoria informativa de la revisión NNSS): HTTP 200, `application/octet-stream`, primeros 1024 bytes con firma `%PDF-1.5`. No acredita el contenido completo ni la disponibilidad de todas las descargas.

`fecha_aprob` se toma solo de **Fecha AD** y `fecha_publicacion` solo de **Fecha de publicación AD**. Por ejemplo, la figura 33400 diferencia 25/06/2009 y 15/10/2009. Las fechas de aprobación inicial y provisional, acuerdos, depósito y publicaciones se retienen en trámites; no se generaliza ninguna de ellas como acuerdo global. `fecha` y `fecha_acuerdo` quedan nulas. No se deduce una fase de `tipo` ni se afirma ejecución física. Vigente es el estado declarado por el inventario, no una comprobación jurídica independiente.

Sin coordenadas, geometría ni geocodificación deducidas. `publication_ready: false`, `geometry_status: unavailable`. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados. Actualización como snapshot completo del mismo subconjunto; no usa una marca incremental que pierda modificaciones retrospectivas.

## Verificación reproducible y evidencia local

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_valencia_de_alcantara -v` — seis pruebas correctas. Cubren identidad y exclusiones, rechazo de paginación y cambios de estructura/estado/municipio, separación de fechas, fechas desconocidas, agrupación y aislamiento de documentos, carga por manifest y conservación de salida anterior ante fallo.

Extracción real mediante `load_manifest('valencia-de-alcantara')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. Pasa por la política compartida de entidades. `evidence/validation.json` contiene recuento, URLs fuente, método POST, limitaciones, informe de entidades y comprobación de descarga. `evidence/inventory.html`, `detail-*.html`, `municipal.html`, `sitex.html`, `parser-tests.txt`, `document-check.json` y `document-1730.prefix` conservan las capturas locales. Los archivos de evidencia no se incorporan a los cuatro archivos fuente solicitados.
