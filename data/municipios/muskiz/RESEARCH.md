# Muskiz — INE 48071, Bizkaia

Verificación en vivo: 2026-11-09. Adaptador único:
`municipio.adapters.muskiz:MuskizAyuntamientoAdapter`.

## Descubrimiento y fuentes

La web oficial municipal es https://www.muskiz.org. Su portada en castellano
https://www.muskiz.org/es-ES/Paginas/default.aspx devuelve principalmente una
plantilla SharePoint con navegación dinámica. La navegación pública de Servicios
https://www.muskiz.org/es-ES/Servicios/_api/web/navigation/quicklaunch?$expand=Children
identifica «Urbanismo» y enlaza el inventario usado por el adaptador:

https://www.muskiz.org/es-ES/Ayuntamiento/PGOU/Paginas/default.aspx

Esta página sí expone secciones HTML completas con instrumentos y documentación.
No requiere sesión. La enumeración de subwebs devuelve 403; no se intenta eludirlo.
Las consultas anónimas de navegación y las capturas son suficientes para descubrir
la página de Urbanismo. El scraper de producción sólo necesita esa página.

También se inspeccionó el catálogo oficial de la Diputación:
https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-muskiz
Su recurso vigente «Datos globales de planeamiento - Muskiz (2023-2026)»:
https://www.opendatabizkaia.eus/es/dump/4172d925-3324-4001-815b-3ea94afbd5f9/datos-globales-planeamiento-muskiz-2023-2026?format=json
contiene agregados trimestrales de suelo y viviendas, no expedientes identificables.
No se convierten esos agregados en proyectos. Captura local: `evidence/globales.json`.

## Cobertura y agrupación

Resultado real: **4 instrumentos**, **25 enlaces documentales**, incluyendo PDF,
carpetas y referencias enlazadas. Una fila por instrumento, no por documento:

| Instrumento | Enlaces | Alcance |
| --- | ---: | --- |
| Normas Subsidiarias de Planeamiento Municipal | 1 | Documento normativo municipal |
| Modificación NNSS IES Muskiz | 4 | Acuerdo, anuncios y documentación de la misma modificación |
| Revisión del PGOU | 19 | Documentación de avance/preavance, informes ambientales y participación |
| Plan especial centro de adiestramiento y hotel canino, parcela 704, polígono 01 | 1 | Documento del plan publicado por el Ayuntamiento |

Se agregan al PGOU los enlaces de su sección «Documentación». Los nombramientos,
renovaciones de vocales y reglamentos del consejo asesor no crean registros.
Cada documento conserva título, URL, URL municipal de procedencia y contexto
textual del inventario. Los documentos del Gobierno Vasco son documentos de ese
organismo alojados/enlazados por el Ayuntamiento; alojamiento no implica autoría.
Los enlaces externos y acortados se retienen como referencias municipales, sin
rastrear carpetas Drive ni afirmar su disponibilidad. Los IDs locales expresan
identidad del instrumento; no son números de expediente administrativos.

La cobertura es **parcial**, no un inventario exhaustivo ni sólo obras activas.
Se excluyen la reurbanización de Kobaron (carpeta Drive externa), el PERI de San
Juan PRCL-1 (enlace a aviso secundario), noticias, conferencias, contratación y
trámites. La navegación raíz contiene además un enlace de aprobación definitiva
del PERI: no se interpreta el aviso inicial de 2016 como su fase vigente.
Los cuatro instrumentos elegidos tienen al menos un PDF municipal directo.
No se ha verificado un registro de licencias concedidas: deshabilitadas.

## Fechas, vigencia y garantías

El plan especial lleva publicación explícita **10/07/2025** en el encabezado.
El documento de alcance ambiental del PGOU y su recopilación de informes tienen
publicación web **05/11/2026**, conservada por documento. El PGOU completo no
recibe esa fecha como si fuese su acuerdo de aprobación. Se extraen también las
fechas explícitas de publicación de ampliaciones de exposición pública de 2025.
No se convierten años de archivo, fechas de redacción o títulos de agenda en
fechas de aprobación. `fecha_acuerdo` y `fecha_aprob` quedan nulos: el adaptador
no analiza el contenido de PDF para extraer acuerdos.

Ejemplo de la distinción: el enlace municipal IES indica «19 de abril 2016» y
«si procede», mientras el PDF descargado dice que el Pleno adoptó el acuerdo el
14 de abril de 2016. Se mantiene el título original del enlace, sin promover su
fecha a acuerdo ni aprobación. El error literal «14/01/2105» de otro enlace
se conserva en el título del documento, sin generar una fecha normalizada.

La página revisada es estática, sin paginación activa. Se recorren todos los
enlaces de las secciones seleccionadas sin límite de registros. Si aparece
paginación se falla explícitamente: no se acepta una primera página truncada.
Se rechazan secciones ausentes, instrumentos sin PDF municipal o cambios en la
sección de modificaciones NNSS que requieran revisar su agrupación. Cada update
refresca la instantánea completa y sólo reemplaza la salida tras parseo correcto.

## Geometría y validación

`geometry_status: unavailable`. Los PDF contienen planos, pero no se ha verificado
una geometría vectorial vinculada por identificador a estos instrumentos. Los
agregados de suelo del catálogo foral tampoco son geometrías del proyecto.
No se geocodifica, vectoriza ni inventa coordenadas. `publication_ready: false`.

Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_muskiz -v` — **5 pruebas pasan**.
Cubren agrupación, procedencia, fechas explícitas, deduplicación, exclusión de
nombramientos/formularios/noticias, rechazo de paginación y cambios de fuente,
actualización sin pérdida de salida previa, licencias vacías y carga del manifest.

Extracción real: `MuskizAyuntamientoAdapter('muskiz', config={'evidence_dir':
'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Evidencias locales: `proyectos.jsonl`, `validation.json` (conteo, URLs,
limitaciones, pruebas, hashes y tamaños de descargas), `inventory.html`, metadatos
de respuesta y capturas de descubrimiento. Cinco PDF principales descargados
con HTTP 200 y cabecera `%PDF`: NNSS, acuerdo IES, documento de alcance PGOU,
plan especial canino e informes PGOU. No se verificaron todos los anexos antiguos.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Sin cambios compartidos, dependencias, publicación ni operaciones de producción.
