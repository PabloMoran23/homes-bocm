# Brenes — INE 41018, Sevilla, Andalucía

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales y alcance

La portada municipal https://www.aytobrenes.es/es/index.html enlaza Hábitat Urbano y Limpieza, https://www.aytobrenes.es/es/temas/habitat-urbano/, cuyo enlace «Ver todos» conduce al inventario utilizado:

https://www.aytobrenes.es/es/temas/habitat-urbano/noticias-tema/

Se recorre el listado completo observado (3 noticias), descargando cada detalle. No se observaron controles de paginación. Si aparecen paginación o enlaces de continuación, el parser falla y exige revisión; no emite silenciosamente una primera página parcial. Un cambio de estructura, fallo HTTP o desaparición de todas las actuaciones reconocidas provoca error antes de sustituir el JSONL.

La noticia descriptiva oficial utilizada es:

https://www.aytobrenes.es/es/temas/habitat-urbano/noticias-tema/Brenes-invertira-mas-de-700.000-euros-en-la-primera-de-fase-de-reconversion-del-antiguo-mercado-de-abastos/

Publicada el **21/11/2024**, describe dos actuaciones físicas previstas y sus objetivos: remodelación del Parque del Bodegón junto al arroyo Buenavista, y reforma/rehabilitación del antiguo Mercado de Abastos de la calle Cuadra y González para usos sociales, culturales y de emprendimiento. La noticia vincula las inversiones a los programas provinciales Más Sevilla y Sevilla 107 y menciona para el mercado la redacción del proyecto y ejecución de la primera fase. Son propuestas de inversión publicadas por el Ayuntamiento: **no se acredita que exista proyecto técnico aprobado, adjudicación, comienzo ni finalización**. El registro del parque utiliza solo su párrafo; el mercado reúne sus párrafos de rehabilitación, primera fase e instalaciones, sin mezclar ambos proyectos. Los títulos proceden del texto publicado. La cifra del titular no se convierte en importe adjudicado.

Se excluyen las otras dos noticias: reivindicación de mejora de carreteras de la comarca y reunión sobre adecuación de edificaciones irregulares. No acreditan actuaciones municipales concretas. Tampoco se extraen formularios ni anuncios de contratación como proyectos o licencias.

## Otras fuentes investigadas y límites

La transparencia https://www.aytobrenes.es/es/transparencia redirige a https://brenes.sedelectronica.es/transparency. La solicitud Python produjo un error de verificación del certificado, también con el almacén CA del sistema. No se deshabilitó la verificación TLS ni se accedió a áreas privadas.

La búsqueda pública localizó el inventario provincial https://3web.dipusevilla.es/planeamiento/planes.htm y el avance histórico del PGOU https://3web.dipusevilla.es/planeamiento/CD_BRENES/18PGAVANCE.htm. Las solicitudes directas agotaron el tiempo de conexión tanto por HTTPS como, para el avance, HTTP. No se convierten los resultados del buscador ni los documentos no descargados en registros. No se afirma cobertura del PGOU, sus modificaciones ni vigencia urbanística actual. La web regional también devuelve resoluciones históricas; no se ha implementado un segundo scraper regional.

La cobertura es **parcial y deliberadamente limitada a las dos actuaciones físicas reconocidas en el contenido revisado**. No constituye inventario exhaustivo de obras ni planeamiento, ni detecta automáticamente otros tipos de actuación futuros. Una actualización relee las mismas fuentes públicas y agrupa publicaciones con la misma actuación por identificador estable, reteniendo los enlaces documentales. La noticia municipal es la fuente documental compartida por las dos actuaciones, no una resolución ni memoria técnica. No había PDF técnico enlazado en el cuerpo revisado; las fotografías de la galería no se presentan como documentos técnicos.

## Semántica y ejecución

`fecha_publicacion` es la fecha de la noticia, nunca fecha de acuerdo o aprobación. No se añaden coordenadas, fechas de acuerdo, geometría, fases de ejecución ni licencias. `tipo=actuacion_fisica_prevista` y `estado_fuente` dejan explícito el carácter de propuesta. `publication_ready=false` y `geometry_status=unavailable`. El manifiesto desactiva licencias, programación y jitter.

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- Pruebas: `python -m unittest municipio.test_brenes -v` — 9 correctas. Verifican selección semántica, separación de actuaciones, fechas, deduplicación, conservación de enlaces, errores de inventario, paginación y contrato del manifiesto.
- Extracción real: `load_manifest('brenes')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con capturas locales habilitadas mediante `capture_dir`.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML exploratorio y `evidence/live-captures/`. Resultado esperado de la comprobación: **2 registros reales procedentes de 1 noticia, tras examinar las 3 noticias del listado**.

Sin base de datos, publicación, despliegue, geocodificación ni cambios compartidos. Las evidencias son locales y no forman parte de los cuatro archivos fuente.
