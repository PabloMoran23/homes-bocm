# El Cuervo de Sevilla — INE 41903, provincia de Sevilla

Investigación y extracción real: 8 de noviembre de 2026. Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente implementada y unidad de registro

[Indicador municipal 50: PGOU, mapas y planos](https://transparencia.elcuervodesevilla.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00004/).

El título del indicador dice PGOU, pero las colecciones concretas identifican `normas-subsidiarias`. Se extrae **un instrumento real**, las Normas Subsidiarias de Planeamiento de El Cuervo de Sevilla, agrupando **62 documentos**: ocho de documentación escrita, cuatro del estudio de impacto ambiental, 38 planos de ordenación y 12 planos de información. Entre ellos figuran los seis libros normativos, la memoria de ordenación, la memoria justificativa, los capítulos e índice ambientales y planos de clasificación del suelo, equipamientos y estructura territorial. Los 50 planos se sirven como GIF bajo `IMG-50-`; los documentos escritos y ambientales como PDF bajo `IND-50-`. No son 62 proyectos independientes.

Cada documento conserva su título literal, URL, sección y todas las páginas del inventario en que se encontró. La identidad del instrumento permanece estable entre actualizaciones. Se excluye el catálogo de bienes protegidos que aparece fuera de las colecciones NNSS: no se ha demostrado su relación documental exacta con este instrumento.

## Paginación y errores

Se recorren todos los enlaces `pagegalleryfiles-*` descubiertos, sin cortar resultados. La ejecución visitó siete URLs: página base, páginas 1–4 de la galería de ordenación (`pagegalleryfiles-3-1`) y páginas 1–2 de información (`pagegalleryfiles-4-1`). Las páginas 1 redundantes se conservan en la procedencia. Se deduplican documentos por URL, nunca por título. Las otras secciones se muestran completas en cada página.

El adaptador exige encabezado del indicador, documentos y las cuatro secciones del instrumento. Rechaza destinos, parámetros o redirecciones inesperados. Un fallo HTTP, cambio incompatible de contenido o límite defensivo de 1.000 páginas produce error antes de escribir la salida; nunca devuelve ese recorrido incompleto como válido. `update_proyectos` vuelve a obtener el inventario entero, sin afirmar una cobertura histórica incremental.

## Descubrimiento y cobertura parcial

También se consultó [Normativa de Alcaldía](https://elcuervodesevilla.es/es/alcaldia/normativa/), que devuelve HTTP 200 y mezcla documentación de planeamiento, obras, ordenanzas, selección de personal, subvenciones y anuncios. No se convierten indiscriminadamente esos enlaces en proyectos ni licencias. Se conserva una captura local de esta página para investigación, pero no forma parte del scraper implementado.

La búsqueda oficial localizó [la consulta pública del avance del PBOM](https://elcuervodesevilla.es/es/Comunicacion/noticias/Se-abre-el-tramite-de-consulta-publica-del-avance-del-PBOM-y-el-Documento-Inicial-Estrategico/). El anuncio distingue expresamente la aprobación del avance a efectos de tramitación de una aprobación inicial o definitiva. No se mezcla ese nuevo instrumento con las NNSS. Las rutas candidatas del indicador 53 con `indicadores-de-transparencia` y `indicadores-detransparencia`, terminadas en `53.-Se-publican-y-se-mantienen-publicados-las-modificacionesaprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00004/`, devolvieron HTTP 404 al verificarlas. Esto limita la cobertura municipal; no impide extraer el instrumento documental real del indicador 50.

No se cubren PBOM, otras modificaciones, obras públicas ni un registro de licencias concedidas. Una solicitud de licencia, adjudicación o noticia genérica no constituye aquí un registro extraído. No se afirma que las NNSS estén consolidadas o que su documentación publicada recoja todas las modificaciones posteriores.

## Fechas y geometría

No se extrae ninguna fecha de publicación, acuerdo o aprobación de este inventario: esos tres campos quedan nulos. El título del indicador y metadatos del CMS no acreditan una fecha ni fase de aprobación. Los planos se conservan como enlaces documentales; no se ha extraído geometría verificable de ellos. Coordenadas y geometría nulas, `publication_ready: false`, `geometry_status: unavailable`. El manifiesto desactiva licencias, ejecución programada y jitter de coordenadas.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_el_cuervo_de_sevilla -v`

Seis pruebas: filtrado y procedencia PDF/GIF; agrupación y recorrido de galerías encadenadas con duplicados; rechazo de fuentes vacías o incompletas; preservación de la salida anterior ante fallo en página posterior; validación de paginación; manifiesto y licencias desactivadas.

Extracción real mediante `ElCuervoDeSevillaAyuntamientoAdapter(config={'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: un registro con 62 documentos y siete páginas de procedencia. Evidencia local no versionada: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/tests.txt`, capturas `inventory-*.html` con sus URLs y dos documentos de muestra (PDF y GIF). La validación registra HTTP, destino final, MIME y firma de las dos muestras descargadas. Los otros 60 archivos se conservan como enlaces inventariados; no se afirma que se hayan descargado o analizado íntegramente. No se utilizan base de datos, geocodificación ni publicación.
