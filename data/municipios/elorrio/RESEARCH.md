# Elorrio — INE 48032, Bizkaia

Verificación en vivo: 2026-11-09. Adaptador municipal único, cobertura parcial.

## Descubrimiento y procedencia

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`,
`registry.py` y los ejemplos Hernani y Manlleu. El manifiesto usa el contrato
existente y deshabilita programación, licencias y desplazamiento de coordenadas.

El portal principal https://www.elorrio.eus redirige a una portada SharePoint cuya
respuesta HTML tiene navegación incompleta. Se localizó y comprobó directamente
el anuncio municipal:

https://www.elorrio.eus/es-ES/Noticias/Paginas/20260930-hapo-elorrio-aurrerakina.aspx

HTTP 200. El anuncio enlaza expresamente https://hapo-elorrio.eus/es como web del
PGOU. Por tanto no se infiere oficialidad únicamente del nombre del dominio.
El adaptador verifica este enlace en cada ejecución y descubre «DOCUMENTOS» desde
la portada del portal temático, sin fijar PDFs individuales como registros.

Inventario oficial actual: https://hapo-elorrio.eus/es/documentos (HTTP 200).
Contiene documentos sustantivos del Avance, documentación gráfica y documentos
de participación y estudios previos, agrupados por fases 3, 2 y 0/1. Es una página
completa del instrumento, no una noticia usada para inventar un proyecto.

También se localizó el catálogo oficial provincial:
https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-elorrio
Describe datos globales del planeamiento y núcleos rurales; no se usa para generar
proyectos a partir de estadísticas ni se afirma haber recorrido sus recursos.
No se verificó un inventario exhaustivo de obras o licencias concedidas.

## Extracción y semántica

Resultado real: **1 instrumento**, revisión del PGOU, con **147 URLs PDF únicas**.
Todos los enlaces del inventario se conservan, incluidas referencias externas a
`d9.createlli.com`; los documentos no se convierten en proyectos distintos.
Cada enlace conserva su título, URL del inventario y referencias de fase documental.
La discrepancia de origen `AE.2.2.A` → `AA.2.2.A.pdf` se conserva como alias del mismo
documento, sin corregir la URL ni generar otra actuación.

La fase actual se toma del primer bloque: exposición pública del Avance. Las fases
posteriores explicadas genéricamente en la portada no son acuerdos aprobados.
La ejecución falla si cambia esa fase o faltan Memoria, Resumen ejecutivo o DIE,
para exigir revisión semántica en vez de mantener silenciosamente una fase antigua.
El ID corresponde al instrumento, estable frente a nuevos archivos o fases.

El anuncio muestra **23/09/2026** en `span.date`: se registra como
`fecha_publicacion`, con `fecha_publicacion_source_url` explícita. No se deriva
una fecha del nombre de URL `20260930`, de los actos participativos, de Last-Modified
ni del nombre de los PDFs. La fecha de publicación del inventario/documentos no se
conoce. `fecha`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas.

Se descargó y comprobó además el PDF «Resumen ejecutivo» enlazado por el inventario:
https://hapo-elorrio.eus/sites/default/files/users/user42740/PGOU_Elorrio_Resumen%20Ejecutivo_2026.pdf

HTTP 200, PDF real de 39.282.727 bytes. La portada identifica Documento de Avance,
Resumen ejecutivo, agosto de 2026; el texto interior identifica el PGOU de Elorrio.
Es fecha documental mensual, no aprobación. Captura PDF y texto en evidencia local.
`pdftotext` recuperó el texto con avisos de fuentes AutoCAD en planos.
No se han descargado ni validado individualmente los otros 146 PDFs. Los enlaces
son procedencia de inventario, no certificación de su contenido: en estudios previos
incluso figura un archivo `28_10_First draft Reporting summaries per topic.pdf` bajo
«Documentación gráfica», conservado sin atribuirle contenido urbanístico verificado.

## Paginación y límites

No hay paginación en la captura actual. Se procesa todo el cuerpo del inventario,
sin máximo de registros/documentos ni recorte de resultados. Si aparece paginación
(rel next/prev, enlaces de pager, page= o siguiente/anterior), el adaptador falla
explícitamente. Las pruebas comprueban que 250 documentos adicionales no se recortan.
Un snapshot vacío o un cambio de estructura exige revisión; no reemplaza la salida
con datos parciales. La actualización vuelve a leer el inventario completo.

No se extraen formularios, noticias ajenas, anuncios de contratación o hipotéticas
licencias. Los métodos de licencias producen vacío con estado disabled. La cobertura
es únicamente este PGOU en revisión, no el planeamiento vigente completo ni todo el
histórico municipal de actuaciones.

## Geometría y validación

`geometry_status: unavailable`. Hay planos PDF pero no se ha verificado geometría
vectorial asociada al instrumento. `lat`, `lon`, `geometry` nulos;
`publication_ready: false`. Sin geocodificación ni centroides inventados.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_elorrio -v` — **3 pasan**. Comprueban
agrupación, alias, todas las fases/enlaces, ausencia de fechas/coordenadas inventadas,
paginación, cambios de fuente/fase, oficialidad, manifiesto y contrato del registro.
Extracción real mediante `load_portal_adapter(load_manifest('elorrio'))` y
`backfill_proyectos`, sin orquestación, publicación ni acceso a bases de datos.

Evidencia local no versionada: `evidence/proyectos.jsonl`, `evidence/validation.json`,
HTML de anuncio/portada/inventario, `resumen-ejecutivo.pdf`, texto extraído y
`pdf-validation.json`. El informe incluye live_records=1, source_urls y limitaciones.
