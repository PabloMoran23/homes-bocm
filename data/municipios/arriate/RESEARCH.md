# Arriate — Málaga — INE 29020

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

La [sede electrónica municipal](https://arriate.sedelectronica.es/info.0) identifica
al Ayuntamiento de Arriate. La identificación territorial puede contrastarse con
el [directorio estatal de entidades locales](https://administracion.gob.es/espanaadmon/quienesquien/entidades-locales-ayuntamientos-estructuras-y-directorios?idProvincia=29&idUniOrganica=L01290206),
que sitúa el Ayuntamiento en Arriate, Málaga. No confundir con Arrieta, Bizkaia.

Se inspeccionaron el [portal de transparencia](https://arriate.sedelectronica.es/transparency)
y el [tablón de anuncios](https://arriate.sedelectronica.es/board). Este último
contiene anuncios heterogéneos y actas; no se convierte ninguno automáticamente
en licencia concedida o proyecto. La web https://www.arriate.es/ y su sitemap
respondieron HTTP 202 sin contenido utilizable en esta ejecución.

La fuente implementada es la sección municipal
[7. Urbanismo, Obras Públicas y Medio Ambiente](https://arriate.sedelectronica.es/transparency/6515c79d-5996-4dea-9e23-0170fb71a39f/).
El inventario muestra 53 documentos distribuidos entre Planeamiento (18),
Normativa urbanística (3), PMVS (11), despliegue FTTH (13) y EDAR/colectores (8).
Las carpetas de programas medioambientales y obras públicas figuran vacías.

## Cobertura implementada y agrupación

Tres registros reales, con 35 enlaces documentales conservados:

| Instrumento/proyecto | Carpeta oficial | Documentos |
| --- | --- | --- |
| Innovación PGOU para ampliación de suelo industrial: creación UE-6 | [UE-6](https://arriate.sedelectronica.es/transparency/85689b67-e2e3-4ac2-ad0e-321b5fa9bc79/) | 16 |
| PMVS 2019–2023, Plan de Vivienda y Suelo | [PMVS](https://arriate.sedelectronica.es/transparency/e2085fd7-6913-419f-8d21-a93dbaba6e2b/) | 11 |
| Proyecto de construcción de saneamiento y depuración de la Cuenca Alta del Río Guadiaro, EDAR y colectores Arriate | [EDAR](https://arriate.sedelectronica.es/transparency/5c787090-93bb-4479-9071-caadc6497b46/) | 8 |

Se extraen los títulos del inventario vivo; no hay registros precargados. El
PMVS agrupa seis tomos y los cinco documentos de la subcarpeta PLANOS. UE-6
agrupa diligencias, documentos de innovación y planos DWF, incluidas las seis
entradas servidas después de «Mostrar más». EDAR agrupa siete tomos y su portada.
Cada documento conserva título, enlace estable de previsualización y carpeta de
procedencia. La identidad del registro deriva del UUID municipal de la carpeta.

La carpeta [Planeamiento urbanístico](https://arriate.sedelectronica.es/transparency/b07c4707-ffcf-4636-bf29-5db8e17b1c72/)
contiene también un BOP y una diligencia registral sin vinculación explícita a
UE-6: no se les atribuye ese expediente. Se excluyen deliberadamente los tres
documentos de la compilación de normativa y los trece del despliegue privado de
FTTH. La cobertura es parcial y documental, no un censo de todo el planeamiento,
las obras históricas o las licencias municipales.

## Navegación, fechas y procedencia

Gestiona utiliza callbacks Wicket de sesión para abrir carpetas; al seguirlos
se obtienen URLs estables `/transparency/<uuid>/`. El adaptador usa una sesión
HTTP pública, descubre los callbacks en cada respuesta y sigue «Mostrar más»
hasta desaparecer. Aplica las sustituciones y filas añadidas de la respuesta
XML, incluida la codificación `wicket1`, sin ejecutar JavaScript. Compara el
número final de documentos, incluidos descendientes, con el contador de cada
carpeta seleccionada. Ausencia de sección, cambio de alcance, respuesta vacía,
bucle de paginación o recuento incompleto provocan error antes de escribir la
salida. No existe límite de páginas que devuelva un resultado parcial.

No se infieren fechas de publicación ni de acuerdo/aprobación. El período
2019–2023, las etiquetas «Abril19» y «2024», o las fechas de creación del gestor
no son fechas de acuerdo ni de publicación. Las diligencias adjuntas se enlazan,
pero su contenido jurídico no se interpreta para afirmar fases o vigencia. La
publicación actual en el portal tampoco demuestra ejecución material o validez
actual del instrumento.

Se comprobó en vivo la [ficha del tomo 1 de EDAR](https://arriate.sedelectronica.es/preview-document/0f846bd8-f248-489c-9cf8-75513cd0b3a5):
identifica un documento electrónico PDF y permite abrirlo/descargarlo. Se guardó
su ficha y una muestra de los primeros 1024 bytes del PDF con firma `%PDF-`.
Esto verifica una muestra, no el contenido de todos los adjuntos. Las URLs
estables de las fichas se conservan en los registros; el enlace temporal del
visor PDF no se usa como identidad documental.

Sin coordenadas verificadas: `geometry_status: unavailable` y
`publication_ready: false`. No se geocodifica ni se inventa geometría. El
manifest desactiva `schedule.enabled`, `geocode.jitter_missing` y
`licencias.enabled`; los métodos de licencias producen una salida vacía
explícitamente deshabilitada, sin interpretar formularios como concesiones.
La actualización vuelve a leer el inventario completo seleccionado.

## Verificación reproducible

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_arriate -v`.
Seis pruebas correctas: manifest/carga de adaptador, XML paginado y codificación,
rechazo de fuente incorrecta, agrupación recursiva/aislamiento de documentos,
rechazo de truncamiento y bucles. Comprueban también ausencia de fechas/fases
inferidas y desactivación de licencias.

Extracción real mediante `ArriateAyuntamientoAdapter('arriate',
{'capture_dir': 'evidence/live'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
**3 registros, 35 documentos**. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas de navegación
HTML/XML en `evidence/live/`, capturas exploratorias y muestra PDF en `evidence/`.
La validación recoge `live_records`, `source_urls`, limitaciones, recuentos por
instrumento y comprobación documental. No se accedió a bases de datos ni se
publicó contenido.
