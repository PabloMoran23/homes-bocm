# Villanueva de la Torre — INE 19319, Guadalajara

Verificado en directo el 9 de noviembre de 2026. Un adaptador municipal con
cobertura parcial del inventario documental POM. No es un registro de licencias
concedidas ni un inventario completo de obras municipales. Programación y jitter
desactivados. Todos los registros tienen `publication_ready: false`.

## Descubrimiento y fuentes oficiales

- https://www.villanuevadelatorre.com/ — web del Ayuntamiento, HTTP 200;
  enlaza expresamente la sede y su portal de transparencia.
- https://villanuevadelatorre.sedelectronica.es/transparency — HTTP 200;
  inventario público con «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE»
  (109 documentos). Las carpetas se abren mediante acciones Wicket públicas.
- https://villanuevadelatorre.sedelectronica.es/transparency/14196eeb-5bd7-43f6-8ddd-23a90e887763/
  — carpeta de urbanismo, HTTP 200. Contiene planeamiento, diagnóstico, consulta
  previa SI-03 y otros documentos; los rótulos aislados no se convierten en obras.
- https://villanuevadelatorre.sedelectronica.es/transparency/ba147749-25db-4fbb-8010-2bf088e84d4b/
  — índice de planeamiento, HTTP 200: POM (25), PAUS (15), PEIS (10), sectores
  antiguos (41), subsanación catastral (1), expedientes en tramitación (8).
  Estos otros ámbitos quedan expresamente fuera de esta implementación.
- https://villanuevadelatorre.sedelectronica.es/transparency/87e10476-50d2-4db1-ba55-0aab0fa8548b/
  — carpeta POM, fuente extraída. Veinte documentos directos: memorias, planos,
  normativa, gestión, catálogo y ordenación detallada. Se agrupan en un POM.
- https://villanuevadelatorre.sedelectronica.es/transparency/7571a260-6591-4d23-af08-b92754508d1c/
  — MODIFICACIÓN ORDENANZA Nº 8, un documento; un instrumento separado.
- https://villanuevadelatorre.sedelectronica.es/transparency/a6193809-417b-4747-951c-ee0e11fa2509/
  — MODIFICACIÓN PUNTUAL POM. DESCLASIFICACIÓN SECTOR I-2, cuatro documentos;
  un instrumento separado, sin atribuirle una fase de aprobación.
- https://villanuevadelatorre.sedelectronica.es/preview-document/739ee7eb-0299-41e1-a139-20854ad11e93
  — vista pública de NORMATIVA URBANISTICA, HTTP 200, con visor PDF y descarga.
  La «Fecha de creación» 18-mar-2022 es metadato del documento electrónico;
  no se utiliza como fecha de aprobación ni publicación del instrumento.
- https://villanuevadelatorre.sedelectronica.es/board — tablón público paginado;
  comprobado para descubrimiento, no extraído. Incluye anuncio SI-03 pero la
  primera página no constituye inventario completo ni prueba de licencia.
- https://www.villanuevadelatorre.com/contacto/tramites-habituales/ — la consulta
  de descubrimiento muestra formularios de obra mayor/menor y declaración
  responsable, excluidos como licencias concedidas.

La búsqueda también localizó el registro autonómico PAU de Guadalajara
(https://urbanismo.castillalamancha.es/registros/pau-gu) y publicaciones BOP;
no se integran ni se atribuyen sus fechas a los documentos municipales.

## Método y semántica

Lee el recuento actual POM del índice, no fija el total observado en el código.
Abre su carpeta y sigue todos los botones «Mostrar más». Las respuestas XML de
Wicket se leen por sus componentes CDATA; no se ejecuta JavaScript. La tercera
página contiene únicamente dos subcarpetas: ambas se recorren y se conservan
como instrumentos independientes. La suma de documentos directos y subcarpetas
ha de coincidir con el recuento publicado; repeticiones, paginadores interminables,
estructuras ajenas o contenido ausente producen error antes de escribir salida.
No se corta silenciosamente la paginación.

Cada documento conserva título, enlace estable `preview-document` y carpeta de
procedencia. El identificador del instrumento deriva de la URL estable de su
carpeta. La actualización reemplaza la instantánea completa sin utilizar una
fecha de rastreo como fecha administrativa. No se afirma que el POM sea una
nueva promoción física. No se infiere vigencia legal, aprobación ni ejecución.
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan null.
Los planos se enlazan como documentos, sin inventar coordenadas ni digitalizar
geometría. `lat`, `lon` y `geometry` quedan null.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_villanueva_de_la_torre -v`: siete pruebas pasan:
  agrupación, campos desconocidos, CDATA, fin de paginación, recuentos dinámicos,
  subcarpetas sin documentos directos, incompletos/duplicados, formularios/login,
  noticias y enlaces ajenos.
- Extracción real mediante `VillanuevaDeLaTorreAyuntamientoAdapter.backfill_proyectos`:
  tres registros, 25 enlaces documentales, cinco páginas de carpetas, más el índice.
- `evidence/proyectos.jsonl`: registros reales; `evidence/validation.json`: conteo,
  URLs, limitaciones y resultado de pruebas. `evidence/live-*` conserva las
  respuestas HTML/XML del adaptador; las otras capturas documentan descubrimiento.
  Las URLs de acciones Wicket son efímeras; las carpetas y vistas documentales
  mantienen enlaces estables. Evidencia local, fuera de los cuatro fuentes.
