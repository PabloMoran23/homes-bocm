# Cervo — Lugo — INE 27013

Verificado el 2026-11-09. Se implementa un único adaptador municipal, basado en el
inventario oficial de planeamiento de la Xunta. Cobertura parcial, sin publicación.

## Descubrimiento y fuentes

- Web municipal actual: https://www.concellodecervo.com/gl (HTTP 200).
  Su navegación enlaza noticias, sede, tablón y perfil del contratante; no se
  convierte ninguna noticia, formulario o licitación en licencia concedida.
- Urbanismo SIOTUGA: https://siotuga.xunta.gal/siotuga/urb (HTTP 200).
  La fila 27013 identifica Cervo y enlaza su inventario; la síntesis muestra NSP,
  1978-07-12. Esa fecha NO se aplica a los demás instrumentos.
- Inventario municipal:
  https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=27013
- Código público de navegación que documenta las consultas:
  https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0
- Consulta JSON de instrumentos (POST):
  https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php
  con `id=27013`, `idclase=14`, `13` o `18`.
- Ficha y documentos (POST):
  https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php
  con `iddoc=<id de inventario>`, `idp=0`, `lang=gl_ES`.

Las consultas usan el nonce del formulario anónimo público, sin autenticación ni
credenciales. Las capturas del adaptador omiten su valor. Se valida también la
identidad Cervo/CERVO de cada ficha, no sólo el texto de su título.

## Cobertura real y agrupación

La ejecución real devuelve **30 instrumentos**: 12 de planeamiento general (clase
14), 18 de desarrollo (13), y ninguno de delimitación de núcleo rural (18, JSON
`null`). Incluye NSP, modificaciones puntuales, planes parciales/especiales y
estudios de detalle. Fechas de aprobación del catálogo: 1978-07-12 a 2022-06-03.
Ejemplos: MP NSP para ampliación do Museo do Mar (28439); PEID para acondicionamento
da estrada As Quintás (28469); PE do Xacemento da Atalaia (28536).

Se agrupan **397 entradas documentales** bajo sus instrumentos, conservando el ID,
título, grupo y enlace del catálogo. Una misma URL puede tener varias etiquetas
originales; no se pierden al deduplicar. No son 397 proyectos. Ocho instrumentos
(24307, 24309–24314 y 25385) tienen `elementos: null`: se conservan sus fichas,
fechas y procedencia, con documentos vacíos y `documentos_status` explícito. No se
inventan adjuntos. Se verificaron además dos PDF enlazados (memoria NSP 24303 y
memoria PEID 28469): HTTP 200, tipo PDF y firma `%PDF`; capturados bajo `evidence/`.
El resto de enlaces procede de las fichas y no se ha descargado íntegramente.

No hay paginación de servidor en estas consultas: el JavaScript recorre todos los
objetos del array y después aplica DataTables en cliente. Se consume el array
completo de cada clase, sin límites ni selección por fecha. Un sobre paginado o
cambio de esquema se rechaza; no se trata como cero resultados. IDs duplicados
contradictorios y diferencias ficha/inventario fallan antes de sustituir la salida.
Las actualizaciones vuelven a obtener la instantánea completa; no usan un cursor
que omita modificaciones de instrumentos antiguos.

## Semántica y límites

- `fecha_aprob` procede de `fechaaddef` (aprobación definitiva según el catálogo).
  BOP, DOG y publicación normativa tienen campos distintos. No se conoce la fecha
  de publicación de la ficha ni una fecha de acuerdo independiente: quedan nulas.
- No se afirma plena vigencia de todo lo aprobado. Se conservan las incidencias
  jurídicas, incluida la sustitución de planos y normativa del plan de Cuiña 24316.
- Se excluye expresamente la clase histórica 16 (dos entradas observadas, una
  adaptación anterior a la segregación de Burela). Tampoco se extraen instrumentos
  territoriales supramunicipales, obras ejecutadas ni planeamiento en trámite.
- Se descubrió una consulta ambiental actual para el parque da Veiga, expediente
  2026AAE3089, código 2879/2026, en el inventario de consultas de la Xunta:
  https://medioambiente.xunta.gal/programas-con-periodo-de-consulta-aberto
  No forma parte del inventario de planeamiento aprobado y no se incorpora como
  aprobación ni obra ejecutada. Esta fuente no implica cobertura de todos los
  proyectos actuales del municipio.
- Los IDs SIOTUGA son identificadores oficiales de catálogo, no números de expediente
  administrativo. El adaptador no inventa estos últimos. Al ejecutar mediante el
  registro compartido, la política de entidades clasifica los 30 como `pendiente`
  (`adapter_incident`, `unknown_entity_spike`), porque no reconoce esta identidad
  de catálogo. Se deja visible en las evidencias para revisión independiente;
  no se modifican reglas compartidas ni se fuerza su elegibilidad.
- Cero licencias: no se ha verificado un registro de concesiones. Formularios,
  anuncios de contratación y noticias no constituyen concesiones.

## Geometría

`geometry_status: unavailable`. SIOTUGA ofrece visor y WMS por municipio (enlace
WMS de la fila 27013). Su configuración pública advierte que la cartografía
vectorial derivada no tiene validez legal y puede tener errores de posición:
https://siotuga.xunta.gal/siotuga/conf/config.js
No se ha verificado ni extraído una geometría enlazada a cada ID del inventario.
Los planos PDF/JPG se conservan como documentos; no se vectorizan ni se atribuyen
coordenadas del centro municipal. `lat`, `lon` y `geometry` quedan nulos;
`publication_ready: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_cervo -v` — **6 pruebas pasan**.
Cubren agrupación de documentos, identidades, fechas separadas, documentos ausentes
explícitos, cambios de esquema/paginación, contradicciones y licencias deshabilitadas.

Extracción real mediante `load_manifest('cervo')` y `load_portal_adapter(manifest)`;
`manifest.portal.config['capture_dir']='evidence/live'`;
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
No se usa orquestador, base de datos ni publicación.

Evidencia local no versionada: `evidence/proyectos.jsonl` (30 registros),
`evidence/validation.json` (recuento, URLs, límites, pruebas, clasificación y
comprobaciones de documentos), y `evidence/live/` (inventario, tres consultas
completas y 30 fichas). `schedule.enabled: false`, `licencias.enabled: false`.
