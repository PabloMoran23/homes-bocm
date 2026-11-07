# Ordizia — INE 20076, Gipuzkoa

Verificación: 2026-11-07. Adaptador de inventarios documentales municipales,
con cobertura parcial explícita. No es un registro de licencias ni un histórico
completo de planeamiento u obras del municipio.

## Descubrimiento y fuentes oficiales

Desde la portada https://www.ordizia.eus/es/ se sigue «Urbanismo»:
https://www.ordizia.eus/es/ayuntamiento/el-ayuntamiento/urbanismo (HTTP 200).
Su contenido central ofrece «Revisión del Plan General», un enlace al Plan de
Movilidad y un PDF titulado `Estudio de detalle "Urdaneta 36-38"`.
El adaptador selecciona el inventario del PGOU y los enlaces PDF identificados
explícitamente como estudios de detalle. No interpreta otros enlaces como proyectos.

«Revisión del Plan General» lleva a:
https://www.ordizia.eus/es/plan-general-de-ordenacion-urbana (HTTP 200).
Título actual: `PLAN GENERAL DE ORDENACIÓN URBANA - Avance 2017`.
La página es un árbol Dropfiles con raíz 196, no una lista de noticias.
El JavaScript público `/plugins/dropfilesthemes/tree/js/script.js` muestra las
peticiones de lectura utilizadas por la interfaz:

- `https://www.ordizia.eus/index.php?option=com_dropfiles&view=frontcategories&format=json&id=196`
- `https://www.ordizia.eus/index.php?option=com_dropfiles&view=frontfiles&format=json&id=196`

Se sustituyen los IDs por los descubiertos en cada respuesta, sin fijar un listado
de documentos. Se recorren raíz y descendientes completos: **12 categorías,
113 documentos**, incluidos memorias, planos, evaluación ambiental, resumen y
exposición. Todos quedan agrupados en **un instrumento**, ID `ordizia-proy-pgou-196`.
Cada documento retiene ID de archivo, título, formato, ruta de carpetas, enlace
municipal de descarga, URL de la respuesta de procedencia y fecha de alta.
No se conservan URLs de visores Google ni sus parámetros variables.

La sección Normativa municipal
https://www.ordizia.eus/es/ayuntamiento/normativa-municipal también enlaza
«Planeamiento urbanístico», cuyo enlace público con `catid[0]=196` devuelve
este mismo árbol. No representa un segundo instrumento. La propia página advierte
del valor divulgativo de los documentos. Los PDFs de Normas Subsidiarias localizados
por búsqueda no se convierten en registros independientes sin un inventario
estructurado adicional revisado.

Segundo instrumento: **Estudio de detalle Urdaneta 36–38**, descubierto en Urbanismo:
https://www.ordizia.eus/media/attachments/2026/02/09/xehetasun-azterlanaren-hasierako-onespen-dokumentua.pdf
(HTTP 200, application/pdf, 3.063.686 bytes). Captura y lectura con `pdftotext`:
el PDF identifica AIU 4 Urdaneta, expediente 2024B0001, documento de noviembre de
2024 y ordenación de alineaciones, rasantes y perfil del edificio resultante de
sustituir los números 36 y 38. Es un instrumento físico concreto, no un formulario
ni anuncio de contratación. Estos datos documentales sirven de comprobación;
el parser utiliza el título/enlace publicado, sin fijarlos como constantes.
El ID se deriva del título para resistir cambios de ubicación del PDF.

## Fechas, fases y límites

- PGOU: `fase=avance`, expresamente indicada en el título. No se afirma aprobación
  definitiva, vigencia jurídica ni que el documento de 2017 sea el último acuerdo.
- Las fechas `created_time` de Dropfiles se guardan exclusivamente como
  `documentos[].fecha_alta_documento`; no son fechas de acuerdo ni de aprobación.
- `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas en ambos
  instrumentos. Ni el año del avance, ni noviembre de 2024, ni la ruta del PDF
  `/2026/02/09/` justifican inventar una fecha diaria de publicación o aprobación.
- No se atribuye fase al estudio a partir del nombre vasco del archivo.
- No se extraen noticias generales, contratación, formularios de solicitud,
  Plan de Movilidad ni el tablón de anuncios paginado. No se afirma cubrir esos
  inventarios: son ámbitos ajenos al alcance documental implementado.
- Licencias deshabilitadas: no se ha verificado un inventario de concesiones.
  Sus métodos generan salida vacía con estado `disabled` sin peticiones de red.

## Completitud y fallos

Se consultan archivos y subcarpetas en cada nodo, incluida la raíz y carpetas sin
archivos. La API pública examinada devuelve listas completas sin paginación;
por ejemplo, las carpetas 199 y 202 devuelven 53 y 40 archivos respectivamente,
concordantes con los contadores del padre. Se comprueba cada contador disponible,
la concordancia de las categorías visibles en HTML con la raíz de la API y las
identidades/relaciones de categorías y documentos. Ciclos, documentos conflictivos,
metadatos inesperados (incluida paginación), contenido ausente, enlaces externos,
recuentos incompletos o más de 200 categorías causan error antes de escribir
una instantánea parcial. La paginación HTML también se rechaza expresamente.
No hay recorte por número de archivos. Las actualizaciones refrescan este alcance
completo; no interpretan desapariciones como revocaciones de instrumentos.

## Geometría

`geometry_status: unavailable`. Los inventarios ofrecen documentos, incluidos
planos PDF, pero no una geometría vectorial verificada vinculada por instrumento.
No se han georreferenciado ni vectorizado esos planos, ni se ha verificado una capa
de visor asociable a ambos expedientes. Coordenadas y geometría nulas;
`publication_ready=false`. No se usa centroide ni dispersión aleatoria.

## Verificación reproducible y evidencia local

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_ordizia -v` (5 pruebas).
Cubren agrupación y exclusión de formularios/contratación, identidad estable,
recorrido descendiente, fechas de alta separadas de fechas del instrumento,
recuentos truncados, categorías ausentes, ciclos, paginación, cambios de fuente,
enlaces externos, contrato del manifest y licencias deshabilitadas.

Extracción real mediante `OrdiziaAyuntamientoAdapter.backfill_proyectos`:
**2 registros y 114 enlaces documentales**, con 26 respuestas HTTP de inventario.
`evidence/proyectos.jsonl` contiene los registros reales;
`evidence/validation.json` recoge recuentos, URLs solicitadas y limitaciones.
`evidence/captures/` conserva las respuestas HTML/JSON con nombres SHA256(URL)
truncados a 20 caracteres; las URLs constan en validation.json.
Además se conservan las páginas de descubrimiento, el JavaScript público y el
PDF/texto de Urdaneta. No se descargan masivamente los otros 113 PDFs; se retienen
sus enlaces de descarga municipales. Evidencia local excluida del control de versiones.

Manifest: `codigo_ine: '20076'`, provincia Gipuzkoa, `schedule.enabled=false`,
`licencias.enabled=false`, `geocode.jitter_missing=false`. Solo cuatro archivos
fuente nuevos, sin dependencias nuevas ni modificaciones compartidas.
