# Alginet — INE 46031, Valencia

Investigación y extracción real: 7 de noviembre de 2026. Identidad contrastada con el [Registro de Entidades Locales de la Generalitat](https://www.entidadeslocales.gva.es/index.php?Itemid=9&id=46031&lang=es&option=com_reglocal_entloc&task=muestraEntidad&tipo=1): Alginet, provincia València/Valencia, código 46031.

## Descubrimiento y fuentes oficiales

La portada https://web.alginet.es/ enlaza Urbanisme → Tauler d'Anuncis. Los enlaces amigables `/tauler-danuncis-urbanisme/`, `/pgou/` y `/pla-general/` no son el transporte utilizado: el tablón devuelve HTTP 404 en esta sesión. La API pública WordPress sí sirve el contenido publicado y sus inventarios documentales:

- https://web.alginet.es/?rest_route=/wp/v2/pages&slug=pgou&per_page=100&page=1 — página 926, PGOU.
- https://web.alginet.es/?rest_route=/wp/v2/pages&slug=pla-general&per_page=100&page=1 — página 3449, Pla General Estructural.
- https://web.alginet.es/?rest_route=/wp/v2/pages&search=urban&per_page=100 — consulta de descubrimiento, conservada localmente; revela también tablón 934 y Llicències 940.

El tablón contiene documentación de Carrer 45, Calvari, modificación de red primaria, participación pública de telecomunicaciones y otros documentos históricos. Se revisó para delimitar cobertura, pero este adaptador extrae únicamente las dos páginas de inventario anteriores; no pretende inventariar todo el tablón ni los boletines autonómicos/provinciales. Los documentos de Los Lagos y los documentos PGE de otras versiones encontrados por buscador no se añaden a partir de resultados de búsqueda. Llicències publica solicitudes de obras mayores/menores y declaraciones responsables: no son licencias concedidas, por lo que la extracción de licencias queda desactivada.

## Extracción y unidad del registro

Resultado vivo: **6 instrumentos**, con **34 enlaces documentales**:

1. Pla General d'Urbanisme: PDF, trece planos y catálogo, agrupados en un registro (15 enlaces).
2. Modificación de usos del Teatre Moderno y Casa de la Cultura.
3. Modificación de normas urbanísticas, cuyo enlace especifica art. 6.7.2.b, uso de almacén.
4. Modificación puntual de normas del PGOU, documento publicado 24/07/2012.
5. Modificación segunda del Plan Parcial de Mejora U.E.R. 4.1.
6. Versión preliminar del Pla General Estructural: memorias, estudios, normas, fichas, planos, catálogo y evaluación ambiental agrupados (15 enlaces únicos).

Los títulos se leen del contenido actual del CMS; no son registros precargados. Los documentos conservan título, URL original y procedencia API. El registro enlaza también la página municipal mediante `?page_id=`. Se mantienen URLs HTTP tal como fueron publicadas; la muestra PDF se comprobó por HTTPS. El documento repetido de indicadores del PGE se conserva una sola vez. No se generan proyectos independientes para cada plano o estudio. No se descargan archivos ZIP ni se descomponen sus contenidos.

Las cabeceras `X-WP-TotalPages` dieron 1 en cada consulta. El adaptador recorre todas las páginas anunciadas, rechaza cambios de total durante la lectura, contenido paginado inesperado y páginas vacías/duplicadas. No hay límite silencioso de registros. La salida solo se reemplaza tras completar ambas fuentes. Las actualizaciones repiten el inventario completo y no simulan un incremental de expedientes.

## Fechas y límites semánticos

Las fechas explícitas `Pub.` se guardan en cada documento como `fecha_publicacion`. La fecha mensual `02/2014` se conserva como texto sin inventar día. No se usa la fecha de creación/modificación de WordPress como acuerdo, aprobación o publicación del instrumento. En particular, el PGOU señala en su página aprobación 27/06/1997 y BOP 30/09/1997; el resumen ambiental de otra versión PGE indexado por buscador menciona 26/06/1997. No se resuelve esa discrepancia asignando una fecha de aprobación. No se extraen fechas de acuerdos desde PDFs en esta implementación.

La disponibilidad actual de inventarios históricos no garantiza vigencia ni exhaustividad. El PGE se denomina expresamente versión preliminar y no se presenta como aprobado. No se infieren fases, ejecución física ni concesiones de licencias. No hay geometría ni coordenadas inventadas; `publication_ready=false`, `geometry_status=unavailable`, programación deshabilitada y jitter deshabilitado.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_alginet -v`: cinco pruebas correctas, que cubren agrupación de componentes y separación de modificaciones, fechas exactas/parciales, rechazo de formularios y vacíos, fallos de paginación sin reemplazar la salida previa, manifiesto y licencias desactivadas.

Ejecución real de `AlginetAyuntamientoAdapter('alginet', config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: seis registros. Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, respuestas API `pgou-1.json` y `pla-general-1.json`, captura de portada y consultas de investigación. `evidence/pgou.pdf`: descarga real de https://web.alginet.es/fitxers/urbanisme/pgou.pdf, HTTP 200, `application/pdf`, 905627 bytes. La comprobación de este PDF no implica verificar individualmente todos los adjuntos.
