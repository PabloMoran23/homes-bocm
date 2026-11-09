# Marina de Cudeyo — INE 39040, Cantabria

Comprobación: 2026-11-09. Un único adaptador municipal, basado en el archivo
oficial autonómico que el propio Ayuntamiento enlaza como planeamiento vigente.

## Descubrimiento y procedencia

- Inventario municipal de recursos de Urbanismo:
  https://marinadecudeyo.com/ayto/ayuntamiento/urbanismo/
  Ofrece catálogo rural, mapa, ampliación, plan vigente y avances del nuevo plan.
- Página municipal del PGOU:
  https://marinadecudeyo.com/ayto/municipio/pgou/
  Identifica el plan de 1987 y distingue la redacción de un nuevo PGOU.
- Destino oficial enlazado:
  https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/marinadecudeyo
- Inventario JSON descubierto en el JavaScript de esa página:
  https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=40
- Manual oficial:
  https://aplicacionesweb.cantabria.es/aucan/manual?nombreArchivo=ManualPublico.pdf

Las páginas municipales se consultaron mediante búsqueda y apertura web; los
intentos HTTP directos desde Python dieron 403 y conexión rechazada. No se usa
una copia del buscador para generar registros. La página AUCAN y su JSON se
obtuvieron directamente con HTTP 200 durante la extracción real.
El encabezado Marina de Cudeyo y el parámetro municipal 40 se validan antes de
extraer. No debe confundirse con Medio Cudeyo (39042).

## Cobertura y agrupación

Resultado real: **12 instrumentos, 128 enlaces documentales**:

- Revisión PGOU 1987: 88 documentos, incluidos planos de distintas fechas.
- Modificaciones puntuales 1, 2, 3, 4, 5, 6, 8 y 11: 35 documentos.
- Catálogo de edificaciones en suelo rústico: 1 documento.
- MP nº1 del catálogo (fichas 148 y 149): 3 documentos.
- PGOU 1984, sección «No Vigente»: 1 documento.

Se recorre todo el árbol, incluidos «Actual» y «No Vigente». La UI hace una sola
petición GET sin parámetros de página/tamaño. El JavaScript treeview utiliza
`downloadDocumento(node.id)` y la página define la descarga como
`/aucan/public/documento/download.do/{id}`. No hay recorte por número de registros,
fecha o número de documentos. Respuestas con envoltorio de paginación, nodos de
tipo desconocido o instrumentos sin documentos propios fallan explícitamente.

Cada carpeta de instrumento genera una fila; sus memorias, planos, publicaciones
y certificados permanecen en `documentos`, con ID oficial, título, URL y ruta del
árbol. Las modificaciones generan filas propias y conservan `instrumento_padre`;
sus documentos no se duplican dentro del PGOU o catálogo padre. Los IDs del
adaptador son hashes deterministas de la jerarquía de títulos de instrumentos,
no números de expediente oficiales inventados. Cambiar un título puede cambiar
su ID. Las carpetas agregadas MP 2 y MP 3 se mantienen agregadas: no se inventan
expedientes separados para cada submodificación mencionada en sus documentos.

## Fechas y límites

Se separa `fecha_acuerdo` (CRU o Ayuntamiento) de `fecha_publicacion` (BOC), a
partir de etiquetas explícitas de carpeta. No son fechas de subida a AUCAN ni de
concesión de licencias. `fecha` permanece nula y no se infiere `fecha_aprob` ni
fase a partir del tipo de instrumento. Para MP 2 y MP 3 hay múltiples fechas:
ambos campos escalares quedan nulos y se conservan las cadenas originales.
Cada título documental retiene sus propias fechas, sin propagarlas al instrumento.

Existe una discrepancia observable en MP 3: la carpeta indica BOC 09/09/1993 y
algunos documentos indican 03/09/1993. Se conservan ambos textos sin decidir cuál
corrige al otro. Como contraste documental se descargó el BOC del catálogo:
https://aplicacionesweb.cantabria.es/aucan/public/documento/download.do/31147
Su texto confirma acuerdo del Pleno de 25/08/2014 y publicación de 10/09/2014.
Solo se descargó ese PDF de contraste; los demás enlaces se conservan desde el
inventario, sin afirmar que todos sus binarios se hayan descargado o validado.

La cobertura es completa respecto al árbol recibido, **parcial respecto al
municipio**. No incluye avances del nuevo PGOU ni ampliaciones u otros documentos
municipales ausentes de AUCAN; tampoco es un inventario de obras físicas,
contratación o licencias concedidas. No se convierten formularios ni noticias en
proyectos. El manual presenta AUCAN como archivo informativo susceptible de
omisiones y errores; «Actual» conserva la clasificación de la fuente, no certifica
la vigencia jurídica. Actualización y backfill son instantáneas completas, sin
modificar el archivo de estado ni borrar la salida anterior ante fallo del parser.

`geometry_status: unavailable`: se enlazan planos PDF, sin geometría vectorial
verificada por instrumento. Latitud, longitud y geometría son nulas.
`schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`, `publication_ready=false`.

La política compartida `entity_policy` clasifica los 12 registros como pendientes
(`insufficient_identity_evidence`, `unknown_entity_spike` / `adapter_incident`):
no reconoció estos instrumentos de archivo con identidad de carpeta y sin número
de expediente. Se conserva ese resultado en la evidencia. No se inventan números
ni se altera la política para forzar elegibilidad. Requiere revisión independiente
antes de cualquier uso como actividad o publicación.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_marina_de_cudeyo -v` (6 pasan).
Cubren agrupación, procedencia, fechas, discrepancias, documentos duplicados,
sección no vigente, más de 100 documentos, errores estructurales, preservación
de salida ante fallo, licencias deshabilitadas y carga mediante manifiesto.

Extracción real: `load_manifest('marina-de-cudeyo')`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['evidence_dir']` apuntando al directorio local de
evidencia. La carga usa el registro compartido y conserva su anotación semántica.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/proyectos.entities.json`, `evidence/aucan.html`,
`evidence/planes.json`, `evidence/treeview.js`, `evidence/manual.pdf`,
`evidence/catalogo-boc.pdf` y sus extracciones de texto. La validación registra
recuento, URLs, limitaciones y resultado de la política compartida.
