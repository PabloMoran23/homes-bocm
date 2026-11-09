# Íscar — Valladolid — INE 47075

Investigación y extracción en vivo: 9 de noviembre de 2026. Se revisaron previamente `municipio/adapters/portal.py`, `municipio/manifest.py`, el registro de adaptadores y los ejemplos de Chipiona y Hernani. No se modifican componentes compartidos ni dependencias.

## Fuentes oficiales descubiertas

La [página municipal de Urbanismo](https://www.villadeiscar.es/areas/urbanismo-servicios-seguridad-ciudadana/urbanismo-2/) enlaza expresamente las Normas Urbanísticas Municipales al [Archivo de Planeamiento de la Junta, municipio 470750001](https://servicios.jcyl.es/PlanPublica/lplanes.plau?municipio=470750001). Se utiliza HTTPS para la misma URL enlazada por el Ayuntamiento en HTTP. El archivo identifica «ÍSCAR Código INE: 47075» y la provincia de los listados de ficheros es Valladolid. El selector `filtroSelDoc=TODOS` está marcado; `bIncluirHist` no está marcado. Es el inventario actual servido por PLAU, no una búsqueda de noticias ni un registro de licencias concedidas.

La [sede electrónica](https://iscar.sedelectronica.es/info.0) ofrece solicitudes y declaraciones responsables; estos trámites no acreditan concesiones y se excluyen. La noticia municipal sobre la reforma de las normas permitió contrastar la existencia de la modificación 1-2025, pero los registros se extraen del inventario y de sus listados documentales, no de noticias genéricas o anuncios de contratación.

## Resultado y unidad de registro

La ejecución del adaptador a través de `load_manifest` y `load_portal_adapter` produjo **8 instrumentos**, procedentes de **9 asientos PLAU**, con **68 enlaces de documentos**:

| Asientos PLAU | Instrumento | Publicación | Acuerdo | Documentos |
| --- | --- | --- | --- | --- |
| 301421 | Modificación 1-2025 de las NUM | 2026-03-13 | 2026-02-25 | 3 |
| 297393, 291410 | Modificación NUM, calle Nogal 27 / avenida San Miguel 90 | 2014-12-15 | 2014-09-24 | 24 |
| 291041 | Plan parcial sector 2C «El Molino 3» | 2014-08-12 | 2014-07-23 | 7 |
| 289193 | Modificación NUM, carretera CL-602, línea de edificación | 2013-02-26 | 2013-01-29 | 4 |
| 288396 | Modificación NUM, sector 2 «El Molino» | 2012-06-29 | 2012-05-29 | 12 |
| 284372 | Estudio de detalle, calle León s/n | 2008-10-24 | 2008-09-30 | 2 |
| 282916 | Modificación NUM, cubierta de plaza de toros y recalificación | 2006-03-08 | 2006-02-09 | 4 |
| 281930 | Normas Urbanísticas Municipales | 2003-07-03 | 2003-04-02 | 12 |

Cada listado `ldoc_files.do?cDocId=…` conserva los nombres y enlaces `openFichero.do?cFicheroId=…`. Se eliminan únicamente los identificadores de sesión de las URL. Los planos, carátulas y textos de un instrumento no generan proyectos separados. Los títulos originales, fechas, identificadores y enlaces de cada asiento se retienen en `entradas_fuente`.

Los asientos 297393 y 291410 resuelven al [mismo acto BOCYL](https://bocyl.jcyl.es/boletines/2014/12/15/pdf/BOCYL-D-15122014-13.pdf). Se descargó y leyó su primera página: acuerdo de 24 de septiembre de 2014, modificación de las NUM en las dos direcciones citadas, expediente CTU 79/12, eliminación de un tramo de viario. Por ello se agrupan por URL del acto individual, fecha de acuerdo y figura. El identificador de salida deriva de esa identidad, sin fijar registros precargados. Los demás instrumentos mantienen sus propios documentos. El estudio de detalle de 2008 resuelve a un índice diario del BOCYL, no a un acto individual; esta circunstancia se conserva como `boletin_alcance: indice_diario` en su asiento y ese índice nunca permite fusionar instrumentos. Las NUM de 2003 enlazan un acto individual HTML, no un PDF.

## Alcance y controles

`fecha_publicacion` y `fecha_acuerdo` se leen de sus columnas diferenciadas. No se introduce `fecha_aprob`, fecha genérica, fase ni fecha de ejecución. El adaptador no interpreta el contenido de todos los PDF ni certifica vigencia jurídica, concesión de licencia o ejecución física. Los proyectos aquí son instrumentos urbanísticos publicados; no un inventario completo de obras públicas, solicitudes o expedientes municipales.

El inventario observado contiene nueve filas en una sola página, con tamaño declarado de 15 y sin enlaces a páginas adicionales. No hay límite silencioso: cualquier enlace de paginación, offset positivo o página llena provoca un error explícito antes de escribir el resultado. Los listados de ficheros observados incluyen todos sus documentos en una página (uno contiene 23), sin controles de paginación; también se comprueban dichos controles. Cambios de municipio, estructura, fechas, categorías o ausencia de documentos provocan error. La salida se reemplaza de forma atómica al finalizar; `update_proyectos` rehace la instantánea actual, sin historia incremental de bajas.

No se infieren coordenadas. `publication_ready=false`, `geometry_status=unavailable`. El clasificador compartido informa ocho identidades pendientes (`insufficient_identity_evidence`): estos registros documentales no están aprobados para publicación. `licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`.

## Verificación y evidencia local

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `…/venv/bin/python -m unittest municipio.test_iscar -v`: **7 pruebas correctas**. Comprueban fechas independientes, identidad municipal, rechazo de datos vacíos y paginación, enlaces sin sesión, agrupación de duplicados, aislamiento de documentos, no agrupación por índice diario y opciones del manifest.
- Extracción real mediante `load_portal_adapter(load_manifest('iscar')).backfill_proyectos(...)`, pasando únicamente `portal.config.evidence_dir` en memoria para guardar capturas. Resultado: 8 registros, 9 asientos, 68 documentos. No se ejecutaron otros pasos del pipeline.
- `evidence/proyectos.jsonl`: registros reales con la anotación del clasificador compartido.
- `evidence/validation.json`: recuentos, URLs consultadas, límites y resultado de verificación.
- `evidence/inventory.html`, `documents-*.html`, `discovery-*.html`: capturas de inventario, listados y página municipal. Los `detail-*.html` corresponden a comprobaciones exploratorias.
- `evidence/boletin-297393.pdf`, `boletin-291410.pdf` y extracto textual: evidencia del acto compartido de 2014.
- `evidence/document-sample.json` y `sample-168176.pdf.prefix`: comprobación del documento técnico aprobado de 2026, HTTP 200, `application/pdf`, firma `%PDF-`, primeros 65.536 bytes. PLAU redirige al archivo público `http://www.jcyl.es/plaupdf/47/47075/301421/DOC.%20TECNICO%20APROBADO%20DEF_stamped.pdf`. Es una captura parcial expresamente identificada; no un PDF completo ni una validación masiva de los 68 enlaces.

La evidencia permanece local y no forma parte de los cuatro archivos fuente propuestos.
