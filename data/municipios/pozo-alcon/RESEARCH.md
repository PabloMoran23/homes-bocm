# Pozo Alcón — INE 23070, Jaén, Andalucía

Verificado el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Cobertura deliberadamente parcial: proyectos de ejecución de obra sometidos a
información pública en el tablón electrónico municipal vigente. No es un
inventario histórico de todo el planeamiento, todas las obras o las licencias.

## Fuentes oficiales investigadas

- https://www.pozoalcon.es/ — web municipal, HTTP 200. Enlaza expresamente a
  la sede, el tablón y el portal de transparencia de `pozoalcon.sedelectronica.es`.
- https://www.pozoalcon.es/ayuntamiento/urbanismo/ — HTTP 200; declara
  «No hay publicaciones de Urbanismo». No genera registros.
- https://pozoalcon.sedelectronica.es/transparency — HTTP 200. La categoría
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» anuncia dos elementos,
  pero su acción Wicket devolvió contenido vacío en la comprobación. Los dos
  documentos visibles en la raíz tratan del presupuesto y de plazos por el
  apagón; no se interpretan como instrumentos urbanísticos. Esta fuente no se
  integra en la extracción y no se afirma cobertura de sus carpetas.
- https://pozoalcon.sedelectronica.es/board — HTTP 200. Inventario público
  actual con columnas Documento, Expediente, Procedimiento, Categoría,
  Descripción y Fecha de Publicación. Diez filas iniciales y seis adicionales
  mediante «Mostrar más». La respuesta Wicket final reemplaza el contenedor
  del botón por un `div` oculto sin botón. Se recorrieron las 16 filas antes de
  seleccionar proyectos; no se corta en la primera página.
- https://pozoalcon.sedelectronica.es/preview-document/62515710-defe-4c09-8cae-70b258b24219
  — HTTP 200. Documento `ANUNCIO_INFORM_PUBLICA.fir`, formato PDF. Su PDF
  se descargó mediante el iframe público en la misma sesión y se contrastó con
  `pdftotext`. Los enlaces `/preview/pdf/…` dependen de la sesión; se conserva
  como enlace duradero la página `preview-document` y el PDF como evidencia.

## Registro real extraído y semántica

Un proyecto: **Proyecto de Ejecución de la obra «Adecuación de intersección en
el P.K. 3.600 de la JA-8201 Pozo Alcón a el Fontanar»**, expediente municipal
**3938/2026**. El anuncio de la Diputación Provincial de Jaén se publica en el
tablón municipal el **22/10/2026**. El documento somete el proyecto y los bienes
necesarios para su ejecución a información pública; remite a las dependencias
de la Diputación para consultar la documentación completa. No se dispone del
proyecto técnico íntegro ni de su geometría.

`fecha_publicacion=2026-10-22` corresponde exclusivamente a la publicación en
el tablón, no a la publicación en BOP, cuyo día no consta en este documento.
El PDF contiene firmas de 13 y 14 de octubre y menciona una resolución de
delegación de competencias de 9 de junio: ninguna es una fecha de aprobación
del proyecto. `fecha_acuerdo` y `fecha_aprob` permanecen nulas. La fecha de
creación del fichero tampoco se usa como fecha del instrumento. La fase es
«información pública», sin afirmar concesión, adjudicación, ejecución o aprobación.

El anuncio de licitación de reparación de pavimento y acerado (3968/2026), las
convocatorias de empleo, comunicaciones de tráfico, documentos notariales y
formularios no se convierten en proyectos ni licencias. No se ha verificado un
registro de licencias concedidas; `licencias.enabled=false`.

## Implementación y límites

El adaptador descarga el tablón con una sesión anónima y sigue las acciones
GET públicas de «Mostrar más». Aplica las sustituciones de componentes y
adiciones de filas de XML Wicket sin ejecutar JavaScript. Errores HTTP,
redirecciones inesperadas, ausencia de inventario, respuestas inválidas,
paginación sin progreso y el límite de seguridad de 100 páginas provocan error
antes de escribir un resultado parcial. La extracción requiere al menos un
proyecto utilizable. No emplea búsquedas o resultados de buscadores como registros.

El selector exige la descripción explícita «Información pública del Proyecto
de Ejecución de la obra …». Por tanto no cubre otros tipos de anuncio ni todos
los instrumentos urbanísticos. La identidad depende de expediente y título
normalizado, no del nombre del fichero. Los documentos con ese expediente y
título se agrupan conservando cada enlace y su fecha de publicación. La fecha
principal es la primera publicación observada del grupo. `update_proyectos`
refresca la instantánea completa: los anuncios pueden caducar y desaparecer.
No implementa un archivo histórico ni interpreta desapariciones como cancelación.

Sin coordenadas, geometría o centroides sustituidos. `publication_ready=false`,
`schedule.enabled=false`, `geocode.jitter_missing=false`.

## Validación y evidencia local

- `python -m unittest municipio.test_pozo_alcon -v`: **6 pruebas correctas**.
  Cubren fechas y agrupación de documentos, exclusión de licitaciones y
  formularios, rechazo de fuentes inválidas, recorrido de dos páginas, fallos
  de respuesta Wicket, esquema de manifest y licencias desactivadas.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos`: **1 registro**, **2 páginas**, **16 anuncios** examinados;
  anotación compartida de entidades con resultado `ok`, sin categorías desconocidas.
- `evidence/proyectos.jsonl` y `evidence/validation.json` contienen el registro
  y el informe de extracción. Capturas: `home.html`, `urbanismo.html`,
  `transparency.html`, `board-live.html`, `board-page-2.xml`,
  `board-complete.html`, `project-preview.html`, `interseccion.pdf` y
  `interseccion.txt`. La evidencia es local y no se incorpora a los fuentes.
