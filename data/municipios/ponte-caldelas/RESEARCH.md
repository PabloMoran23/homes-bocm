# Ponte Caldelas — INE 36043, Pontevedra

Verificado el 2026-11-09 mediante peticiones HTTP reales. Un solo adaptador,
`municipio.adapters.ponte_caldelas:PonteCaldelasAyuntamientoAdapter`.

## Descubrimiento y procedencia

La web municipal actual es https://pontecaldelas.gal/ y su sede pública es
https://pontecaldelas.sedelectronica.es/info.0. La página
https://pontecaldelas.gal/gl/tramites-administrativos/ ofrece solicitudes de
urbanismo, no un inventario de licencias concedidas. No se transforman en registros.

El inventario oficial utilizado es el SIOTUGA, mantenido por la **Xunta de Galicia**,
no por el ayuntamiento. Desde https://siotuga.xunta.gal/siotuga/urb, la fila INE
36043, Ponte Caldelas, enlaza a:
https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36043.
La fuente se identifica en los registros como `xunta_siotuga`. El valor
`proyectos.source: ayuntamiento` selecciona la ruta de adaptadores municipales del
esquema existente; no atribuye la publicación al ayuntamiento.

El JavaScript público
https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0
expone el funcionamiento de la consulta. Se abre una sesión anónima, se obtiene
el nonce público del formulario y se consultan por POST:

- `assets/inventario/query_document.php`, `id=36043`, clases 14 (general),
  13 (desarrollo), 16 (histórico), 18 (delimitaciones rurales).
- `assets/inventario/getIOTPU.php`, `iddoc` descubierto, `idp=0`, `lang=gl_ES`.

No son operaciones de escritura del portal. La consulta devuelve un array completo
por clase (o null cuando no hay resultados). DataTables pagina ese array en el
navegador; no existe un límite de página aplicado por este adaptador. Se recorren
las cuatro clases y todos sus instrumentos/documentos, sin tope ni corte. Los
sobres JSON de paginación desconocidos se rechazan explícitamente. Los IDs
repetidos se deduplican y los conflictos provocan error antes de sustituir la salida.
El inventario vacío también exige revisión. Update refresca la instantánea completa.

## Resultado real

| ID SIOTUGA | Instrumento | Aprobación definitiva | Documentos enlazados |
| --- | --- | --- | --- |
| 22912 | Normas subsidiarias de planeamento | 1993-02-12 | 66 |
| 22913 | Modificación puntual — NSP | 1995-07-05 | 11 |
| 27838 | Plan especial de dotacións da rúa Valdarrosa | 2013-12-30 | 11 |
| 26535 | Estudio de detalle para reordenación de volumes na parcela Piñeiral da Laranxeira | 2008-05-15 | 0 |

Clases 16 y 18 devuelven null en la ejecución verificada. Cada ID constituye un
instrumento; las memorias, normativa, anexos y planos no se cuentan como proyectos
nuevos. Se retienen los 88 enlaces y sus grupos documentales. La ficha 26535 devuelve
`elementos: null`: se conserva con `documentos_status: unavailable_in_source`.
Se descargó un PDF de cada una de las otras tres fichas, HTTP 200 y cabecera `%PDF`.
No se ha comprobado la disponibilidad de cada uno de los 88 enlaces.

Las fechas proceden de los campos explícitos del inventario y de la ficha:
`fechaaddef` → `fecha_aprob`, `fechabop` → `fecha_publicacion_bop`, `fechadog` →
`fecha_publicacion_dog`, `fechanormativabop` → `fecha_publicacion_normativa_bop`.
`fecha` y `fecha_publicacion` genéricas quedan nulas; no se supone que una de las
publicaciones equivalga al acuerdo. Por ejemplo, el plan especial fue aprobado
el 2013-12-30 y publicado en DOG el 2014-02-18. No se corrigen ni deducen fechas
por el orden de las publicaciones. Los parámetros y endpoints de procedencia se
conservan por registro, además del enlace navegable al inventario municipal.

## Cobertura y límites

Cobertura **parcial del inventario municipal de planeamiento**, sin afirmar que
sean todos los expedientes municipales ni que el inventario recoja inmediatamente
las nuevas tramitaciones. El endpoint separado `assets/iot/queryIotInv.php`,
consultado durante la investigación, ofrece ordenación territorial/sectorial,
incluidos instrumentos supramunicipales; está fuera del alcance del adaptador.
Tampoco se extraen noticias, licitaciones ni obras públicas desde la web municipal.
La modificación nº 2 en tramitación encontrada en la búsqueda no aparece en estas
cuatro clases; no se incorpora desde resúmenes secundarios ni se presenta como
aprobada definitivamente. Licencias deshabilitadas: cero concesiones verificadas.

`geometry_status: unavailable`. SIOTUGA ofrece visor/WMS y planos raster, pero
no se ha verificado geometría vectorial asociada a los cuatro IDs. No se
vectorizan documentos ni se asigna el centro municipal como ubicación del proyecto.
Latitud, longitud y geometría nulas; `publication_ready: false`.
`schedule.enabled: false`, `geocode.jitter_missing: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_ponte_caldelas -v`: **5 pruebas pasan**.
Cubren agrupación documental, fechas, ausencia explícita de documentos, rechazo de
otro municipio/ID/fechas contradictorias, deduplicación, rechazo de paginación no
comprendida, recorrido de las cuatro clases y resolución del manifiesto.

Extracción real mediante `load_manifest('ponte-caldelas')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
**4 registros**, 88 enlaces. Configuración local `evidence_dir='evidence'` captura las
respuestas de la misma ejecución, sin modificar el manifiesto. Evidencias locales:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `live-class-*.json`,
`live-detail-*.json`, HTML/JavaScript de descubrimiento y tres PDFs de muestra.
Las evidencias no forman parte de los cuatro archivos fuente entregados.
