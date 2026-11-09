# Cartes — INE 39018, Cantabria

Verificado el 9 de noviembre de 2026. Adaptador exclusivo de Cartes, con cobertura
parcial de instrumentos de planeamiento en AUCAN, archivo oficial del Gobierno de
Cantabria. No representa un registro de licencias concedidas ni el conjunto de obras
municipales. Extracción real: **16 instrumentos, 114 enlaces documentales**.

## Inventarios oficiales examinados

- https://cartes.es/ — web del Ayuntamiento, identifica su dirección en Cartes,
  Cantabria. Archivo de noticias paginado (186 páginas en esta visita); no se usa
  como inventario de proyectos ni se presenta su primera página como histórico.
- https://cartes.es/pgou/ — HTTP 200, título PGOU pero contenido vacío y aviso de
  modificación de la web. No acredita un PGOU vigente; antiguos PDF indexados por
  buscadores no se convierten en un plan aprobado.
- https://cartes.sedelectronica.es/transparency — HTTP 200; categoría «7. URBANISMO,
  OBRAS PÚBLICAS Y MEDIO AMBIENTE (0)». No se deduce ausencia de proyectos municipales.
- https://cartes.sedelectronica.es/citizen-service/9a56d75c-ff9b-47a4-84ec-65cdb7a27626
  — trámites urbanísticos, ejecución de obras y primera ocupación. Son servicios,
  no concesiones de licencia; excluidos.
- https://cartes.sedelectronica.es/board — tablón actual, diez filas y «Mostrar más».
  No se extrae ni se afirma cobertura completa del tablón. Notificaciones de
  disciplina urbanística, subvenciones y convocatorias no son proyectos.
- https://ayuntamientocartes.transparencialocal.gob.es/ — enlazado por el Ayuntamiento,
  pero el certificado TLS caducado impide la consulta verificada. No se desactiva TLS.
- https://aplicacionesweb.cantabria.es/aucan/public/home — archivo urbanístico
  oficial; el selector identifica Cartes con valor 18. Su formulario de búsqueda
  pública redirige a la página municipal indicada a continuación.
- https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/cartes — HTTP
  200; encabezado Cartes, árbol de planeamiento y código público que solicita
  `/aucan/public/planes` con `idMunicipio: '18'`.
- https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=18 — HTTP
  200 JSON: árbol completo con ramas Actual, En Trámite y No Vigente. No tiene
  paginación ni peticiones diferidas por expansión: el JavaScript treeview recibe
  el array entero. Se inspeccionó también su implementación pública.

AUCAN advierte que su contenido es informativo, carece de efectos jurídicos
vinculantes y puede contener errores o desactualización. «Actual» se conserva como
clasificación del archivo, sin certificar vigencia legal actual de cada instrumento.

## Registros y procedencia

Se extraen las Normas Subsidiarias, once modificaciones de éstas (números 2, 3, 5,
6, 7, 4, 8, 9, 10, 11 y 13), el Plan Especial y Catálogo del Conjunto Histórico de
la Villa de Cartes con su modificación nº 1, el Plan Especial de Riocorvo y el
Catálogo de Edificaciones en Suelo Rústico. Las ramas En Trámite y No Vigente no
contenían instrumentos documentados en la respuesta verificada; se recorren también.

Cada instrumento conserva todos sus documentos descendientes (memoria, normativa,
catálogo, anexos, planos y documentos ambientales), con identificador oficial del
fichero, título íntegro, ruta jerárquica, URL de descarga y URL del inventario.
Las modificaciones son instrumentos separados con la ascendencia del plan padre;
la subsanación de errores de las NNSS se retiene dentro de su registro padre. No
se crean proyectos separados a partir de cada plano, anexo o del proyecto de
clausura Dique Jaime incluido en la modificación 11.

Las URLs de descarga reproducen la función `downloadDocumento(idFichero)` de la
página oficial. Se comprobó en vivo el fichero 27103 (publicación BOC de la
modificación 9): HTTP 200, 101672 bytes y cabecera PDF. Captura local
`evidence/sample-27103.pdf`. Los otros 113 enlaces proceden del inventario; no se
ha descargado ni validado el contenido de todos ellos.

La identidad del registro es un hash de su ruta de instrumento, no un expediente
administrativo inventado. Cambiar el título o su ubicación en el archivo puede
cambiar el ID; añadir/reordenar documentos no lo cambia. El título de las
modificaciones mantiene su numeración original; no se presupone que sea número
de expediente municipal.

## Fechas, geometría y cobertura

Se separan `fecha_acuerdo` (rótulos CRU, CROTU, Ayto. o Cons. Gob. del título del
instrumento) y `fecha_publicacion` (rótulo BOC del mismo título). No se transforman
las fechas entre paréntesis sin rótulo de los documentos en acuerdos/aprobaciones.
Sus cadenas originales se conservan. Las fechas de carga del servidor, rutas de
WordPress y reloj de la sede no se usan. `fecha` y `fecha_aprob` quedan nulas;
`fase` solamente refleja la existencia de una carpeta «Aprobación definitiva».
Las fechas o avisos de documentos anexos no sobrescriben las del instrumento padre.

No se extrae geometría de los planos PDF ni se asignan centroides o coordenadas
ficticias. `lat`, `lon`, `geometry` son null y `publication_ready` false. Licencias,
programación y jitter están desactivados en el manifest. La fuente efectiva se
identifica como `gobierno_cantabria`; `proyectos.source: ayuntamiento` selecciona
la vía del adaptador de planeamiento municipal y no atribuye AUCAN al Ayuntamiento.

La anotación común `entity_policy` del cargador deja los 16 instrumentos en
`pendiente/insufficient_identity_evidence` y devuelve `adapter_incident` por el
porcentaje desconocido. Es una limitación de clasificación posterior: este archivo
no proporciona números de expediente compatibles con esa política. No se inventan
referencias para forzar elegibilidad. Los registros reales, su procedencia y los
PDF agrupados siguen disponibles en el JSONL para revisión independiente; no están
listos para publicación automática.

## Funcionamiento y validación

Backfill y update renuevan el árbol completo con dos GET verificados, timeout de
40 segundos y control de tamaño. Se comprueba el encabezado municipal y su enlace
al API. Cambios de estructura, clasificación desconocida, identificadores de
fichero inválidos, inventario vacío y marcadores de paginación/carga diferida
provocan error. No hay recorte a un número máximo de registros ni selección de
la primera página. El archivo de salida se reemplaza después de completar el
parseo; una consulta fallida conserva el snapshot anterior.

- Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
- `python -m unittest municipio.test_cartes -v`: 7 pruebas satisfactorias. Cubren
  agrupación de documentos y modificaciones, subsanación, semántica de fechas,
  estabilidad de identidad, todas las clasificaciones, rechazo de formularios,
  cambios de estructura/paginación, manifest y licencias desactivadas, y fallo de red.
- Extracción real mediante `load_manifest('cartes')`, `load_portal_adapter` y
  `backfill_proyectos`: 16 registros / 114 documentos; se verificó unicidad de IDs,
  INE 39018, presencia documental y ausencia de coordenadas.
- Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/aucan-cartes.html`, `evidence/aucan-planes.json`, capturas de descubrimiento
  y PDF de muestra. Evidencia fuera de los cuatro archivos fuente entregables.
