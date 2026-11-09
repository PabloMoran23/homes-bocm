# Arroyo de la Luz — INE 10021, Cáceres

Verificación: 2026-11-09. Adaptador exclusivo de este municipio. Programación y
licencias deshabilitadas; sin jitter ni coordenadas inventadas.

## Descubrimiento y fuentes oficiales

- Web municipal: https://arroyodelaluz.es/ — identifica el Ayuntamiento y ofrece
  actualidad municipal, incluidas noticias de obras. No se usa como inventario
  de licencias ni se convierten las noticias, formularios o licitaciones en obras.
- Consulta oficial de planeamiento de la Junta de Extremadura:
  https://sitex.juntaex.es/SITEX/planeamiento
- Inventario municipal:
  https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat
  Se consulta mediante **POST**, cuerpo `municipioseleccionado=243`, como hace el
  JavaScript público `Ajax.Updater` del visor. Un GET con parámetros no obtiene
  este inventario. La opción municipal se descubre por nombre en el selector,
  sin confundir el identificador interno SITEX **243** con el INE **10021**.
- Fichas descubiertas desde el árbol, por ejemplo:
  https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40407
  No se fija una lista de expedientes como semilla del extractor.

La procedencia es **autonómica**, no un registro del Ayuntamiento. El valor
`proyectos.source: ayuntamiento` sigue la ruta municipal del esquema existente;
cada registro declara `source: sitex-juntaex` y
`origen: registro_autonomico_planeamiento` para conservar la procedencia real.

## Cobertura y significado

El árbol completo contiene 43 fichas: se extraen los **42 instrumentos de ámbito
exclusivamente municipal** y se excluye el Plan Territorial Tajo-Salor (39826),
supramunicipal. Resultado observado: **31 vigentes, 7 en trámite y 4 no vigentes**.
Incluye normas subsidiarias y revisión, modificaciones, planes parciales, el
PGM en trámite, el estudio de detalle de calle Carretera y el PIR Residencial
Pontones con sus modificaciones. Son instrumentos reales identificados por
referencia e ID oficial, no licencias concedidas ni contratos de obras.

Cada ficha produce un registro; sus memorias, planos y publicaciones se agrupan
en `documentos`, con título, URL y ficha de procedencia. Las modificaciones
siguen siendo instrumentos distintos con sus propias referencias oficiales.
Los números del título y de la referencia no siempre coinciden: se preservan
ambos tal como los publica SITEX. Se conservan también los trámites y enlaces.
Hay **78 enlaces documentales** asociados a 26 instrumentos; 16 fichas sólo
ofrecen metadatos. No se garantiza la disponibilidad de todos los PDFs ni se
han interpretado sus contenidos para deducir datos adicionales.

`fecha_aprob` procede de **Fecha AD** y `fecha_publicacion` de **Fecha de
publicación AD**, es decir, publicación en el diario indicado por SITEX. No es
la fecha de actualización de la web ni se rellena `fecha_acuerdo` por inferencia.
Ejemplo verificable, ficha 40407: aprobación definitiva municipal el **28/03/2023**,
publicación en DOE el **02/08/2023**; memoria y publicaciones permanecen juntas.
Los campos vacíos son null. En trámite no significa aprobado; no vigente no
significa vigente. Los trámites conservan su fecha y denominación originales.

Cobertura parcial respecto a toda la actividad municipal: no incluye inventario
de obras, licencias, contratos, ni todos los posibles anuncios DOE/BOP ajenos al
árbol SITEX. Los estados son los declarados por este registro, cuya actualización
puede diferir del boletín oficial; no se certifica exhaustividad legal ni vigencia
independiente. Por ejemplo, no se añade al inventario una noticia o publicación
de búsqueda que SITEX no vincule a una ficha descubierta.

## Recorrido, errores y geometría

Se recorren todos los enlaces de ambos árboles legales, sin límite de registros,
ventana temporal ni corte por antigüedad. No hay paginación activa: los árboles
expandibles ya contienen los enlaces en HTML. Si aparece paginación se falla
explícitamente para exigir ampliar el recorrido. Se rechazan inventarios vacíos,
links desconocidos, municipio distinto, fichas sin identidad y fechas inválidas.
Se valida también el ámbito exacto de cada ficha. Un error de red/parser impide
reemplazar el fichero anterior. `update_proyectos` refresca el inventario completo.

El visor de consulta carga `Municipios.geojson` y `PT.geojson` como contexto
territorial (el JavaScript declara EPSG:25829). No son geometrías verificadas
por instrumento. No se reutiliza el límite municipal como ubicación de un
proyecto ni se vectorizan planos PDF. `geometry_status: unavailable`, geometría,
latitud y longitud null; `publication_ready: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`

Pruebas: `python -m unittest municipio.test_arroyo_de_la_luz -v` — **7 pasan**.
Cubren descubrimiento, deduplicación sin límite de registros, rechazo de
paginación y cambios de ámbito, documentos agrupados, separación de fechas,
ausencias sin inventar datos, preservación de salida ante error, refresco e
identidad/configuración del manifiesto.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`capture_dir: evidence/live-captures` como configuración sólo de la ejecución.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
capturas HTML y mapa de peticiones en `evidence/live-captures/requests.jsonl`.
La validación registra recuentos, URL de inventario/fichas/documentos,
limitaciones y la anotación de entidades aplicada por el registro de adaptadores.
Las evidencias no forman parte de los cuatro ficheros fuente entregables.

La validación final del clasificador compartido devuelve `status: ok`: 40
expedientes y 2 pendientes (PGM y NNSS histórica, cuyas referencias originales
no contienen cifras). Se conservan como instrumentos reales sin inventar otra
referencia para forzar la clasificación. La memoria de 40407 y su publicación DOE
se descargaron adicionalmente con HTTP 200 y cabecera PDF válida; las comprobaciones
y capturas están en `evidence/source-checks.json`, `memoria-40407.pdf` y
`doe-40407.pdf`. Esto no supone verificar todos los enlaces del inventario.
