# A Pobra do Caramiñal — INE 15067, A Coruña

Verificación: 2026-11-08. Adaptador único, sin cambios compartidos ni dependencias nuevas.

## Fuentes descubiertas

- [Concejalía municipal de Urbanismo](https://apobra.gal/es/concejalia-de-urbanismo/): describe competencias y enlaza transparencia en https://apobra.sedelectronica.es/. No constituye un inventario de proyectos ni de licencias concedidas. La petición directa con requests devolvió 403. El contenido consultable mediante búsqueda tampoco proporciona un listado utilizable. No se extraen noticias, formularios ni anuncios de contratación.
- [Estado oficial del planeamiento SIOTUGA](https://siotuga.xunta.gal/siotuga/urb?lang=es_ES): fila 15067, «Pobra do Caramiñal, A», PXOM y enlace al inventario específico. Captura `evidence/siotuga.html`.
- [Inventario municipal oficial de la Xunta](https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15067&lang=es_ES): fuente usada. La [ayuda oficial](https://siotuga.xunta.gal/siotuga/axuda?lang=es_ES) explica su carácter de plataforma autonómica de documentación de instrumentos aprobados y el significado de la tabla de estado.

La página carga mediante `assets/inventario/controls.min.js?2.5.0`. Su código público, conservado en evidence, muestra las peticiones POST a `assets/inventario/query_document.php` con `id=15067`, `idclase` y nonce anónimo emitido por la propia página. El detalle usa POST a `assets/inventario/getIOTPU.php`, `iddoc`, `idp=0`, `lang=es_ES`. No hay autenticación de usuario. El adaptador comprueba tanto el municipio como el identificador y título en el detalle.

## Cobertura y agrupación

Se extraen completas las clases 14 (planeamiento general) y 13 (desarrollo):

| ID SIOTUGA | Instrumento | Enlaces |
| --- | --- | ---: |
| 26070 | Plan xeral de ordenación municipal | 232 |
| 27651 | Modificación PXOM polígonos 9 y 10, centro de salud | 16 |
| 27197 | Modificación normativa PXOM, polígono de A Tomada | 1 |
| 27611 | Plan parcial SURD I.1, ampliación polígono industrial de A Tomada | 31 |
| 27131 | Estudio de detalle, reajuste de alineaciones rúa Díaz de Rábago | 0 |

Cada ID es un registro estable. Memorias, normativa y planos permanecen agrupados en `documentos`, con sus títulos, secciones y URLs completas. El último instrumento está identificado en inventario y detalle, pero `elementos` es null: se conserva como instrumento real con `documentos_status` explícito, sin inventar adjuntos.

El JavaScript obtiene arrays completos y aplica DataTables en cliente: no hay paginación del servidor en estas consultas. Se recorre cada elemento sin límite de filas. Una futura respuesta paginada en un objeto falla explícitamente; no se acepta una primera página en silencio. Las respuestas vacías de ambas clases fallan; errores HTTP/JSON y detalles inconsistentes impiden escribir una instantánea parcial. Update refresca la instantánea completa, sin inventar un cursor incremental.

Durante investigación también se consultaron clases 16 (13 instrumentos históricos) y 18 (null), conservadas como capturas. Están fuera del ámbito del adaptador. Los instrumentos de ordenación territorial IOT, obras públicas y otros expedientes municipales también quedan fuera. No se afirma cobertura exhaustiva del urbanismo municipal ni vigencia jurídica actual de cada documento. SIOTUGA puede incorporar cambios con retraso.

## Fechas y procedencia

`fechaaddef`, `fechadog`, `fechabop` y `fechanormativabop` se preservan en `fechas_fuente`. Las tres fechas de publicación tienen campos explícitos DOG/BOP; no se confunden con publicación en la web. `fecha` y `fecha_publicacion` genéricas son null. La fecha de aprobación se normaliza solo para instrumentos sin incidencias jurídicas.

El PXOM 26070 tiene una primera aprobación definitiva parcial condicionada el 01/03/2007 (DOG 16/03/2007), una segunda el 25/10/2007 (DOG 14/11/2007, BOP y normativa 22/11/2007), y aprobación definitiva final el 03/07/2008 (DOG 01/09/2008), según la narración jurídica del inventario. Se conserva íntegra esa narración y no se convierte su primera fecha en aprobación final: `fecha_aprob` queda null. No se deduce ninguna fecha de nombres de ficheros.

La procedencia de los registros es `source=siotuga_xunta`, no una atribución de publicación al Concello. `proyectos.source=ayuntamiento` en el manifest usa la ruta de adaptador municipal disponible en el esquema compartido; el portal y las notas explicitan que publica la Xunta. Las URLs de inventario y detalle, identificador y parámetros del detalle permiten rastrear cada ficha.

No se calculan coordenadas, geometrías ni fechas no verificadas. `publication_ready=false`. Licencias, planificación automática y jitter están deshabilitados.

## Validación y reproducción

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_a_pobra_do_caraminal -v
```

Ocho pruebas pasan: agrupación, semántica de fechas, aprobación condicionada, adjuntos ausentes, rechazo de envelopes de paginación/error, más de 100 elementos sin truncar, duplicados e inconsistencias, identidad/procedencia, carga de manifest, licencias sin red y reemplazo de instantánea.

La extracción real se ejecutó mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. Resultado: 5 registros, 280 enlaces. `evidence/validation.json` contiene recuento, URLs, limitaciones y comprobaciones. La política compartida de entidades marca 5 categorías desconocidas; no se presenta esa anotación como una clasificación urbanística validada.

Se guardaron inventario HTML, respuestas de ambas clases y los cinco detalles. Se descargó un PDF de cada instrumento con adjuntos (cuatro HTTP 200 y firma PDF válida): `26070me001.pdf`, `27651me001.pdf`, `27197no001.pdf`, `27611no001.pdf`. No se descargaron ni interpretaron todos los 280 documentos. Las evidencias son locales y no forman parte de los cuatro archivos fuente.
