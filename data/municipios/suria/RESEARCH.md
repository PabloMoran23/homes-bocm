# Súria — Barcelona — INE 08274

Investigación y extracción real: 9 de noviembre de 2026. Un único adaptador municipal, sin licencias, geocodificación, publicación ni tareas programadas.

## Fuentes oficiales descubiertas y alcance

- https://www.suria.cat/urbanisme — área municipal; competencias y enlace al POUM. No se convierte la página de servicios en un proyecto.
- https://www.suria.cat/poum — descripción municipal del proceso de elaboración del Pla d'Ordenació Urbanística Municipal de Súria. Exige una narrativa específica del municipio para evitar producir registros desde mera navegación.
- https://www.suria.cat/poum/documents2/ — inventario documental del mismo instrumento: 18 enlaces, correspondientes a materiales de 2015, 2022 y 2023 (avances, propuestas, participación, dictamen y cartel). Todos se agrupan en un registro POUM; el dictamen sobre participación no es aprobación del plan. La fecha de actualización CMS, las fechas de nombres de archivo y los años de los apartados no se convierten en fechas de aprobación/publicación.
- https://www.suria.cat/urbanisme/normativa-urbanistica/normes-subsidiaries-de-planejament/ — inventario de las Normes Subsidiàries: 11 enlaces PDF (índice, ocho títulos, disposiciones transitorias y un enlace alternativo de título VIII), agrupados en un segundo instrumento. Se conserva también la consulta RPUC como enlace relacionado; no se presenta como un expediente específico. La narrativa identifica aprobación definitiva de 21/01/2003 y publicación DOGC 3877 de 06/05/2003. Se distinguen `fecha_aprob` y `fecha_publicacion`; no se inventa una fecha de acuerdo adicional. La propia fuente advierte que las modificaciones posteriores deben consultarse en oficinas municipales o RPUC. Es una versión histórica publicada, no un texto consolidado actualizado.
- https://www.suria.cat/seu-electronica1/197-transparencia/urbanisme-obres-publiques-i-medi-ambient redirige a la sede en `suria.eadministracio.cat`. Se capturó su índice: planeamiento (107), obras e infraestructuras (35), además de otras categorías. Su navegación usa callbacks Wicket/AJAX y enlaces `#`; este adaptador no los recorre ni convierte esas categorías o contadores en proyectos. Esta exclusión es una limitación de cobertura, no una afirmación de que no existan más expedientes públicos.
- El área municipal enlaza el tablón urbanístico de la sede y el perfil de contratación. No se extraen formularios de solicitudes, anuncios de contratación ni noticias como licencias concedidas.

## Método y límites

Se consultan tres páginas municipales en cada ejecución: descripción POUM y dos inventarios completos de documentos. Las listas están en `#pepe article` y no presentan paginación en la captura. No se aplica límite al número de documentos ni se corta una lista; la aparición de controles de paginación/continuación causa error para revisión. También se rechazan contenedores ausentes, inventarios vacíos y narrativas de aprobación cambiadas o sin fechas explícitas. El límite de tamaño HTTP causa error, nunca truncamiento aceptado.

Identificadores estables por instrumento; los documentos se deduplican por URL normalizada dentro del instrumento. Se conservan etiqueta contextual, página de procedencia y `source_href` literal. Los enlaces antiguos HTTP y dobles barras se normalizan a HTTPS municipal, conservando el original. El documento gráfico/cartel queda unido al POUM, sin convertirse en actuación separada. No se descargan ni interpretan todos los PDF: los enlaces prueban procedencia documental y no garantizan disponibilidad de cada archivo. El enlace alternativo antiguo de título VIII se retiene tal como está publicado; no se afirma haberlo validado.

Cobertura parcial de planeamiento municipal, sin inventario exhaustivo de actuaciones actuales, modificaciones RPUC, obras públicas o licencias. El POUM no tiene aprobación definitiva inferida. Sin geometría verificada, coordenadas nulas y `publication_ready: false` en ambos registros. La política compartida clasifica ambos como categoría desconocida; se conserva su resultado, sin inventar uso residencial o localización.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_suria -v
```

Ocho pruebas correctas: agrupación y aislamiento documental, deduplicación y procedencia, semántica de fechas, ausencia de geometrías, rechazo de fuentes vacías/cambiadas, paginación, enlaces externos, refresco completo, licencias desactivadas y carga del manifest/adapter.

Ejecución real mediante `load_manifest('suria')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `portal.config.evidence_dir` fijado localmente a `evidence/`. Resultado: **2 registros**, con **18 y 11 documentos** respectivamente. La primera prueba detectó que los saltos de línea de la narrativa rompían la expresión regular; se normalizó el espacio y se repitieron las pruebas y la extracción real satisfactoriamente.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de fuentes y descubrimiento. Dos muestras documentales (primeros 1024 bytes de un PDF de cada instrumento) dieron HTTP 200, `application/pdf` y firma `%PDF`; URLs finales y resultados están en validation.json. La validación registra `live_records`, `source_urls`, limitaciones, recuentos de documentos y resultado de pruebas. No se ejecuta ningún pipeline de publicación o base de datos.
