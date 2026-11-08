# Salvaterra de Miño — Pontevedra — INE 36050

Verificado en vivo el 2026-11-07. Adaptador de un único municipio: inventario
urbanístico SIOTUGA de la Xunta, expresamente enlazado por el Concello. Cobertura
parcial de planeamiento, incluido un proyecto histórico. No es un inventario de
licencias concedidas ni de obras municipales recientes. Programación y jitter
geográfico deshabilitados; `publication_ready: false` por ausencia de geometría
verificada.

## Descubrimiento de fuentes oficiales

- https://www.concellodesalvaterra.com/ — HTTP 200. Menú Urbanismo y enlace al
  inventario municipal de planeamiento. Captura `evidence/home.html`.
- https://www.concellodesalvaterra.com/departamentos/urbanismo — HTTP 200. Describe
  funciones del servicio y enlaza «Acceda ao Planeamento Urbanístico de Salvaterra
  de Miño». El texto de funciones no contiene proyectos ni licencias concedidas y
  no se transforma en registros. Captura `evidence/discovery-0.html`.
- El enlace municipal histórico es
  `http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php?idconcello=36050&inv=1`.
  Su variante HTTPS falla por certificado de hostname. No se desactiva TLS.
- https://siotuga.xunta.gal/siotuga/inventario?idconcello=36050&inv=1 — HTTP 200,
  portal actual SIOTUGA con selector INE 36050 = Salvaterra de Miño. El antiguo
  sufijo `inventario.php` en este dominio también muestra el formulario; el
  adaptador usa la ruta actual. Captura `evidence/siotuga-inventory.html`.
- https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0 — JS
  público del buscador, capturado en `evidence/inventario.js`. Documenta los cuatro
  POST de planeamiento y la construcción de enlaces de archivos en cada ficha.
  La interfaz recibe arrays completos y después pagina mediante DataTables en el
  cliente; no hay límites de filas ni bucles de paginación omitidos.
- https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php — POST
  público `id=36050`, `idclase=14,13,16,18`, con nonce anónimo obtenido del propio
  formulario. Respuestas completas capturadas en `evidence/inventory-*.json`.
- https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php — POST público
  `iddoc=<id de inventario>`, `idp=0`, `lang=gl_ES`, mismo nonce. Una ficha por
  instrumento, capturada como `evidence/detail-<id>.json`. No se usa autenticación.
- https://siotuga.xunta.gal/siotuga/documentos/urbanismo/SALVATERRADEMINO/documents/0922me001.pdf
  — muestra real de memoria del instrumento 22965, HTTP 200, `application/pdf`,
  184639 bytes, guardada en `evidence/sample-document.pdf`. Los otros enlaces se
  retienen tal como los publica la ficha, sin afirmar que se hayan descargado o
  interpretado individualmente.

## Resultado y agrupación

Snapshot de los cuatro inventarios urbanísticos completos:

| Clase | Contenido | Instrumentos |
| --- | --- | ---: |
| 14 | Planeamiento general | 11 |
| 13 | Planeamiento de desarrollo | 2 |
| 16 | Planeamiento histórico | 1 |
| 18 | Delimitaciones de núcleo rural | 0 (respuesta null) |

Total: **14 instrumentos, 196 enlaces documentales**. Un registro por ID de ficha
SIOTUGA, no por PDF, plano o publicación. Los componentes conservan título, URL,
ID de componente y secciones. Las modificaciones son instrumentos propios; no se
fusionan por compartir fecha o lugar con un plan parcial. El ID SIOTUGA se etiqueta
como identificador de catálogo, nunca como número de expediente municipal.

Incluye las Normas Subsidiarias (22965), diez modificaciones (28266, 28267, 27639,
27331, 26684, 26679, 25782, 22966, 22969, 22968), el Plan Parcial Zona Industrial
Chan da Ponte (24515), el Estudio de Detalle en Rosalía de Castro/Fontoura (25696)
y el Proyecto de Urbanización y Ensanche de Salvatierra del Miño de 1959 (27080).
Su presencia en el inventario no acredita vigencia jurídica actual, inicio de
obra, terminación ni concesión de licencia.

Las fichas 28267 y 25696 tienen metadatos de instrumento y fechas pero no
componentes documentales publicados; se conservan con `documentos: []` y aviso.
La ficha 22965 agrupa 129 componentes, incluidos planos JPG, memorias y normativa;
no se convierten esos archivos en 129 proyectos.

## Fechas, procedencia y límites

- `fechaaddef` se conserva en `fecha_aprob`; BOP, DOG y publicación de normativa
  BOP se conservan por separado. El adaptador deja `fecha`, `fecha_publicacion`
  genérica y `fecha_acuerdo` nulas para evitar elegir una publicación o inventar
  un acuerdo. `fechatextodef` se conserva como `fecha_texto_refundido`.
- El registro 27639 publica aprobación 2011-11-30, DOG 2011-10-14 y BOP 2011-11-02.
  Se señala la cronología contradictoria de la fuente; no se corrige por conjetura.
  Las NSP 22965 indican aprobación 1993-06-12 y BOP 1993-07-26.
- Cada registro conserva el editor Xunta/SIOTUGA, la página municipal que lo
  enlaza, los endpoints, parámetros públicos sin nonce y el mapeo de fechas.
  `source: ayuntamiento` identifica la vía de integración municipal, mientras que
  `source_publisher` identifica quién mantiene realmente los documentos.
- No se han extraído coordenadas o polígonos de los planos escaneados. `lat`,
  `lon` y `geometry` son nulos; no se usa un centroide municipal.
- No incluye el inventario territorial separado de SIOTUGA ni expedientes de
  evaluación ambiental. La búsqueda oficial localizó una ficha de modificación
  puntual 12 en la Xunta, fuera de los arrays urbanísticos consultados:
  https://medioambiente.xunta.gal/ultimos-plans-e-programas-abertos?_aaeLast_WAR_aae__spage=%2Fportlet_action%2Faae%2FdetalleProxecto%3Fid%3D2503&_aaeLast_WAR_aae_id=2503&p_p_col_count=1&p_p_col_id=column-2&p_p_id=aaeLast_WAR_aae&p_p_lifecycle=0&p_p_mode=view&p_p_state=normal
  No se afirma que las 14 fichas agoten el planeamiento o sus trámites actuales.
- No se ha verificado un registro público de licencias otorgadas. Formularios,
  perfil de contratante, anuncios de contratación y noticias ajenas a instrumentos
  concretos quedan fuera. `licencias.enabled=false`; sus métodos emiten vacío
  explícitamente deshabilitado.

## Comportamiento y validación

Los cuatro inventarios se consultan en cada backfill/update como snapshot
completo. Se deduplican IDs idénticos, conservando todos los instrumentos. Se
rechazan respuestas paginadas de estructura nueva, HTML de acceso, identidad o
municipio discordantes, fechas inválidas, discrepancias inventario/ficha y rutas
de documentos inesperadas. Un fallo aborta antes de reemplazar la salida previa.
No hay truncado, caché como sustituto de extracción ni fixtures en la salida real.

Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_salvaterra_de_mino -v`: **11 pruebas aprobadas**.
  Cubren semántica y ausencia de fechas, cronología contradictoria, agrupación de
  componentes, identidad/municipio, enlaces, schema/paginación, más de una página
  de resultados, refresh y opciones obligatorias del manifest.
- `SalvaterraDeMinoAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`
  con `config={'capture_dir': 'evidence'}`: **14 registros reales**, 196 enlaces,
  todas las fichas e inventarios capturados durante la propia extracción.
- `evidence/validation.json` documenta recuentos, fuentes, avisos, límites y hora
  UTC de la extracción. La evidencia es local y no se incorpora a fuentes.

Solo se añaden manifest, investigación, adaptador y pruebas de este municipio.
Sin cambios compartidos, dependencias, publicación, despliegue ni operaciones de
base de datos.
