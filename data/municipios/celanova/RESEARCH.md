# Celanova — Ourense — INE 32024

Verificado en vivo el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Cobertura deliberadamente parcial: planeamiento municipal publicado en SIOTUGA,
no un registro completo de obras ni de licencias concedidas.

## Descubrimiento y procedencia oficial

- https://www.celanova.gal/ redirige a
  https://www.celanova.gal/index.php/gl/ (HTTP 200). Su enlace **Urbanismo**
  dirige a https://siotuga.xunta.gal/siotuga/inventario.php.
  Captura local: `evidence/www.celanova.gal.html`.
- https://siotuga.xunta.gal/siotuga/urb (HTTP 200): la tabla identifica exactamente
  **32024, Celanova**, Plan xeral de ordenación urbana, aprobación 1995-05-09,
  y enlaza su inventario municipal. No se usa la fecha del rastreo como fecha del plan.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=32024
  (HTTP 200): formulario público del inventario de la Xunta. El adaptador verifica
  la opción Celanova/32024 y utiliza el nonce anónimo del formulario como el JS
  público; no utiliza acceso autenticado.
- El JS oficial `assets/inventario/controls.min.js?2.5.0` muestra las consultas
  POST a `assets/inventario/query_document.php` con `id=32024`, `idclase` y
  el nonce del formulario. Clases consultadas íntegramente: **14 general**,
  **13 desarrollo**, **16 histórico**, **18 delimitaciones de núcleos rurales**.
  Devuelve arrays completos (o `null` sin resultados); DataTables pagina en el
  cliente. No hay límite de filas ni corte de páginas en el adaptador. Una nueva
  respuesta paginada con envoltorio JSON falla para revisión, en vez de truncarse.
- Cada entrada se completa mediante POST a `assets/inventario/getIOTPU.php`,
  `iddoc=<ID>`, `idp=0`, `lang=gl_ES`. Se comprueban ID, municipio, carpeta,
  denominación, figura y aprobación contra el inventario.
  Los enlaces se construyen exactamente como el visor, con `filesroot`, `folder`
  y `elementos[].componentes[].pathesperado`. Se conservan títulos, grupos y URL
  de documentos PDF e imágenes, agrupados dentro de su instrumento.
- https://celanova.sedelectronica.es/ devuelve HTTP 200 y redirige a `/info.0`.
  Se observa catálogo de trámites y enlace a transparencia, no un inventario
  verificado de licencias concedidas. No se convierte ningún formulario en licencia.
- `www.concellodecelanova.gal`, referenciado por un directorio externo, no resolvió
  DNS en esta comprobación. Se usa la web municipal operativa `www.celanova.gal`.

Los IOT territoriales/sectoriales que el mismo visor consulta se investigaron
(`evidence/iot.json`), pero están fuera del alcance del adaptador municipal:
no se presentan planes regionales de aplicación general como proyectos locales.
No se extraen noticias, anuncios de contratación ni trámites.

## Cobertura y agrupación

La ejecución devuelve **12 entradas**, **11 instrumentos** y **364 enlaces**:

| ID SIOTUGA | Instrumento |
| --- | --- |
| 22685 | PXOU, revisión y adaptación (1995) |
| 25642 | Modificación PXOU entre Casas Baratas y campo de fútbol, segunda modificación |
| 22686 | Modificación PXOU entre Casas Baratas y campo de fútbol |
| 22597 | Modificación PXOU entreplanta entre Avda. San Rosendo y Rúa do Cerado |
| 22598 | Modificación PXOU SUNP parque empresarial |
| 24377 | Plan parcial parque empresarial |
| 24380 | Plan especial del burgo medieval de Vilanova dos Infantes |
| 24378 | Plan especial del entorno del Mosteiro de San Salvador |
| 26594, 26589 | Estudio de detalle de parcela sanitaria S-3 y conexiones viarias |
| 26556 | Estudio de detalle alineaciones Francisco González Rey–San Torcuato–Mourillos |
| 25418 | Estudio de detalle alineaciones de la zona oeste |

General: 5 entradas; desarrollo: 7; histórico y delimitaciones: `null`.
Los IDs **26594 y 26589** tienen idéntica figura, denominación y aprobación
(2008-07-21), y los mismos autores; uno añade la publicación DOG. Se agrupan
sin perder ninguno de los IDs ni sus fechas originales. Cambios de denominación,
figura o aprobación generan instrumentos separados; las modificaciones no se
fusionan con el PXOU original. La identidad estable se deriva de esa clave
semántica, conservando todos los identificadores de la fuente.

Los estudios de detalle 25418, 26556 y el grupo 26594/26589 tienen metadatos de
aprobación pero `elementos: null`: se conservan como instrumentos reales con
`documentos: []`, explicitando que faltan adjuntos digitalizados. No se promete
que la ausencia de incidencias jurídicas demuestre vigencia legal actual.

`fecha_aprob` procede exclusivamente de `fechaaddef`. Las fechas BOP, DOG y
BOP normativa se conservan como publicaciones separadas con su medio y dossier
origen; `fechatextodef` se conserva en procedencia. `fecha`, `fecha_acuerdo` y
`fecha_publicacion` genérica quedan nulas. No se deduce la fecha del acuerdo de
la fecha de aprobación ni se escoge arbitrariamente una publicación.
La fuente efectiva se declara como **Xunta de Galicia — SIOTUGA**, aunque el
canal del pipeline es `ayuntamiento` por el enlace municipal al inventario.

No se han obtenido coordenadas ni geometrías vectoriales verificadas de los
instrumentos. Se retienen planos escaneados como documentos, sin convertirlos
en geometría. `lat`, `lon`, `geometry` son nulos y `publication_ready` es falso.
`schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` son falsos.
Las actualizaciones refrescan el mismo inventario completo; no se afirma que
este snapshot sea un histórico de altas y bajas ni un incremental por fecha.

## Verificación reproducible y evidencia local

- `python -m unittest municipio.test_celanova -v`: **8 pruebas pasan**;
  fechas distintas, agrupación de dossiers, conservación de adjuntos, ausencia de
  documentos, errores de identidad/municipio, rechazo de esquemas paginados y
  formularios, más de 150 filas sin truncar, origen documental y manifest.
- Ejecución real de `CelanovaAyuntamientoAdapter(config={'evidence_dir':
  'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  **11 registros**, 12 entradas del inventario, 364 enlaces, 3 registros sin adjuntos.
- `evidence/validation.json` contiene recuento real, URLs fuente, limitaciones,
  resultados de pruebas y muestras documentales. `live-class-*.json` y
  `live-detail-*.json` capturan las respuestas utilizadas por el adaptador.
  El HTML y JS públicos investigados también se conservan en `evidence/`.
- Se comprueban tres PDF enlazados mediante descarga real y cabecera `%PDF`;
  no se afirma haber descargado ni validado todos los 364 adjuntos.

La evidencia es local, fuera de los cuatro ficheros fuente entregados.
