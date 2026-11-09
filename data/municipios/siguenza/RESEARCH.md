# Sigüenza — Guadalajara — INE 19257

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único de proyectos de inventario municipal; licencias desactivadas.

## Fuente oficial actual y alcance

La portada https://siguenza.es/ enlaza **URBANISMO** a https://siguenza.es/?page_id=628 . Su contenido municipal enumera dos instrumentos concretos:

- INFORMACIÓN PÚBLICA: DOCUMENTO PARA APROBACION INICIAL DEL PLAN ESPECIAL DE REHABILITACIÓN DEL CASCO HISTÓRICO → https://siguenza.es/pagina/8/87/
- BORRADOR PARA CONSULTA PREVIA DEL PLAN ESPECIAL DEL PAISAJE DEL MUNICIPIO DE SIGÜENZA → https://siguenza.es/pagina/8/88/

El inventario devuelve HTTP 200 y contiene los dos títulos y enlaces. **Ambas fichas antiguas devuelven HTTP 404**, también al comprobar el dominio www. Se extraen dos entradas reales del inventario público vigente como página web; no se afirma vigencia jurídica de los instrumentos, disponibilidad del texto íntegro ni aprobación. La URL principal de cada registro es la página accesible que acredita la entrada. Los enlaces documentales originales, su procedencia y el estado HTTP se conservan dentro de `documents`.

La búsqueda oficial indexada también localizó los PDF de normativa, memoria justificativa y documento ambiental del PECH bajo el directorio antiguo `archivosUser/Plan%20Especial%20Rehabilitacion%20Casco%20Historico/`. La comprobación directa de https://www.siguenza.es/archivosUser/Plan%20Especial%20Rehabilitacion%20Casco%20Historico/Normas_Siguenza_17_12.20.pdf devolvió 404. No se usan resultados indexados como documentos descargados ni fechas del buscador como fechas municipales. Esa respuesta se conserva en `evidence/pech-normativa-response.bin`.

También se inspeccionaron https://siguenza.es/?page_id=495 (Obras y Mantenimiento: descripción genérica de servicios y medios) y https://siguenza.es/?page_id=969 (Documentos de interés: autoliquidaciones). No son inventarios de obras concretas ni licencias concedidas. Las alusiones de Urbanismo a 70 viviendas, peatonalización y revitalización de La Alameda no identifican expedientes/documentos concretos y no generan registros.

## Extracción y semántica

Se analiza `main .entry-content`, se exige la cabecera Urbanismo y se seleccionan exclusivamente los enlaces con rótulos documentales de planes especiales para aprobación inicial o consulta previa. El contenido del registro procede del HTML vivo, sin registros precargados. El identificador deriva del título normalizado del instrumento, agrupando enlaces de un mismo plan. Si una ficha vuelve a estar disponible, se conservan todos sus adjuntos PDF/ZIP/RAR/7Z municipales dentro del instrumento correspondiente, con su URL de procedencia; no se crean proyectos por cada archivo. No se interpreta el cuerpo de los documentos ni se presume que una ficha accesible tenga aprobación.

`estado_documental` conserva el sentido del rótulo del inventario; “documento para aprobación inicial” no se transforma en acuerdo de aprobación. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. No se deducen fechas del CMS, cabeceras HTTP o nombres de archivos. Sin coordenadas, geometrías o geocodificación. `publication_ready: false` y `geometry_status: unavailable` en los dos registros.

Cobertura **parcial**, limitada a las entradas documentales de esta página, sin pretensión de censo histórico ni registro completo de planeamiento municipal. El inventario inspeccionado no muestra paginación. Si aparecen controles de paginación el adaptador falla explícitamente para evitar truncamientos. La desaparición del contenedor, de la cabecera o de todos los instrumentos también provoca error. Solo 404/410 se admiten como indisponibilidad documentada de una ficha; otros errores HTTP se propagan. La actualización vuelve a obtener el inventario completo, sin seguimiento histórico de bajas.

## Validación reproducible y evidencia local

Runtime preinstalado usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_siguenza -v`: **6 tests correctos**, comprobando selección semántica, rechazo de formularios/licitaciones/noticias, agrupación, aislamiento de documentos entre instrumentos, ausencia de fechas inventadas, errores ante paginación/cambios de estructura y tratamiento de fichas 404.

Se cargó el manifest mediante `load_manifest('siguenza')`, se comprobaron INE/provincia y las tres desactivaciones exigidas, y se ejecutó `SiguenzaAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))` con `config={'capture_dir': 'evidence/captures'}`. Resultado real: **2 registros**. `evidence/validation.json` contiene `live_records`, `source_urls`, momento de extracción y limitaciones. Las capturas de inventario y fichas incluyen URL solicitada/final, estado HTTP y tipo de contenido. Se guardaron además las páginas de Obras y Documentos de interés inspeccionadas. La evidencia permanece local y no forma parte de los cuatro archivos fuente entregados.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`. No se ejecutó publicación, sincronización, base de datos ni geocodificación.
