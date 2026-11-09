# Carranque — Toledo — INE 45038

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y alcance

Fuente implementada: [Urbanismo del Ayuntamiento de Carranque](https://www.carranque.es/portal/urbanismo/).
La página municipal publica dos inventarios WordPress Download Manager: «Normas Subsidiarias» y «Planos». El primero contiene 14 fichas: siete capítulos NNSS, cuatro ordenanzas de zona, Suelo No Urbanizable, anexos y documento completo. El segundo contiene una cuadrícula de distribución, diez planos de clasificación/calificación (P01 y P03–P11) y una ortofoto. No se inventa un P02 ausente.

Se extrae **un instrumento real, Normas Subsidiarias de Carranque**, agrupando los 14 documentos normativos y los 11 documentos cartográficos publicados junto a ellos: **25 enlaces**, conservando título, sección, URL de ficha estable y URL de procedencia. La relación de la cartografía se basa en su publicación en esta misma página; no se verifica su edición o correspondencia jurídica exacta con el texto completo. La ortofoto se excluye por ser material de referencia, sin constituir otro instrumento. Los capítulos, ordenanzas zonales, anexos y hojas de plano tampoco se convierten en proyectos independientes.

Se verificaron las fichas [NNSS completo](https://www.carranque.es/portal/download/nnss-completo/) y [Generalidades](https://www.carranque.es/portal/download/nnss-1-generalidades/). La ficha completa anuncia 107,11 MB; no se descarga ese paquete grande. En Generalidades se siguió el enlace municipal de descarga: HTTP 200, `application/pdf`, firma `%PDF-`. Se guardaron únicamente los primeros 1024 bytes. Los enlaces con parámetros temporales del gestor no se usan como identidad persistente; se conservan las fichas navegables.

También se consultó la [sede electrónica municipal](https://carranque.sedipualba.es/), enlazada desde la web del Ayuntamiento. La portada identifica Ayuntamiento de Carranque, Toledo, y ofrece tablón y transparencia. No se recorrió su archivo ni se acreditó un registro público de licencias concedidas. No forman parte de la extracción. Formularios, ordenanzas fiscales, anuncios de contratación y noticias no se interpretan como concesiones ni proyectos.

## Cobertura y semántica

La cobertura es parcial: inventario documental municipal disponible en la fecha de consulta. No es un histórico completo de obras, modificaciones del planeamiento, licencias o expedientes administrativos. No acredita vigencia jurídica consolidada, aprobación o ejecución de las NNSS. No se afirma que incluya todas las modificaciones posteriores ni se usa la presencia del documento completo para darlo por consolidado.

Las fechas de creación y actualización del CMS (por ejemplo, 27 de febrero de 2024 en fichas NNSS) no son fechas de acuerdo, aprobación ni publicación oficial de normativa. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas. No se deduce fase ni se añaden coordenadas municipales como ubicación del instrumento. `geometry_status: unavailable` y `publication_ready: false`; sin geocodificación artificial. Licencias y programación desactivadas en el manifest.

Ambas listas WPDM muestran sus contenedores de paginación vacíos; todos sus elementos están en el HTML capturado. No se aplica un límite de registros. Si aparecen controles de paginación, el parser aborta expresamente para impedir una extracción truncada. También falla si faltan las secciones, el paquete NNSS completo o la cartografía, o cambia la procedencia municipal de los documentos. Los documentos nuevos que no encajen en las familias de nombres seleccionadas quedan fuera del alcance declarado.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_carranque -v` — **7 pruebas correctas**. Comprueban agrupación, filtros de exclusión, metadatos desconocidos, rechazo de HTML incompleto, paginación y procedencias externas, deduplicación, refresco completo y configuración del manifest. Los fixtures HTML están incluidos en el fichero de pruebas; no dependen de capturas locales.

Ejecución real: `CarranqueAyuntamientoAdapter('carranque', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))` — **1 registro, 25 documentos**. Se usó una petición real del adaptador, sin mocks. Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo.html`, fichas `nnss-completo.html` y `nnss-1-generalidades.html`, `sede.html` y `nnss-generalidades-prefix.bin`. La validación conserva recuento, fecha de observación UTC, fuentes, limitaciones y resultado de la comprobación PDF. Sin dependencias añadidas ni modificaciones compartidas; sin publicación ni acceso a bases de datos.
