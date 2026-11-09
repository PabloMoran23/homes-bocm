# Carral — INE 15021, A Coruña

Investigación y ejecución en vivo: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

- [Inventario municipal del PXOM](https://carral.es/pxom-carral/): HTTP 200. Es un índice documental estructurado, no una noticia ni una contratación. Publica la versión de aprobación inicial del Plan Xeral de Ordenación Municipal de Carral. Contiene memoria, normativa, cartografía, evaluación ambiental, catálogo y expediente de tramitación, además de un anuncio de ampliación de exposición pública. La fuente advierte que la copia en papel diligenciada prevalece frente a la digital.
- [Área de Obras e Urbanismo](https://carral.es/concello/areas/obras-e-urbanismo/): HTTP 200; información general de servicios y trámites, sin inventario verificable de concesiones. Se conserva como captura de investigación, pero no genera registros.
- [Memoria enlazada por el índice](https://carral.es/wp-content/uploads/2016/04/I2-Cl-D01-MEMO.pdf): comprobación real HTTP 200, `application/pdf`, firma `%PDF-`. Se capturaron únicamente los primeros 1024 bytes. No se ha validado la disponibilidad ni leído íntegramente cada PDF.

La extracción produce **un instrumento con 222 enlaces PDF distintos**, conservando títulos, URL de cada documento, procedencia del índice y distinción entre documentación del plan y anuncio de tramitación. Se excluye el formulario de alegaciones. Los mapas y fragmentos del expediente no se convierten en proyectos independientes. No se crean registros desde formularios, servicios municipales, anuncios de contratación ni noticias.

Cobertura parcial: este índice del PXOM, no un censo completo de instrumentos, licencias u obras físicas. La disponibilidad actual de una versión histórica no demuestra que sea el planeamiento vigente ni la fase más reciente. No se afirma aprobación definitiva. `estado_documentado` describe exclusivamente la versión documental publicada.

## Semántica y mantenimiento

No se extraen fechas: las rutas de subida de 2016, la ampliación del plazo de alegaciones y los metadatos del CMS no son fechas de acuerdo del instrumento. No se inventan fechas de publicación, aprobación ni coordenadas. `publication_ready: false`, `geometry_status: unavailable`. Licencias, programación y jitter de geocodificación desactivados en el manifest.

El adaptador descarga el índice completo en cada actualización. No hay paginación observada en este índice de una sola página. Si aparece navegación de páginas detectada, falla expresamente y exige revisar el recorrido; no devuelve silenciosamente la primera página. También falla ante ausencia de contenido, cambio del municipio, falta de documentos esenciales o redirección fuera de la fuente. Deduplica documentos por URL y conserva todos los enlaces admitidos sin límite artificial. La cobertura documental se limita a enlaces PDF oficiales de Carral en el cuerpo del índice; no incluye menús o pie de página.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_carral -v`

Cinco pruebas correctas: agrupación, procedencia y exclusiones; ausencia de fechas/coordenadas inferidas; rechazo de vacíos/cambios; paginación explícita; carga del manifest y ejecución del contrato de actualización; preservación de salida anterior cuando falla el índice.

Extracción real mediante `load_portal_adapter(load_manifest('carral')).backfill_proyectos(...)`, con `capture_dir` local para guardar el HTML obtenido por el propio adaptador. Resultado: un registro, 222 documentos. El envoltorio compartido añadió su anotación de política de entidades (`status: ok`, entidad desconocida); no se atribuye promotor o adjudicatario sin evidencia.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/pxom.html`, `evidence/urbanismo.html` y `evidence/memoria-pdf-prefix.bin`. La validación recoge hora UTC, número de registros, fuentes, resultado de pruebas, huella de la captura y limitaciones. No se ejecutaron publicación, sincronización, bases de datos ni despliegues.
