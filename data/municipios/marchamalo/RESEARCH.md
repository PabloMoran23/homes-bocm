# Marchamalo — INE 19171, Guadalajara

Verificación: 2026-11-08. Adaptador de cobertura parcial del inventario municipal
de planeamiento; no es un registro de licencias ni un inventario completo de
obras públicas. Se conserva la identidad municipal exacta. Ejecución programada,
licencias y desplazamiento de coordenadas ausentes están desactivados.

## Fuentes oficiales descubiertas

- Inventario utilizado: https://www.marchamalo.com/ayuntamiento/normativa/normativa-urbanistica/
  (HTTP 200). Publica un listado explícito de normativa urbanística municipal,
  dividido en PGOU, planes parciales, planes especiales y estudios de detalle.
  Los documentos están en Drive, pero su procedencia es el enlace publicado por
  el propio Ayuntamiento. No se emplea una búsqueda de archivos de terceros.
- PGOU: https://drive.google.com/folderview?id=0Bzlq8p7yDfqDMjFPbTFzNTJlZ28&usp=sharing
  (HTTP 200, redirige a `/drive/folders/…`). La carpeta pública muestra
  `P.G.O.U..pdf`, Uso Industrial, Modificaciones y Criterios Interpretativos.
  Se conserva como una referencia documental del PGOU, sin recorrer su contenido.
- Colecciones generales enlazadas por el inventario:
  [planes parciales](https://drive.google.com/folderview?id=0Bzlq8p7yDfqDMldLajlCbFVGYW8&usp=sharing),
  [planes especiales](https://drive.google.com/folderview?id=0Bzlq8p7yDfqDb2MzTGJZYXVtYW8&usp=sharing),
  [estudios de detalle](https://drive.google.com/folderview?id=0Bzlq8p7yDfqDXzFKWWIzVHd4UmM&usp=sharing).
  Son índices generales, no instrumentos adicionales. No se enumeran sus
  contenidos y no se afirma haber completado el archivo documental de Drive.
- Página municipal de transparencia:
  https://www.marchamalo.com/ayuntamiento/normativa/portal-de-transpariencia/
  (HTTP 200), enlaza a https://marchamalo.sedelectronica.es/transparency/
  (HTTP 200). La sede muestra la categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO
  AMBIENTE (20)» con expansión mediante Wicket AJAX y enlaces dependientes de
  sesión. Esta implementación no expande ese árbol: sus 20 documentos no están
  incluidos ni se interpretan como 20 proyectos o licencias concedidas.
- Registro autonómico contrastado:
  https://urbanismo.castillalamancha.es/registros/pau/pau-de-los-sectores-spod56-oeste-del-canal-y-sppp52
  (HTTP 200), expediente PAU de esos sectores de Marchamalo. Es una fuente
  complementaria descubierta, no incluida en este adaptador. No se fusiona un
  programa de actuación urbanizadora con un plan parcial por compartir sector.

## Cobertura y semántica

La extracción real devuelve **11 registros y 14 referencias documentales**:

- Un PGOU, con su carpeta general y los tres enlaces subordinados de Uso
  Industrial, Modificaciones y Criterios interpretativos agrupados en
  `documentos`. Las modificaciones no se inventan como instrumentos individuales
  a partir del nombre genérico de una carpeta.
- Ocho planes parciales: SP.pp.41; SP.pp.52 y SP.od.56; SP.od.52 y 54; SP.od.55;
  SP.od.50 y SP.pp.50; SP.pp.51; SP.od.53; SP.pp.53. Se respeta la denominación y
  agrupación de sectores de la fuente; no se separa un PDF común en varios planes.
- Dos estudios de detalle: SUE 551 y SUE 555.

Cinco denominaciones carecen de enlace documental y se excluyen, con reporte
explícito en `unlinked_entries`: SP.od.51, PERI, SUE 500, SUE 552 y SUE 557.
No se convierten las categorías generales, solicitudes, navegación o anuncios
de contratación en instrumentos. Los 14 enlaces documentales extraídos
respondieron HTTP 200; las páginas públicas de Drive muestran títulos de PDF o
carpetas concordantes. No se han descargado ni interpretado los PDF, de modo que
la validación es del inventario y sus referencias, no de su contenido jurídico.

La presencia en «Normativa Urbanística» no prueba por sí sola vigencia legal ni
una fase de aprobación concreta. `fase`, `fecha`, `fecha_publicacion`,
`fecha_acuerdo` y `fecha_aprob` quedan a null. Las fechas de creación/modificación
de WordPress o de archivos Drive no se convierten en fechas de aprobación ni
publicación del instrumento. No hay coordenadas o geometría verificadas:
`lat`, `lon`, `geometry` son null y `publication_ready` es false.

## Implementación y validación

Se usa únicamente el bloque municipal `#main-content-block`, sus categorías y
las denominaciones vinculadas. Cada documento retiene URL original, título,
identificador Drive, tipo de referencia y URL municipal de procedencia. Las
repeticiones de un instrumento se agrupan, y sus documentos se deduplican por
identificador Drive. Los IDs de registros se derivan del tipo y denominación,
independientes del parámetro de compartición del enlace.

El inventario municipal revisado es una única página sin paginación. Si aparece
paginación, cambia una categoría, se pierde la estructura esperada o aparece
un alojamiento documental desconocido, se produce un error explícito. No hay
un límite de registros que corte resultados. No se realiza una búsqueda
incremental por fechas: `update_proyectos` vuelve a leer el inventario completo.
La escritura sustituye el archivo después de validar la respuesta; un fallo de
red o parser conserva la extracción anterior.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- Pruebas: `-m unittest municipio.test_marchamalo -v`, 7 pruebas correctas:
  agrupación/deduplicación, exclusiones, fechas y geometría ausentes,
  identidad estable, variantes de carpetas Drive, rechazo de cambios/paginación,
  conservación de salida ante errores y contrato del manifest/licencias.
- Extracción real mediante `MarchamaloAyuntamientoAdapter.backfill_proyectos`:
  11 registros. El manifest se carga con `load_manifest('marchamalo')`.
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/normativa-urbanistica.html`, capturas
  `source-00.html` a `source-15.html` y `transparency.html`. La validación contiene
  URLs completas, estados HTTP, títulos, número de registros y limitaciones.

No se han modificado dependencias ni código compartido. No se han utilizado
credenciales, bases de datos, publicación, despliegues ni operaciones remotas Git.
