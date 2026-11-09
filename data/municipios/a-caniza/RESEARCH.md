# A Cañiza — INE 36009, Pontevedra (Galicia)

Investigación y extracción real: 2026-11-09. Un único adaptador municipal,
`municipio.adapters.a_caniza:ACanizaAyuntamientoAdapter`.

## Descubrimiento y fuentes

- Servicio municipal: https://www.caniza.org/es/servizos-tramites/urbanismo
  describe funciones, sin inventario de concesiones.
- Trámites: https://caniza.org/es/servizos-tramites/tramites/obras-e-urbanismo
  ofrece solicitudes. No se convierten en licencias concedidas ni proyectos.
- Inventario oficial autonómico:
  https://siotuga.xunta.gal/siotuga/urb?lang=es_ES
  contiene la fila INE **36009**, «Cañiza, A», y enlaza su inventario municipal.
- Fuente efectiva:
  https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36009&lang=es_ES
- La lógica pública del portal, `assets/inventario/controls.min.js?2.5.0`, muestra
  las consultas completas POST a `assets/inventario/query_document.php`
  (`id=36009`, `idclase=14,13,16,18`) y las fichas POST a
  `assets/inventario/getIOTPU.php` (`iddoc`, `idp=0`, `lang=es_ES`).
  Todas las rutas son relativas a https://siotuga.xunta.gal/siotuga/ .

Se usa una sesión anónima: el valor anti-CSRF público se obtiene del propio
formulario, sin credenciales ni autenticación; no se conserva en la evidencia
producida por el adaptador. Los JSON y parámetros estables de consulta quedan
vinculados a cada registro, incluidos el ID oficial y la clase del inventario.
La procedencia es **Xunta de Galicia / SIOTUGA**, no una afirmación de publicación
por el Concello. `proyectos.source: ayuntamiento` selecciona la ruta del adaptador
según el contrato existente; el registro declara `source: siotuga_xunta`.

## Cobertura y agrupación

Extracción en vivo mediante el cargador real de manifests y registro de adaptadores:
**7 instrumentos**, **230 enlaces documentales**, **2 instrumentos históricos**.

| ID SIOTUGA | Instrumento | Clase | Documentos |
| --- | --- | --- | ---: |
| 22807 | PLAN XERAL DE ORDENACIÓN MUNICIPAL | general | 101 |
| 27970 | MP PXOM NO ANTIGO MERCADO GANDEIRO | general | 12 |
| 26754 | CATALOGO DO PXOM | general | 2 |
| 27630 | O VIEIRO (Plan Sectorización) | desarrollo | 39 |
| 23942 | SOLO INDUSTRIAL (Plan Parcial) | desarrollo | 19 |
| 26442 | NORMAS SUBSIDIARIAS DE PLANEAMENTO | histórico | 32 |
| 22808 | NSP NUM 1 | histórico | 25 |

La clase 18 (núcleos rurales) devuelve `null`, sin registros. No hay un límite de
filas ni selección de la primera página: las cuatro consultas devuelven arrays
completos y DataTables pagina en el navegador. El parser rechaza un objeto/envelope
paginado para evitar aceptar un futuro cambio de esquema como listado completo.
Se agrupa por ID de instrumento, no por fichero. Se conservan grupos, referencias,
títulos y URLs de todos los componentes PDF/JPG y se deduplican URLs dentro de la
ficha sin perder sus referencias. Las modificaciones con ID propio permanecen
separadas del plan matriz; los capítulos y planos de ese plan no generan proyectos.

Cobertura **parcial**: sólo planeamiento urbanístico del inventario autonómico,
no todas las obras municipales, expedientes pendientes, licencias ni el inventario
territorial/sectorial. La consulta territorial descubierta ofrece instrumentos de
ámbito regional y proyectos supramunicipales; no se incorporan a este alcance.
La sede electrónica no se ha usado como registro de concesiones.

## Semántica y límites

`fecha_aprob` corresponde exclusivamente a `fechaaddef` (aprobación definitiva).
Las fechas DOG, BOP y publicación de normativa BOP permanecen en campos separados;
`fecha`, `fecha_publicacion` genérica y `fecha_acuerdo` quedan nulas. Por ejemplo,
el PXOM tiene aprobación 2003-06-27, DOG 2003-08-25 y BOP 2003-08-29.
Se comprueba coincidencia de fechas entre inventario y ficha. No se deducen fechas
del nombre de archivo o del CMS, ni se equipara aprobación con licencia concedida,
ejecución de obra o vigencia legal actual. Se retienen incidencias jurídicas.
Los documentos no se han contrastado íntegramente con boletines: una etiqueta
documental de normativa del PXOM menciona 29/08/2002 mientras el metadato BOP de la
ficha indica 2003-08-29; ambas afirmaciones de la fuente se preservan sin resolver
la discrepancia ni sustituir una por la otra.

`geometry_status: unavailable`: el índice ofrece WMS y fichas con planos raster,
pero no se ha verificado una geometría vectorial vinculada a los IDs de instrumento.
No se generan coordenadas, centroides ni geometrías a partir de planos.
Todos los registros tienen `publication_ready: false`. El anotador compartido de
entidades carga correctamente y devuelve 7 categorías desconocidas; el adaptador
no altera la política común para forzar una clasificación.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_a_caniza -v`: **4 pruebas pasan**. Cubren
agrupación documental, aislamiento entre instrumentos, fechas separadas,
rechazo de municipio/ID/fechas incoherentes, ausencia documental, cambio de esquema,
recorrido de las cuatro clases, conservación del snapshot ante fallo y carga del
manifest por el registro real. Las fixtures son autocontenidas; no requieren red.

Ejecución live: `load_manifest('a-caniza')`, `load_portal_adapter(manifest)`,
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando sólo
`manifest.portal.config['evidence_dir']` al directorio local de evidencia.
`update_proyectos` refresca el inventario completo, sin cursor de fechas; no puede
omitir una modificación de un expediente antiguo por su fecha de aprobación.
Se escribe el JSONL sólo después de validar todas las fichas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, cuatro respuestas de inventario y siete fichas JSON,
HTML del inventario y capturas de descubrimiento. Muestra de documento enlazado:
https://siotuga.xunta.gal/siotuga/documentos/urbanismo/ACANIZA/documents/0764me002.pdf
respondió HTTP 200, `application/pdf`, firma `%PDF-`; se conservaron sólo los
primeros 1024 bytes. No se afirma haber comprobado los 230 enlaces ni descargado
sus documentos completos.

Licencias, programación y jitter de geocodificación desactivados en manifest.
Sin cambios compartidos, dependencias nuevas, publicación ni persistencia externa.
