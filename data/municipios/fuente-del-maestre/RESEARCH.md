# Fuente del Maestre — investigación y cobertura

Revisión y extracción real: 2026-11-09. Municipio Fuente del Maestre, Badajoz,
Extremadura, INE **06054**. El identificador **79** de SITEX es una clave
interna del portal, no el código INE.

## Fuentes oficiales y descubrimiento

- Portal municipal: https://www.fuentedelmaestre.es/ . Su portada enlaza
  «Plan General Municipal Aprobación Provisional 2» mediante un acortador
  antiguo, además de sede, transparencia y perfil del contratante. No se
  confunden esos enlaces con proyectos ni con licencias concedidas. La variante
  sin www dio error de certificado TLS; la variante www funciona con verificación.
- Consulta oficial de planeamiento de la Junta de Extremadura:
  https://sitex.juntaex.es/SITEX/planeamiento . El selector identifica
  Fuente del Maestre con valor 79. El JavaScript de la propia página consulta
  `/SITEX/ptofiguras/listadoresultadossigcat` al cambiar el municipio.
- Inventario usado: https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat
  mediante **POST de consulta**, `municipioseleccionado=79`, cabecera
  `X-Requested-With: XMLHttpRequest`. Un GET con parámetros no filtra correctamente
  y no sirve como inventario. Se valida la opción seleccionada no vacía, pues el
  HTML conserva también una opción vacía marcada selected.
- PGM: https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37246 .
- Plan parcial SUNC-06/AU:
  https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40990 .
- Contraste oficial del acuerdo del PGM:
  https://doe.juntaex.es/otrosFormatos/html.php?anio=2023&doe=2370o&xml=2023AC0090
  y PDF enlazado por SITEX:
  https://doe.juntaex.es/pdfs/doe/2023/2370o/23AC0090.pdf .

## Extracción y semántica

Se recorre el árbol completo del inventario municipal; no se limita el número
 de resultados. Se incluyen únicamente instrumentos con estado SITEX `Vigente`
o `En trámite`. En la ejecución se encontraron **2** incluidos y **55**
`No vigente` excluidos de forma explícita. No hay paginación en la respuesta
revisada; el parser rechaza indicadores de paginación si aparecen, para evitar
una extracción parcial silenciosa. No se extrae el refundido raster como otro
instrumento, ni formularios o anuncios de contratación.

Cada ficha produce un registro estable por ID SITEX. Se conserva el tipo de
figura, referencia, estado literal, municipio, provincia y procedencia regional.
Se agrupan en `documentos` todos los enlaces de trámites y descargas de esa
ficha, con títulos y procedencia; las memorias y planos no generan proyectos
adicionales. Se conservan todos los trámites con su fecha y descripción.

- **Plan General Municipal**, PGM, estado `Vigente`: aprobación definitiva
  (`fecha_aprob`) 2023-04-27, publicación de aprobación definitiva
  (`fecha_publicacion`) 2023-12-13 y depósito 2023-11-29.
  **32 enlaces**: 23 descargas y 9 publicaciones de trámites.
- **Plan parcial de ordenación del sector SUNC-06/AU**, PGM.PPO-001:
  SITEX mantiene `En trámite`, aunque registra aprobación definitiva municipal
  2026-03-30 y depósito 2026-05-18. No tiene fecha de publicación definitiva
  informada, y por tanto se omite `fecha_publicacion`. Contiene **1 enlace** de
  información pública inicial en DOE, de 2025-09-12; esa fecha no se atribuye
  a la aprobación definitiva. No ofrece descargas técnicas en esta ficha.

No se infiere una fase a partir del tipo. No se emite fecha genérica,
coordenadas, centroides ni desplazamientos. `publication_ready=false` indica
que la extracción no constituye autorización de publicación. El cargador
compartido añade su clasificación de entidades sin cambiar sus fuentes.

## Límites y actualización

Cobertura parcial: inventario actual de planeamiento municipal en SITEX,
no todas las obras públicas, programas de ejecución, expedientes urbanísticos
ni todos los anuncios DOE. El histórico no vigente queda fuera. Las etiquetas
SITEX pueden ir retrasadas respecto a sus trámites; se conservan ambas sin
resolver artificialmente la discrepancia. Se inventarían enlaces sin asegurar
que cada documento esté disponible o que equivalga a la versión consolidada.
Se comprobó adicionalmente una descarga PDF real (`12397`, anexo de memoria)
y se capturó el HTML DOE del PGM. No se interpreta el contenido de los planos
como geometría. No hay registro verificado de licencias; extracción de licencias
desactivada y salida vacía. Programación desactivada.

Backfill y update reconstruyen la misma instantánea completa, sin marca temporal
que impida recoger cambios de estado o documentos. Un error de red, municipio,
estructura, fecha o paginación impide sustituir el archivo de salida anterior.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_fuente_del_maestre -v`:
**7 pruebas pasadas**. Verifican selección municipal, filtrado, paginación,
fechas separadas y ausentes, agrupación documental, rechazo de fichas ajenas,
contrato del adapter y carga del manifest.

Extracción real: `load_manifest('fuente-del-maestre')`, configurar
`manifest.portal.config['capture_dir']='evidence'`, cargar con
`load_portal_adapter(manifest)` y llamar
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local sin commit: `evidence/proyectos.jsonl` (2 registros),
`evidence/validation.json` (recuento, URLs y limitaciones),
`inventory-live.html`, `37246.html`, `40990.html`, `planeamiento.html`,
`municipal.html`, `doe-pgm.html` y `b054anexo.pdf` bajo `evidence/`.
