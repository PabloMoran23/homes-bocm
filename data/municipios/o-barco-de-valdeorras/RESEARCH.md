# O Barco de Valdeorras — INE 32009, Ourense

Verificado mediante HTTP y extracción real el 2026-11-07. Cobertura parcial:
instrumentos urbanísticos del inventario municipal oficial SIOTUGA, mantenido por
la Xunta de Galicia. No es un inventario de obras ejecutadas ni de licencias.

## Descubrimiento y procedencia

- Web municipal: https://www.concellodobarco.gal/gl/
- Urbanismo: https://www.concellodobarco.gal/gl/os-servizos/urbanismo
  enlaza «PXOM do Barco» al anterior dominio planeamentourbanistico.xunta.es
  y la información urbanística a la antigua sede electrónica .org.
- Plataforma actual: https://siotuga.xunta.gal/siotuga/urb contiene la fila
  INE 32009, Barco de Valdeorras, O, PXOM aprobado el 2003-06-27, y enlaza
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=32009
- Manual oficial: https://siotuga.xunta.gal/siotuga/axuda explica las secciones
  del inventario y su cobertura de instrumentos con aprobación definitiva.
- Portal municipal actual: https://sede.concellodobarco.gal/transparency
  ofrece categorías mediante Wicket. La antigua ruta de Urbanismo redirige a
  una ruta .gal que devuelve 404. No se trata ese resultado como inventario vacío.

El JavaScript público `assets/inventario/controls.min.js` revela los endpoints:
`POST assets/inventario/query_document.php`, parámetros id=32009 e idclase=14
(planeamiento general) y 13 (desarrollo); `POST assets/inventario/getIOTPU.php`,
parámetros iddoc, idp=0 y lang=gl_ES. Se obtiene el valor anti-CSRF anónimo de
la página pública dentro de una sesión HTTP nueva, sin autenticación.
El resultado de consulta es un array completo; DataTables pagina en el cliente.
Se consumen todos los elementos sin límite de filas ni corte de página. Un cambio
a respuesta paginada/envoltorio produce error explícito. Se deduplica por ID oficial,
rechazando colisiones contradictorias. Cada ficha se verifica contra el municipio
y el ID solicitado, además de las fechas del inventario.

## Resultado y semántica

49 instrumentos reales: 15 de clase 14 y 34 de clase 13. Fechas de aprobación
entre 1987-09-29 y 2022-09-01. El inventario actual puede tener retrasos; estas
fechas no prueban ausencia de instrumentos posteriores. Ejemplos: PXOM (22579),
modificaciones puntuales y planes parciales/especiales/estudios de detalle.
Los 834 enlaces a componentes PDF/JPG se agrupan en 38 instrumentos, conservando
sus títulos, grupos e identificadores. Las otras 11 fichas identifican instrumentos
pero no exponen componentes: `documentos_status=unavailable_in_source`. No se
inventan enlaces ni se presentan componentes documentales como proyectos separados.
Se ha descargado y comprobado como PDF el índice del PXOM (0419me001.pdf, HTTP 200).
No se ha descargado ni comprobado la disponibilidad individual de los 834 enlaces.

`fecha_aprob` procede exclusivamente de `fechaaddef`, aprobación definitiva según
el contrato de la fuente. `fecha_acuerdo`, `fecha` y `fecha_publicacion` son nulas:
no se deduce una fecha municipal de publicación o acuerdo. Las fechas BOP, DOG y
BOP normativa están separadas en `publicaciones`, con su campo original. También
se retienen fechas brutas, incidencias jurídicas y fechas de texto refundido.
Cinco instrumentos tienen alguna fecha de publicación anterior a la aprobación;
se conservan sin corregirlas y con advertencia, sin inferir que sean concesiones.
El estado vigente individual no se presume ni se convierte `tipo` en `fase`.

## Límites

Se cubren íntegramente los arrays de las dos clases seleccionadas, no todo el
urbanismo municipal: se excluyen secciones independientes de ordenación territorial,
planeamiento histórico y delimitaciones rurales; también expedientes pendientes,
obras municipales, actas y anuncios de exposición pública en otras fuentes. Por
ejemplo, la búsqueda descubre documentación municipal PERI 7.1 de 2024, fuera de
este inventario consultado; no se afirma cobertura total ni actualidad jurídica.
No se recogen noticias, anuncios de contratación, formularios ni licencias concedidas.
Los métodos de actualización refrescan la instantánea completa; no existe cursor.
Fallos HTTP, JSON o de identidad abortan antes de reemplazar proyectos.jsonl.

La política compartida `entity_policy` clasifica los 49 como `pendiente` y reporta
`unknown_entity_spike`: estos registros tienen ID oficial de catálogo, pero la
fuente no proporciona número de expediente en los campos consultados. No se
inventa un expediente para eludir esa política. Requieren revisión posterior;
`publication_ready=false` para todos. No se modifica la política compartida.

## Geometría

geometry_status: unavailable

El WMS oficial responde y enumera capas cuyos nombres contienen IDs SIOTUGA:
https://siotuga.xunta.gal/siotuga/ws?codine=32009&SERVICE=WMS&REQUEST=GetCapabilities
Por ejemplo, `_32009_PXOM_200306_AD_1DEL_22579`. Se conserva una captura de
capacidades. No se extraen entidades vectoriales, polígonos ni centroides de ese
servicio de visualización; las coordenadas y geometrías permanecen nulas.
No se usan coordenadas municipales como ubicación de instrumentos ni jitter.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
`PYTHONDONTWRITEBYTECODE=1 <runtime> -m unittest municipio.test_o_barco_de_valdeorras -v`
comprueba fechas y anomalías, agrupación, procedencia, identidad, arrays completos
con más de 100 filas, duplicados, cambio de esquema, documentos ausentes, carga
por registry y licencias deshabilitadas. Cuatro pruebas pasan.

La extracción real se ejecutó mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir']='evidence'`. Timeout HTTP 40 s, pausa
0,15 s entre consultas. `evidence/validation.json` contiene conteos, URLs y límites;
las respuestas de inventario y las 49 fichas se conservan comprimidas en evidence/,
junto a las páginas de descubrimiento, JavaScript, capacidades y PDF de muestra.
La captura HTML del inventario omite el valor anti-CSRF público. Evidencia local,
no destinada a commit. Agenda y licencias deshabilitadas; sin publicación.
