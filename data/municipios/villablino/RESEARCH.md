# Villablino — INE 24202, provincia de León

Verificado en vivo el 2026-11-08 con el entorno preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Cobertura parcial de instrumentos urbanísticos; no registro de licencias concedidas.
El adaptador implementa el contrato de `municipio/adapters/portal.py` y se carga
mediante el manifiesto, sin modificar el registro compartido ni dependencias.

## Fuentes oficiales descubiertas

- [Urbanismo municipal](https://www.aytovillablino.com/pagina-principal/areas-municipales/urbanismo/)
  devuelve HTTP 200. Identifica Villablino, INE 24202, y enlaza expresamente el
  archivo de planeamiento de la Junta. Ofrece además un cartel de licencia,
  un anuncio de información pública de autorización de uso excepcional
  (1527/2024) y una memoria de telecomunicaciones. No acreditan concesión de
  licencias y quedan excluidos. La revisión del PGOU se presenta con acuerdos
  inicial de 08-07-2010 y provisional de 27-01-2012, y orden de 10 de octubre
  publicada el 2 de noviembre; la fecha completa se obtiene del archivo regional,
  no se completa a partir del año del nombre del fichero.
- [Inventario PLAU municipal de la Junta](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion&pager.sortindex=-3&provincia=24&municipio=202&filtroSelDoc=TODOS)
  devuelve HTTP 200 y muestra VILLABLINO / Código INE 24202. Actualización visible
  del portal: 06-nov-2026 (no es fecha de acuerdo de ningún instrumento).
  «Todos los documentos», históricos desmarcados: seis entradas, una sola página.
  Las columnas distinguen explícitamente publicación y acuerdo.
- [Consulta con históricos](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=202&bIncluirHist=S)
  devuelve once entradas, incluidas versiones y modificaciones anteriores.
  Se investigó para delimitar cobertura, pero no se ingiere ese histórico.
- [Árbol de documentos](https://servicios.jcyl.es/PlanPublica/searchVDocJerarquiaPlau.do?provincia=24&municipio=202&bInfoPublica=N)
  devuelve una interfaz HTML con árbol dinámico; la extracción usa la tabla
  tabular del inventario y las listas de ficheros, no ese árbol.
- [Tablón municipal](https://aytovillablino.sedelectronica.es/board) devuelve
  HTTP 200, diez anuncios visibles y «Mostrar más». Incluye delegaciones,
  subvenciones culturales, cacerías y actas. No se ingiere ni se afirma haber
  recorrido ese tablón: requeriría paginación y análisis documental propios.
  El perfil de contratante enlazado en la web tampoco se ingiere como proyectos.

Las capturas de esta investigación están en `evidence/urbanismo.html`,
`planeamiento.html`, `historicos.html`, `tree.html` y `board.html`.

## Registros extraídos

| Instrumento | ID archivo | Publicación | Acuerdo | Enlaces a ficheros |
| --- | --- | --- | --- | --- |
| PGOU (revisión) | 288804 | 2012-11-02 | 2012-10-10 | 78 + 1 sentencia |
| Actuación y reparcelación UE-1, sector UPRS-2 | 285024 | 2010-03-04 | 2009-07-27 | 5 |
| Plan parcial sector UPSR 2 | 283850 | 2007-09-18 | 2007-08-27 | 5 |
| PPI UPSI-2 | 277351 | 1996-03-01 | 1996-02-01 | 3 |
| PP sector UPSR-4 | sin documento | sin fecha publicada | 1989-12-10 | 0 |

Se conservan las grafías UPRS/UPSR de cada título de origen. El PP UPSR-4 es una
entrada real con marcador explícito «No hay documentos»: no se inventa ID de
expediente ni URL documental. Su identidad técnica se deriva del tipo y título.

La sexta entrada, ID 292985, se titula «SENTENCIA DEL RECURSO Nº 2/2013 REFERIDO
A LA ANULACIÓN PARCIAL DEL PGOU. ENTRE LAS CALLES VIDALGUERA Y PERUCHAL». Se agrupa
con el único PGOU principal del inventario vigente, conservando título, ID,
publicación 2016-05-27 y acuerdo 2016-05-16 en `entradas_archivo`, y su fichero
como documento relacionado. No se genera otro proyecto ni se sustituye la fecha
del PGOU por la sentencia. El agrupamiento exige un único PGOU y el título
explícito de anulación parcial; una relación ambigua aborta la extracción.

Cada [lista de ficheros](https://servicios.jcyl.es/PlanPublica/ldoc_files.do?cDocId=288804)
se consulta en vivo; sus enlaces `openFichero.do?cFicheroId=…` y nombres se guardan
en `documentos`, con ID y URL del inventario padre. Se eliminan solamente los
parámetros efímeros `;jsessionid`. No se convierten planos o memorias en proyectos
independientes. Los 92 enlaces son enlaces publicados por el archivo; no se afirma
haber descargado o validado el contenido de cada PDF. El RAR municipal de 615 MB
se descubrió, pero no se descarga ni se necesita para extraer el inventario.

## Comportamiento y límites

- Instantánea completa del inventario vigente en cada backfill/update. No se
  presenta como histórico exhaustivo ni delta. Sin cobertura integral de obras.
- La página actual tiene seis filas frente al tamaño por defecto de quince.
  Ante enlaces con desplazamiento positivo, navegación «siguiente», o una página
  llena de quince filas, se aborta con error explícito para ampliar el recorrido;
  no se devuelve una primera página truncada. Se comprueban también las listas
  de ficheros, que actualmente muestran todos sus enlaces sin paginación.
- Identidad municipal, encabezados, tipos, fechas y relación con cada lista de
  ficheros se validan. Cambios de esquema, páginas vacías, enlaces ambiguos y
  respuestas de acceso fallan. Peticiones con timeout de 40 s y límite de 4 MB
  de HTML. Sólo se reemplaza el JSONL después de completar todas las consultas.
- `fecha_publicacion` y `fecha_acuerdo` mantienen el significado de sus columnas.
  `fecha`, `fecha_aprob` y `fase` quedan nulas: el inventario no precisa la fase
  de aprobación de cada acuerdo. La sentencia tiene sus fechas propias anidadas.
- No se extraen coordenadas de mapas, centroides o planos no interpretados.
  `lat`, `lon`, `geometry` son nulos y `publication_ready` es false. Licencias,
  programación y jitter están desactivados en el manifiesto.

## Validación reproducida

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villablino -v`

Seis pruebas offline correctas: fechas distintas/ausentes e identidad estable;
agrupación de sentencia con documentos y fechas independientes; rechazo de
formularios, municipios y columnas incorrectos; rechazo de paginación y duplicados;
retención de todos los ficheros y validación de procedencia; carga por manifiesto,
actualización, licencias deshabilitadas y conservación del resultado ante errores.
Las pruebas contienen fixtures sintéticos, no dependen de las capturas locales.

Extracción real mediante `load_manifest('villablino')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: cinco registros, seis
entradas fuente, 92 enlaces documentales, cero coordenadas. Los campos de política
de entidad añadidos por el cargador compartido quedan `unknown` (5/5); no se ha
forzado una categoría de construcción para instrumentos de planeamiento.

`evidence/validation.json` conserva `live_records`, URLs, límites, recuento de
pruebas y timestamp de extracción. `evidence/live_inventory.html` y
`evidence/live_files_*.html` contienen las respuestas de esta ejecución. Toda la
evidencia permanece local y no forma parte de los cuatro ficheros fuente.
