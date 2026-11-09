# Huarte / Uharte — INE 31122, Navarra

Verificación: 2026-11-08. Adaptador de un archivo público municipal, con cobertura
parcial de instrumentos urbanísticos documentados; no es un censo de licencias.

## Descubrimiento y fuentes

- Portal oficial: https://huarte.es/ . Su navegación enlaza Noticias, Participación,
  sede electrónica y callejero.
- Inventario público consultado:
  https://huarte.es/wp-json/wp/v2/posts?search=plan+especial&per_page=100&page=1&orderby=id&order=asc
  Es la colección de entradas WordPress, filtrada por términos de búsqueda. Se
  contrastó con la búsqueda pública REST y los detalles HTML de las publicaciones.
- https://huarte.es/wp-file-download/urbanismo/ responde 200 pero no muestra un
  inventario utilizable (mensaje de contenido no encontrado).
- https://huarte.sedelectronica.es/info.0 muestra trámites y tablón. Los trámites de
  comunicación urbanística no prueban concesiones. No se extraen licencias.

El inventario devuelve 15 entradas en una página durante esta verificación. Solo
se aceptan las seis publicaciones tituladas «Proceso de participación – Plan
Especial Actuación Urbana…» que contienen la explicación del avance y enlaces a
documentación técnica municipal. Los resúmenes de plenos, noticias generales,
solicitudes y contratación quedan fuera de esta cobertura. La web contiene también
enlaces de spam ajenos al urbanismo: no se siguen ni se consideran fuentes.

## Registros y procedencia

Cinco instrumentos, seis publicaciones y trece documentos PDF enlazados:

| Instrumento | Publicación municipal | IDs WordPress | Documentos |
| --- | --- | --- | --- |
| PEAU Zubiarte 22, parcela 215, Construcciones Auztarri | 2021-09-27 | 9101 | 3 |
| PEAU Zubiarte 16 | 2021-10-29 y 2022-10-21 | 9121, 5233 | 4 |
| PEAU Zubiarte 42 | 2022-03-08 | 4953 | 2 |
| PEAU Artadiburua | 2022-03-08 | 5025 | 2 |
| Modificación de determinaciones del Barrio Antiguo | 2022-04-28 | 5079 | 2 |

Ejemplo HTML contrastado:
https://huarte.es/noticias/proceso-de-participacion-plan-especial-actuacion-urbana-cons-auztarri-2/
Describe expresamente la parcela 215, polígono 1, calle Zubiarte 22 y enlaza
reunión, documento y resumen. Cada registro conserva las URLs completas de sus
publicaciones y documentos, sus títulos originales y fechas por procedencia.

Se agrupan las publicaciones por ámbito indicado en el título; Zubiarte 16 no se
duplica por tener dos anuncios. Los documentos tampoco generan registros aparte.
El anuncio del Barrio Antiguo usa la plantilla de PEAU, pero su propio texto y
memoria describen una modificación de determinaciones: se clasifica como tal.

Las fechas son de **publicación** WordPress, contrastadas con las fechas visibles
en el detalle. La fecha principal es la primera publicación del instrumento; todas
las posteriores se retienen. No se deducen fechas de los nombres de fichero, de
la modificación del sitio, ni de menciones a aprobaciones de planes anteriores.
`fecha_acuerdo` y `fecha_aprob` permanecen nulas. La fase se limita al proceso de
participación previo a aprobación inicial descrito por estos anuncios históricos;
no certifica el estado jurídico actual, ejecución ni aprobación del instrumento.

Los PDF de Zubiarte 16 incluyen «Pamplona» en algunas cabeceras y referencias
catastrales contradictorias en el texto, mientras el anuncio municipal identifica
Huarte y Zubiarte 16. Se conserva esa procedencia documental sin convertir esas
referencias en geometría ni normalizarlas como datos catastrales fiables. El PDF
`Urbanismo_Reunion_Zubiarte_16.pdf` carece de texto extraíble en la comprobación
con `pdftotext`; se retiene su enlace y captura, sin afirmar lectura OCR.

## Cobertura, paginación y geometría

Se recorren todas las páginas declaradas en `X-WP-TotalPages`, comprobando también
`X-WP-Total`, IDs repetidos y cambios de totales durante el recorrido. Se falla
ante inventario incompleto, página inesperadamente vacía, documentos técnicos
ausentes o contenido enlazado que no sea PDF. El límite de seguridad de 1000
páginas falla explícitamente; no trunca resultados. Actualización y backfill hacen
la misma instantánea completa de esta búsqueda acotada.

No incluye todos los planes, obras municipales, noticias de obras, acuerdos de
pleno, BON, ni un histórico completo de urbanismo. No confirma cambios posteriores
de fase. La agrupación presupone un instrumento por ámbito/título; futuros planes
distintos con idéntico título requerirían revisar esa identidad.

geometry_status: unavailable

La navegación enlaza el callejero
https://www.nekar.com/index.php/es/herriak/herria/52 . Los anuncios revisados no
enlazan una capa vectorial identificada por instrumento. No se han georreferenciado
planos PDF ni usado centroides municipales. Coordenadas y geometrías quedan nulas,
`publication_ready: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_huarte -v` (5 casos). Cubren agrupación,
procedencias y fechas, exclusión de formularios/noticias, documentos ausentes,
clasificación del Barrio Antiguo, paginación completa y rechazo de pérdida de filas
o cambios de inventario, además del contrato del manifest.

Extracción real mediante `load_portal_adapter(load_manifest('huarte'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, activando únicamente
`config['capture_dir']='evidence/captures'` para guardar respuestas locales.
Se verifican por HTTP y cabecera binaria todos los PDF enlazados. Evidencias:
`evidence/proyectos.jsonl`, `evidence/validation.json` y respuestas/cabeceras en
`evidence/captures/`. Evidencia local excluida del control de versiones.

El clasificador compartido anota los cinco registros como `pendiente` con motivo
`insufficient_identity_evidence`: no se han inventado números de expediente para
forzar su elegibilidad. La extracción documentada queda disponible para revisión;
no se afirma aptitud para publicación automática.

`schedule.enabled: false`; licencias deshabilitadas. Sin publicaciones, despliegues
ni acceso a servicios privados.
