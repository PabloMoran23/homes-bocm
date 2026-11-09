# Valle Gran Rey — INE 38049

Municipio: Valle Gran Rey, provincia de Santa Cruz de Tenerife, Canarias.
Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

- [Inventario de ordenación del territorio](https://transparencia.vallegranrey.es/ordenacion-del-territorio/): enlaza el inventario utilizado.
- [Información del plan de ordenación](https://transparencia.vallegranrey.es/ordenacion-del-territorio/plan-de-ordenacion/): fuente implementada. Tablas HTML completas, incluidos paneles plegados; cuatro filas municipales identificadas por PGO, además de planos, memorias y documentos del Plan Insular de La Gomera. No se observó paginación. Se recorren todas las tablas y se rechazan señales de paginación para evitar devolver solo la primera página si cambia el portal.
- [Obras públicas](https://transparencia.vallegranrey.es/obras-publicas/): índice de adjudicación y ejecución.
- [Obras en fase de adjudicación](https://transparencia.vallegranrey.es/obras-publicas/obras-publicas-fase-adjudicacion/): remite al perfil del contratante. No se convierte un anuncio de contratación en proyecto ejecutado o licencia concedida.
- [Obras en ejecución](https://transparencia.vallegranrey.es/obras-publicas/obras-publicas-fase-ejecucion-administracion/): publica PDF/TXT «Obras en ejecución 2025» y hojas ODS/XLSX «Obras Mayores 2025» y por trimestres. Se capturó el TXT, que contiene obras físicas de Taguluche, parque de Borbalán, bombeo de Arure y campo de fútbol de Playa del Inglés. Este inventario existe y es utilizable, pero **no está implementado por este adaptador**, cuya cobertura se limita al PGO. Las hojas de obras mayores no se interpretaron como un registro de licencias concedidas.
- [Sede electrónica](https://vallegranrey.sedelectronica.es/info.0): ofrece modelos y trámites. No se usan formularios como evidencia de concesiones.

## Unidad de extracción y documentos

Se devuelve **un instrumento real**, «Plan General de Ordenación de Valle Gran Rey», apoyado en cuatro entradas del inventario vivo:

1. Certificado acuerdo plenario inicio estudio ambiental para PGO.
2. Encargo a GESPLAN fase 1 Y 2 PGO.
3. Encargo a GESPLAN fase 3 PGO.
4. Propuesta de alcaldía al pleno para PGO.

Cada documento conserva su título literal, URL del inventario, texto de última actualización y todos sus formatos PDF/TXT. Las cuatro entradas se agrupan en un registro estable `valle-gran-rey-pgo`; los encargos de fases y sus versiones TXT no se cuentan como proyectos adicionales. Solo se emite el registro si existen documentos identificados en las tablas actuales; un listado vacío o sin fuentes PDF provoca error. No se precargan registros desde evidencia local.

La página contiene una descripción genérica que afirma que el Ayuntamiento no dispone de plan municipal y solo del insular. No se usa esa descripción para establecer vigencia: los documentos municipales posteriores acreditan un procedimiento de elaboración del nuevo PGO. Los documentos insulares y sus planos no se atribuyen al nuevo PGO ni se generan como proyectos municipales separados.

## Fechas, procedencia y límites

Las cuatro filas muestran **12 de Junio de 2026 bajo «Última actualización»**. Se conserva únicamente como `ultima_actualizacion_texto` del documento. No es una fecha de acuerdo ni acredita la publicación inicial.

La lectura del certificado TXT oficial identifica una sesión extraordinaria del **23/12/2025** relativa a solicitar el inicio de la evaluación ambiental estratégica del borrador y documento inicial estratégico, y cita el inicio del procedimiento de elaboración acordado el **28/05/2024**. No son fechas de aprobación definitiva del PGO. Los documentos de encargo acreditan trabajos de redacción, no una aprobación urbanística. El adaptador no extrae fechas del cuerpo de estos documentos ni asigna una fase actual a partir de ellos: deja ausentes `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob`.

Cobertura parcial del inventario documental municipal del nuevo PGO, sin prometer histórico completo, todos los instrumentos, obras, concesiones ni vigencia. No se extrae el Plan Insular ni se deducen coordenadas. `publication_ready: false`, `geometry_status: unavailable`; licencias, programación y jitter desactivados en manifest. Las limitaciones también aparecen en cada registro y en el resultado de extracción.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_valle_gran_rey -v` con ese runtime: **6 pruebas correctas**. Comprueban agrupación y deduplicación, exclusión de modelos y documentos insulares, separación de fechas, ausencia de fuentes, enlaces ajenos o sin PDF, rechazo de paginación, escritura de snapshot y preservación del archivo anterior ante errores, manifiesto y licencias desactivadas.

Extracción real: cargar `load_manifest('valle-gran-rey')`, construir `ValleGranReyAyuntamientoAdapter(manifest.slug, manifest.portal.config, manifest.portal.base_url)` y ejecutar `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: **1 registro, 4 documentos, 8 enlaces de formato**. Se descargaron los ocho enlaces descubiertos: HTTP 200, los cuatro PDF con cabecera `%PDF-`, los cuatro TXT con contenido referido a Valle Gran Rey.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`, `evidence/validation.json` (contador `live_records`, URLs, limitaciones y comprobaciones HTTP), `evidence/plan-de-ordenacion.html`, `evidence/documento-1.pdf` a `documento-4.pdf` y sus TXT. También se conservan capturas de los índices de territorio/obras y TXT de obras en ejecución para documentar el alcance excluido. No se accedió a bases de datos ni se ejecutó publicación, despliegue o sincronización.
