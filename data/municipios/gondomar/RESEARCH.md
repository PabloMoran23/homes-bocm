# Gondomar — Pontevedra — INE 36021

Verificación y extracción real: 2026-11-07. Adaptador exclusivo de Gondomar,
Galicia (España); no confundir con el municipio portugués homónimo.

## Descubrimiento y fuente efectiva

Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de
adaptadores y los ejemplos Hernani y Manlleu antes de implementar. El portal
municipal https://concellodegondomar.gal/ y su sección
https://concellodegondomar.gal/urbanismo-vivenda-patrimonio-e-contratacion-publica/
responden HTTP 403 al cliente requests. Las fichas indexadas de Urbanismo describen
competencias; no son inventarios de expedientes. La sede
https://concellodegondomar.sedelectronica.gal/info.0 muestra solicitudes y trámites,
que no se han tratado como licencias concedidas. Tampoco se extraen noticias ni
anuncios de contratación.

Se descubrió el inventario municipal oficial de la Xunta mediante las páginas de
urbanismo y ayuda de SIOTUGA:

- https://siotuga.xunta.gal/siotuga/urb?lang=es_ES
- https://siotuga.xunta.gal/siotuga/axuda?lang=es_ES
- https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=36021&lang=es_ES

La URL correcta de consulta usa `inv=1&idconcello=36021`; un parámetro `ine` solo
no realiza la selección. El adaptador verifica la opción INE/nombre y obtiene el
token público de formulario de la página. No usa credenciales ni sesión autenticada.
La fuente efectiva de cada registro es `xunta_siotuga`, aunque el selector de
pipeline `proyectos.source: ayuntamiento` mantiene el contrato del adaptador portal.

El JavaScript oficial
https://siotuga.xunta.gal/siotuga/assets/inventario/controls.min.js?2.5.0
muestra las consultas POST de la interfaz pública:

- `assets/inventario/query_document.php`: `id=36021`, `idclase=13` (desarrollo)
  y `idclase=18` (delimitaciones de núcleo rural), más token público.
- `assets/inventario/getIOTPU.php`: `iddoc` descubierto, `idp=0`, `lang=es_ES`
  y token público.

Se recupera el array completo de cada categoría. La paginación DataTables ocurre
en el navegador sobre ese array; no hay límite de página ni corte temporal en el
adaptador. Un objeto paginado o un cambio de esquema provoca error. IDs duplicados
idénticos se deduplican; conflictos y cruces de municipio se rechazan. El refresco
incremental repite la instantánea completa sin usar una fecha de corte.

## Cobertura comprobada

Ocho instrumentos reales, con 113 enlaces agrupados por ID de instrumento:

| ID SIOTUGA | Instrumento | Documentos |
| --- | --- | ---: |
| 28486 | PEID centro de día Sor Rosario Fernández Pereira, Borreiros | 20 |
| 27638 | Modificado para o desarrollo do polígono P-17 | 11 |
| 26768 | Estudio de detalle Rúa Elduayen 16 | 0 |
| 28387 | DSNR A Carballa, Morgadáns | 19 |
| 28386 | DSNR A Mourisca, Chaín | 18 |
| 28329 | DSNR San Roque, Morgadáns | 16 |
| 28134 | DSNR Penalba, Mañufe | 12 |
| 28133 | DSNR Prado, Morgadáns | 17 |

Cada componente conserva título, grupo, ID y URL construida con `filesroot`,
`folder` y `pathesperado` según el JavaScript oficial. No se convierte cada PDF o
plano en otro proyecto. La ficha 26768 devuelve `elementos: null`; se retiene el
instrumento y se declara `documentos_status: not_exposed_by_source`.

Las fechas `fechaaddef`, `fechadog`, `fechabop` y `fechanormativabop` se conservan
como aprobación definitiva y tres campos distintos de publicación. No se elige una
publicación arbitraria como fecha genérica: `fecha` queda nula. La ficha 27638 no
ofrece fechas; tampoco se infiere fase de aprobación. La presencia en una categoría
no certifica vigencia jurídica. Se conservan las incidencias de inventario y detalle.

Cobertura parcial: no incluye instrumentos territoriales supramunicipales,
planeamiento histórico/anulado (clase 16), otras categorías, obras municipales ni
licencias. En la exploración la clase 14 devolvió null y la 16 varios instrumentos
históricos, incluido el PXOM anulado. Esas respuestas se guardan solo como evidencia;
no se presentan como proyectos vigentes ni como cobertura del adaptador.

## Geometría y límites

`geometry_status: unavailable`. SIOTUGA dispone de visor y cartografía, y entre los
documentos hay planos PDF/JPG. No se ha verificado una geometría vectorial por ID de
estos instrumentos; no se digitalizan planos ni se usan centroides del municipio.
Latitud, longitud y geometría quedan nulas; `publication_ready: false`.
`licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` son false.

## Validación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_gondomar -v`, cinco pasan. Comprueban
agrupación/documentos, semántica y ausencia de fechas, array completo de 150 fichas,
duplicados, rechazo de respuestas paginadas/cambio de municipio/fechas inválidas,
documentación explícitamente ausente y desactivación de licencias sin red.

Extracción real invocando `GondomarAyuntamientoAdapter.backfill_proyectos` con el
manifest y `config.evidence_dir=evidence`: ocho registros. Evidencia local:
`evidence/proyectos.jsonl`, `evidence/validation.json`, HTML de inventario,
respuestas JSON de categorías y ocho detalles. Se capturan además el 403 municipal,
el JavaScript de la consulta y el PDF real `28486no001.pdf` (HTTP 200,
application/pdf, 299385 bytes). Los 113 enlaces se han extraído de fichas vivas;
no se afirma haber descargado todos los documentos. El informe incluye URLs,
recuento, fecha de extracción y limitaciones. La evidencia no forma parte del commit.
