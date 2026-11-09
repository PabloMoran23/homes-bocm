# Lekeitio — Bizkaia — INE 48057

Verificación en vivo: 2026-11-09. Adaptador limitado al inventario municipal
**Proyectos Municipales**: un proyecto real de obra física, «Proyecto de
reurbanización del entorno de Zumatzeta de Lekeitio», con un documento técnico.
No es una licencia concedida, un anuncio de contratación ni una noticia.

## Descubrimiento y fuentes oficiales

El directorio del Gobierno Vasco identifica Lekeitio, Bizkaia y código 48057 y
enlaza la web municipal `https://www.lekeitio.com`:
https://www.euskadi.eus/gobierno-vasco/atencion-ciudadania-servicios-digitales/-/ayuntamiento-de-lekeitio/

`https://www.lekeitio.eus` y su variante sin www dieron error TLS en requests;
no se desactiva la verificación de certificados. `.com` responde HTTP 200.
Su portada es una plantilla SharePoint con menú cargado por JavaScript.
El script público `/style%20library/anboto/js/anboto.js` consulta las listas de
navegación. La lista anónima «Menu Segundo Nivel» de `/es-ES/_api/web/lists/`
enlaza «Urbanismo, obras y servicios»:
https://www.lekeitio.com/es-ES/Servicios/urbanismoobrasyservicios

Esta página enlaza PGOU, Plan Especial Rehabilitación Casco Viejo, trámites,
ordenanzas y **Proyectos Municipales**. Inventario utilizado, HTTP 200:
https://www.lekeitio.com/es-ES/Servicios/urbanismoobrasyservicios/Paginas/udal-proiektuak.aspx

Cada bloque de proyecto contiene su título y documentos. El adaptador conserva
un registro por título de proyecto y agrupa todos sus documentos, incluso si se
repite el bloque. No utiliza una URL de PDF fija como seed de extracción.
Se verificó la totalidad de la biblioteca pública `udalproiektuak` mediante
SharePoint REST anónimo, colecciones `Files` y `Folders`:
https://www.lekeitio.com/es-ES/Servicios/urbanismoobrasyservicios/_api/web/GetFolderByServerRelativeUrl('/es-ES/Servicios/urbanismoobrasyservicios/udalproiektuak')/Files

La biblioteca devuelve un archivo de 98.959.664 bytes. Única subcarpeta:
`Forms` (carpeta de sistema). Documento enlazado por el proyecto:
https://www.lekeitio.com/es-ES/Servicios/urbanismoobrasyservicios/udalproiektuak/00-urbanizacion-zumatzeta-completo.pdf

Comprobación adicional: GET Range bytes=0-8191, HTTP 206,
Content-Type application/pdf y cabecera `%PDF-`. Se conserva solo ese prefijo
como captura parcial; no se afirma haber analizado las 94,3 MB del documento.

## Cobertura parcial y otras fuentes inspeccionadas

La cobertura es el inventario Proyectos Municipales, completo en esta consulta,
no la totalidad del urbanismo, obras municipales, proyectos históricos ni licencias.
La página PGOU contiene otros enlaces (antecedentes, aprobación definitiva,
primera modificación puntual, gestión y PE02 Karabia); no se extraen en este
adaptador ni se infiere de esos rótulos su vigencia jurídica actual:
https://www.lekeitio.com/es-ES/Servicios/urbanismoobrasyservicios/Paginas/pgou.aspx

Se inspeccionó también el catálogo oficial de Bizkaia:
https://www.opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-lekeitio

Su descarga JSON «Datos globales de planeamiento (2023-2026)» presenta estadísticas
municipales trimestrales, superficies y viviendas agregadas. No son expedientes
individuales y no se convierten en proyectos. Capturas en evidence/planning-data.*.
La búsqueda del endpoint CKAN `/api/3/action/package_show` devolvió 404; los
recursos se descubrieron en el HTML del catálogo, no mediante ese endpoint.
Los trámites de licencias y formularios no prueban concesiones: licencias deshabilitadas.

## Fechas, procedencia y geometría

La página de proyectos no declara fecha de publicación, acuerdo ni aprobación:
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son null. Tampoco se
asigna fase de ejecución o aprobación. `archivo_creado` (2026-07-14T11:55:18Z) y
`archivo_modificado` (2026-07-14T12:20:43Z) describen exclusivamente el fichero
SharePoint, nunca la aprobación de la obra ni su publicación municipal.
Cada documento retiene título, URL, página de procedencia, URL de biblioteca,
UUID del archivo y tamaño. El identificador de proyecto depende del título,
no de fechas de descarga o cambios del archivo.

geometry_status: unavailable. No se ha verificado geometría del proyecto ni
coordenadas en esta fuente. No se vectoriza el PDF ni se asigna el centroide del
municipio. `publication_ready=false`; geocode.jitter_missing=false.

## Paginación y errores

Se siguen todos los `__next` de las colecciones Files/Folders, con detección de
ciclos y validación del dominio municipal. No se aplica límite de registros.
La relación de documentos de la página debe coincidir exactamente con Files:
si el webpart limita u oculta archivos se aborta, sin sobrescribir la salida.
Nuevas subcarpetas diferentes de Forms y controles HTML de paginación requieren
revisión y producen error explícito. También se rechazan páginas vacías,
formularios, documentos externos y cambios de estructura. Una futura ampliación
podría necesitar reglas nuevas para agrupar instrumentos de otras bibliotecas.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_lekeitio -v`: 5 pruebas pasan; agrupación,
  semántica de fechas, exclusión de formularios, paginación REST y ciclos,
  fallo por desajuste sin sobrescritura, manifiesto y licencias deshabilitadas.
- Extracción real mediante `load_manifest('lekeitio')`, `load_portal_adapter(...)`
  y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 1 registro.
- `evidence/validation.json`: número de registros, URLs y limitaciones.
- `evidence/live-captures/`: respuestas reales del inventario y colecciones REST;
  config opcional `capture_dir` permite repetir las capturas.
- `evidence/document-check.json` y `zumatzeta-pdf-prefix.bin`: verificación parcial
  del PDF; otras capturas de descubrimiento bajo evidence/.

schedule.enabled=false. Sin cambios de dependencias o fuentes compartidas,
sin orquestador, publicación, base de datos ni despliegue. Evidencias locales,
no destinadas al commit. La aceptación corresponde al revisor independiente.
