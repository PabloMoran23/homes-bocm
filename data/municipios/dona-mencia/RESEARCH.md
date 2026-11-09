# Doña Mencía — Córdoba — INE 14022

Investigación y extracción real: 9 de noviembre de 2026.

## Inventarios oficiales revisados

- [Urbanismo](https://donamencia.es/urbanismo-2/): índice de las tres secciones de planeamiento. La primera petición HTTP respondió 403; la fuente de planeamiento general funcionó con el agente de usuario explícito empleado por el adaptador.
- [Urbanismo General](https://donamencia.es/urbanismo-general/): fuente implementada. Contiene dos pestañas, «PGOU» y «Modificación puntual 1 PGOU», con 14 y 3 enlaces respectivamente. Se extraen **2 instrumentos**, conservando **17 documentos**, sin convertir cada plano o memoria en un proyecto independiente. El PGOU contiene normas, memoria, catálogo, fichas, EIA, índice y planos. La modificación contiene el documento de modificación, resumen ejecutivo y propuesta de aprobación definitiva.
- [Urbanismo Detallada](https://donamencia.es/urbanismo-detallada/): cinco pestañas de categorías vacías en la revisión actual. No se extraen categorías como proyectos.
- [Urbanismo Complementarios](https://donamencia.es/urbanismo-complementarios/): pestaña de estudios de detalle vacía. No se fabrica un estudio a partir del rótulo.

Cobertura parcial: inventario publicado de planeamiento general, no registro histórico exhaustivo, ni inventario de obras en ejecución, ni concesiones de licencias. No se incorporan formularios, licitaciones o noticias. Las secciones vacías se documentan como observación de investigación; el adaptador solo consulta Urbanismo General.

## Extracción y procedencia

El parser relaciona cada etiqueta de `.et_pb_tabs_controls` con su panel `.et_pb_all_tabs > .et_pb_tab` dentro del contenido municipal. Conserva todos los enlaces del panel y sus títulos literales en `documentos`, con `source_url` para la página de procedencia. Los enlaces repetidos se deduplican dentro de cada instrumento. Los identificadores dependen de la etiqueta del instrumento, no del orden de los documentos.

Las 14 URLs del PGOU son enlaces municipales que redirigen a PDFs; las tres URLs de la modificación enlazan directamente a PDFs. La validación real siguió los 17 enlaces: HTTP 200 y firma `%PDF-` en todos. `evidence/validation.json` conserva las URLs iniciales y finales, tipo de contenido y comprobación de firma. Por ejemplo, el enlace municipal de normas redirige a `https://donamencia.es/wp-content/uploads/2021/11/NORMAS-URBANISTICAS_TEXTO-REFUNDIDO_MOD-PGOU-DONA-MENCIA.pdf`. Los registros conservan la URL publicada, no reemplazan silenciosamente su procedencia por el destino de la redirección. Se capturaron los primeros 1024 bytes de cada PDF; esta comprobación no analiza su contenido completo.

La fuente general observada es una página con dos pestañas, sin paginación. Se leen ambos paneles aunque uno esté oculto inicialmente. Si aparecen enlaces de paginación, pestañas desconocidas, paneles vacíos, enlaces externos o una estructura incompatible, se produce error antes de reemplazar la salida. No hay límite de registros ni truncamiento silencioso. La actualización vuelve a leer el inventario entero para detectar cambios documentales bajo la misma etiqueta.

## Fechas y límites semánticos

No se extraen fechas: el CMS y las carpetas de subida no acreditan publicación, acuerdo ni aprobación. «Propuesta de aprobación definitiva» se conserva como título documental y no como prueba de aprobación. No se afirma vigencia, fase de ejecución ni concesión de licencia. No hay coordenadas ni geometría; `geometry_status: unavailable` y `publication_ready: false`. El manifest desactiva licencias, programación y desplazamientos aleatorios de geocodificación.

## Verificación reproducible

Runtime preinstalado utilizado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_dona_mencia -v
```

Tres pruebas locales cubren agrupación, deduplicación, aislamiento de documentos, procedencia, identificadores estables, ausencia de fechas y geometría inventadas, rechazo de estructura inválida y paginación, carga del manifest, escritura, refresco, licencias desactivadas y redirecciones inesperadas. Resultado: correcto.

La ejecución real cargó el manifest con `load_manifest('dona-mencia')`, construyó el adaptador mediante `load_portal_adapter` y ejecutó `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `config['capture_dir']='evidence'`. Resultado: 2 registros y 17 documentos. La anotación compartida de entidades reportó dos entidades desconocidas, sin error; no se ha impuesto una categoría física a instrumentos de planeamiento.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo-general.html`, capturas de las secciones vacías y prefijos PDF. No se han utilizado bases de datos ni pasos de publicación; la evidencia no forma parte de los cuatro archivos fuente entregados.
