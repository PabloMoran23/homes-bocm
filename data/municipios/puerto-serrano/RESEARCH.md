# Puerto Serrano — Cádiz — INE 11029

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

La web del Ayuntamiento enlaza expresamente el portal de transparencia provincial con entidadId=2001:
https://www.puertoserrano.es/ayuntamiento/ordenanzas-y-otras-normas-locales/category/43-pgou.html

Su categoría PGOU contiene únicamente «Ordenanza_de_Clasificacion_de_la_Unidad_de_Ejecucion_7», download=153. Se capturó la página y el PDF escaneado, pero no se incorpora esta ordenanza como proyecto sin verificar su contenido. Los trámites de solicitud de licencia de la sede no son concesiones. No se utilizan anuncios de contratación, agregadores comerciales ni noticias como expedientes.

Inventario seleccionado: sección 7 (Medioambiente, urbanística y vivienda), entidad 2001, del catálogo oficial de información pública:
https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=2001

El adapter conserva en `inventory_url` la consulta completa que abre esa sección mediante los parámetros públicos de Liferay. Deben conservarse todos sus parámetros de navegación; una consulta abreviada no siempre muestra la sección. La sección muestra un instrumento: **ESTUDIO DE DETALLE PLAZA DIAMANTINO**, indicadorId=20474. No hay paginación visible ni controles de páginas en el inventario observado. Se rechaza explícitamente cualquier paginación detectada, en vez de devolver silenciosamente solo la primera página.

PDF técnico enlazado desde la ficha:
https://gobiernoabierto.dipucadiz.es/uploads/indicadores/1753439516290.pdf

Descarga real: HTTP 200, application/pdf, 8.922.693 bytes, firma `%PDF-1.4`. El PDF consta de 36 páginas escaneadas; la primera se renderizó e inspeccionó visualmente. Identifica el Estudio de Detalle «Plaza Diamantino», Ayuntamiento de Puerto Serrano como propietario/promotor, expediente SAM 1783/23 y fecha documental marzo de 2024. Contiene una diligencia de aprobación definitiva en sesión plenaria manuscrita; el parser no transcribe esa fecha ni interpreta automáticamente sellos. No se incorpora ninguna fecha de aprobación precargada.

## Cobertura y semántica

**Una extracción viva, un instrumento real, un documento asociado.** Cobertura parcial del inventario actual de transparencia, no un censo de obras, un histórico completo de planeamiento ni prueba de vigencia jurídica actual de todos los instrumentos. Solo se aceptan títulos de instrumentos/proyectos urbanísticos identificables dentro del contenedor de inventario. Cada indicador produce un registro estable; sus distribuciones documentales se agrupan y deduplican en `documentos`, conservando URL y procedencia de la ficha. Se comprueban el identificador de entidad y la correspondencia del título entre inventario y ficha.

La creación de la ficha, 25/07/2025 12:31, se conserva como `fecha_creacion_ficha`, no como publicación del acuerdo, fecha de acuerdo ni aprobación. No se infieren fases, fechas, coordenadas o geometría. `publication_ready=false`, `geometry_status=unavailable`. Licencias, programación y jitter geográfico están desactivados en el manifest. El método incremental refresca el inventario actual completo; no reconstruye elementos retirados. Cambios de contenedor, inventario vacío, discrepancias de título, documentos ausentes o enlaces fuera del host oficial provocan error antes de reemplazar la salida.

## Verificación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_puerto_serrano -v`: seis pruebas correctas. Cubren exclusión de formularios/licitaciones/noticias, deduplicación, agrupación y aislamiento documental, semántica temporal, rechazo de entidad incorrecta y paginación, fallos de ficha y conservación de salida ante error.
- Ejecución real mediante `load_manifest('puerto-serrano')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: un registro. Incluye la anotación de política compartida del cargador, sin editar código compartido.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, inventario `urbanismo.html`, ficha `diamantino.html`, PDF `diamantino.pdf`, primera página renderizada `diamantino-page1.png`; también capturas exploratorias `transparencia.html`, `pgou.html`, `ue7.pdf`. Los archivos de evidencia no forman parte de los cuatro archivos fuente entregados.

No se han utilizado bases de datos, credenciales, publicación ni despliegue. No se requieren dependencias nuevas.
