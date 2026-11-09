# Fuente de Cantos — Badajoz — INE 06052

Investigación y extracción real: 9 de noviembre de 2026. Municipio de Extremadura; no confundir con Fuentecantos (Soria).

## Descubrimiento y alcance

La web oficial https://www.fuentedecantos.eu/ enlaza el archivo de noticias, bandos, edictos, perfil del contratante y la sede https://fuentedecantos.sedelectronica.es/info.0. La portada no ofrece un inventario específico de planeamiento. Los formularios y ordenanzas fiscales no acreditan licencias concedidas. El perfil del contratante y las ofertas de empleo tampoco constituyen por sí solos proyectos urbanísticos.

Se consultaron los inventarios REST públicos WordPress de páginas y entradas buscando modificaciones. El primero no devolvió páginas; el segundo incluía empleo, patrimonio y una publicación de planeamiento. Se comprobó después la consulta temática exacta de entradas:

https://www.fuentedecantos.eu/wp-json/wp/v2/posts?search=Normas+Subsidiarias&per_page=100&page=1&orderby=id&order=asc

El servidor declaró `X-WP-Total: 1` y `X-WP-TotalPages: 1`. Este es el inventario vivo que extrae el adaptador, no una lista literal precargada de expedientes. Recorre todas las páginas declaradas; comprueba el total, los identificadores repetidos y los cambios de totales durante el recorrido. Un inventario vacío, incompleto, sin instrumentos reconocibles o sin documentos utilizables produce error antes de sobrescribir la salida. No hay truncamiento por un máximo arbitrario de páginas.

## Registro documentado

[Publicación municipal del 21 de septiembre de 2021](https://www.fuentedecantos.eu/2021/09/21/anuncio-12/): «ANUNCIO-Modificación puntual Nº 01/2021 de las Normas Subsidiarias Municipales que se detalla a continuación». El texto convoca información pública durante 45 días. Incluye nueve documentos: anuncio DOE, planos 1 a 6, memoria y anexos, documento ambiental estratégico. Constituyen **un instrumento**, con los nueve enlaces conservados en `documentos` y su página de procedencia en cada documento. Las publicaciones posteriores de la misma modificación se agrupan por número/año y conservan sus fechas, textos y enlaces en `publicaciones`. Modificaciones distintas se mantienen separadas.

Ejemplos de documentos originales:

- https://www.fuentedecantos.eu/wp-content/uploads/2021/09/anuncio-doe-1.pdf
- https://www.fuentedecantos.eu/wp-content/uploads/2021/09/20210617_Memoria-y-Anexos-MP-1.2021-1.pdf
- https://www.fuentedecantos.eu/wp-content/uploads/2021/09/Documento-Ambiental-Estrategica-MP-1.2021.pdf

No se limita a transformar la noticia en proyecto: selecciona una modificación numerada de las Normas Subsidiarias con documentación técnica municipal. El tipo exige ese título específico y documentos PDF oficiales. Se excluyen solicitudes, tasas, licitaciones y noticias ajenas al planeamiento.

También se localizó https://www.fuentedecantos.eu/2025/11/25/plan-de-recuperacion-transformacion-y-resiliencia-dus/ sobre instalaciones energéticas municipales DUS 5000. Está fuera del archivo temático implementado y **no se cuenta** entre los resultados. Tampoco se extraen anuncios de contratación como si fueran proyectos o licencias.

## Semántica y límites

`fecha_publicacion: 2021-09-21` procede del campo `date` de WordPress, no de la última modificación del CMS, del directorio de subida ni del nombre de un PDF. Se conserva el trámite de información pública en la publicación que lo afirma. No se atribuyen fecha de acuerdo, aprobación inicial/definitiva, vigencia jurídica ni fase actual del instrumento. El contenido completo de los PDF no se analiza automáticamente. Una fecha incluida en el nombre de un documento no se usa como aprobación.

Cobertura parcial: entradas públicas WordPress que coinciden con «Normas Subsidiarias» y cumplen el patrón de modificación puntual numerada. No pretende cubrir todas las obras, todo el planeamiento, la sede, actas o expedientes administrativos. Una entrada archivada accesible actualmente no implica un procedimiento activo. No se ha verificado un registro de licencias concedidas: `licencias.enabled=false`. No hay coordenadas ni geometría inventadas; `geometry_status=unavailable`, `publication_ready=false`, `geocode.jitter_missing=false`, `schedule.enabled=false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_fuente_de_cantos -v`, **8 pruebas correctas**. Cubren selección y exclusiones, fechas, ausencia de aprobación/geometría inventada, agrupación y separación de instrumentos, documentos obligatorios, origen oficial, recorrido de dos páginas, rechazo de páginas vacías/repetidas/cambiantes, conservación de una salida anterior al fallar, manifest y licencias desactivadas.

Extracción real mediante `load_manifest('fuente-de-cantos')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`. Resultado: **1 registro real, 9 documentos**, política de entidades correcta. Los nueve documentos respondieron HTTP 200 y presentaron firma `%PDF-`; solo se capturaron sus primeros 1024 bytes, sin afirmar lectura íntegra ni verificación de sus acuerdos.

Evidencia local, excluida del commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (conteo, URLs consultadas, comprobaciones y limitaciones), `evidence/planning-page-1.json`, `evidence/home.html`, consultas de descubrimiento `evidence/search-{posts,pages}.json`, prefijos `evidence/document-*.pdf.prefix` y resultado de la política de entidades `evidence/proyectos.entities.json`. No se ejecutaron publicación, geocodificación, sincronizaciones ni acceso a bases de datos.
