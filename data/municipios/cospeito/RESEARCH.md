# Cospeito — INE 27015, Lugo, Galicia

Verificación en vivo: 2026-11-09. Un solo adaptador municipal, cuatro archivos
fuente nuevos. Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

- Ayuntamiento: https://www.concellodecospeito.es/
- Urbanismo: https://www.concellodecospeito.es/es/servicios-de-urbanismo/
  Respuesta 200. Contiene comunicación previa, autoliquidaciones y modelos de
  solicitud. No acredita licencias concedidas; se excluyen todos esos formularios.
  La búsqueda municipal `/?s=pxom` respondió 403; no se usa como inventario.
- Inventario autonómico oficial: https://siotuga.xunta.gal/siotuga/urb
  La fila **27015 / Cospeito** enlaza el inventario municipal y señala Normas
  subsidiarias de planeamento, fecha 1997-04-14.
- Fuente ejecutada: https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=27015
  El formulario contiene la opción 27015 = Cospeito. El JavaScript público
  `https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js`
  documenta las consultas y la construcción de enlaces documentales.
- Inventarios POST: https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php
  con `id=27015`, `idclase=14,13,16,18`. Valor anti-CSRF público obtenido en
  sesión anónima desde el formulario; sin autenticación ni credenciales.
- Detalles POST: https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php
  con `iddoc` descubierto, `idp=0`, `lang=gl_ES`.

El editor real es **Xunta de Galicia**, no el ayuntamiento. El valor
`proyectos.source: ayuntamiento` mantiene la ruta local del contrato existente;
los registros identifican `source: siotuga`, editor y peticiones de procedencia.

## Cobertura y semántica

Se recorren íntegramente los arrays JSON de planeamiento general (14), desarrollo
(13), histórico (16) y delimitaciones rurales (18). El JS oficial aplica
DataTables en cliente sobre el array completo, sin peticiones por páginas.
No se impone tope de filas/documentos. Un sobre de paginación futuro, cambios de
identidad, conflictos de fechas o detalle sin documentos causan error antes de
reemplazar la salida. Las clases 16 y 18 devolvieron `null`, no páginas omitidas.
La actualización vuelve a consultar todo el inventario, no representa sólo altas.

Resultado real: **9 instrumentos, 188 enlaces documentales únicos por instrumento**:

| ID SIOTUGA | Instrumento | Aprobación definitiva según inventario |
| --- | --- | --- |
| 24320 | Normas subsidiarias de planeamento | 1997-04-14 |
| 24321 | MP NSP de Feira do Monte | 2002-01-29 |
| 24323 | Plan parcial Parque Empresarial de Muimenta | 1998-12-22 |
| 26300 | Plan de sectorización Parque Empresarial de Muimenta | 2007-11-08 |
| 26301 | Plan de sectorización en FM II de SUB (P/RI) | 2007-11-08 |
| 27774 | MP NSP para execución das sentencias 921 e 922 | 2012-10-26 |
| 27964 | MP NSP núcleos Broz, Carracido, A Escoleira, O Monte e Pereiras | 2014-10-20 |
| 28226 | MP NSP para DSNR da Fraga, San Martiño de Pino | 2019-06-20 |
| 28671 | Estudio de detalle rúa Curros Enríquez para definir aliñacións | 2024-09-26 |

Identidad por ID oficial, no por título: el plan parcial y el de sectorización
homónimos de Muimenta son instrumentos distintos. Memoria, normativa, planos,
índices y demás componentes se agrupan en `documentos`, conservando grupo, título,
ID y URL. No se crean proyectos por cada PDF o plano.

`fecha_aprob` procede de `fechaaddef`. BOP, DOG y publicación de normativa en BOP
tienen campos separados; `fecha` y `fecha_publicacion` genéricas quedan nulas.
No se inventan fechas de publicación municipal ni se confunde una publicación con
un acuerdo. Se conserva `fechatextodef` si existe. Por ejemplo, el estudio de detalle
28671 tiene aprobación 2024-09-26, DOG 2024-10-04 y BOP 2024-10-08.

La existencia de aprobación no significa vigencia íntegra actual: se conservan las
incidencias jurídicas originales, incluidas las exclusiones de ámbitos rurales,
úcleos urbanos, laguna y normativa de las NSP de 1997. No se asigna una fase de
vigencia universal. No se extraen licencias, contratación, noticias, obras físicas,
instrumentos territoriales del apartado IOT ni procedimientos ambientales de otros
inventarios de la Xunta. El inventario seleccionado no cubre por sí solo todo el
planeamiento en tramitación de 2026 ni el nuevo PXOM en elaboración.

## Geometría

`geometry_status: unavailable`. SIOTUGA ofrece visor y un enlace WMS por municipio;
no se ha verificado ni extraído una geometría vectorial vinculada por ID a estos
instrumentos. Los planos PDF/JPG se retienen como documentos, sin vectorizarlos.
Coordenadas y geometría nulas, `publication_ready: false`, sin jitter.

## Validación reproducible y evidencia local

`python -m unittest municipio.test_cospeito -v`: **4 pruebas pasan**. Cubren
identidad municipal y documental, fechas distintas, conservación de incidencias,
agrupación y deduplicación, rechazo de sobres de paginación/detalles incompatibles,
consulta de las cuatro clases y manifest. Fixtures sintéticos, sin depender de
capturas locales ni de red para las pruebas.

Extracción real mediante `load_manifest('cospeito')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`portal.config.capture_dir='evidence/live'` únicamente durante la validación.
La política compartida devuelve estado `ok`, 9 totales, 3 `unknown`; esos registros
se retienen sin alterar la política común. La evidencia no implica aprobación de
publicación y requiere revisión independiente.

- `evidence/proyectos.jsonl`: nueve registros reales con sus documentos.
- `evidence/validation.json`: conteo, URLs, limitaciones, resultado y comprobaciones.
- `evidence/live/`: formulario, cuatro arrays y nueve detalles JSON del mismo run.
- `evidence/inventario.js`, `siotuga.html`, `urbanismo.html`: descubrimiento.
- `evidence/curros-source.pdf`: índice oficial del estudio de detalle.

Se comprobó un PDF por instrumento: nueve respuestas 200 con tipo
`application/pdf`; no se descargaron todos los 188 documentos. Evidencia local,
excluida de Git. `schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`. Sin cambios compartidos ni dependencias nuevas.
