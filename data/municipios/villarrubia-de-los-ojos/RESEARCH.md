# Villarrubia de los Ojos — INE 13096, Ciudad Real

Comprobación en vivo: 2026-11-07. Un adaptador municipal, con cobertura parcial
exclusivamente del inventario de planeamiento general de la Junta de Comunidades
de Castilla-La Mancha. No es un inventario de obras ejecutadas ni de licencias.

## Descubrimiento y fuentes oficiales

- Ayuntamiento actual: https://www.villarrubiadelosojos.es/
- Antigua ruta del POM:
  https://www.villarrubiadelosojos.es/index.php/adm-municipal/normativa/plan-ordenacion-municipal
  responde HTTP 200 con la portada actual, sin inventario de planeamiento.
- Archivo municipal antiguo:
  http://mail.villarrubiadelosojos.es/index.php/adm-municipal/normativa/plan-ordenacion-municipal
  sí expone seis volúmenes del POM y anuncios. HTTPS falla por certificado no
  válido para ese hostname; no se ha desactivado la verificación TLS.
  Los enlaces de descarga probados regresan al listado HTML en vez de entregar
  PDF. Los recuentos de categorías superan las diez filas predeterminadas aunque
  no aparecen controles de paginación; `limit=0` permitió ver las 19 del volumen 2.
  No se usa esta fuente incompleta en el adaptador. Capturas locales `pom.html`,
  `volume-*.html` e `inventory.html` documentan el hallazgo.
- Sede: https://villarrubiadelosojos.sedelectronica.es/ muestra solicitudes de
  licencia; no acreditan concesión y no se convierten en registros.
- Inventario oficial regional seleccionado:
  https://urbanismo.castillalamancha.es/planeamiento-municipal-cloned
  explica los tipos de planes y la descarga por municipio. Advierte del carácter
  informativo de las copias frente al expediente administrativo diligenciado.
- Visores oficiales: https://urbanismo.castillalamancha.es/visores-tematicos
- Servicio público del inventario:
  https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0
  Campos comprobados en `evidence/layer.json`.

## Extracción y semántica

Se consulta `/query` con `where=COD_INE = '13096'`, primero
`returnIdsOnly=true`. Se recuperan todos los IDs en lotes de 100, exigiendo igualdad
exacta entre identificadores solicitados y recibidos y rechazando errores o
`exceededTransferLimit`. No hay corte por número de páginas ni por volumen total.
Se comprueban también COD_PROV=13 y el nombre municipal exacto. La desaparición
del inventario, un lote incompleto o un documento inválido provocan error antes de
sustituir la instantánea de salida. `update_proyectos` refresca la instantánea
completa, no usa una fecha artificial como cursor incremental.

Resultado real: **1 instrumento, Plan de Ordenación Municipal (POM)**,
OBJECTID 1104 en la consulta verificada. FECHA_APRO=1466553600000 se interpreta en
UTC como **2016-06-22**, fecha de aprobación según el inventario. No se infiere
que sea fecha de publicación, acuerdo ni una fase concreta de aprobación.
FECHA_ACTU=1543449600000 corresponde a **2018-11-29**, actualización del inventario,
no del estado jurídico del plan a la fecha actual. No se afirma que el catálogo
contenga todas las modificaciones posteriores. Fecha genérica, publicación,
acuerdo y fase quedan nulas.

El registro conserva los atributos fuente, la URL del servicio, la procedencia
`administracion_autonomica` y el enlace del paquete documental:
https://ficheroscomunes.castillalamancha.es/planeamiento/CIUDAD_REAL/13096_VILLARRUBIA_DE_LOS_OJOS.zip

El archivo oficial respondió HTTP 206 a `Range: bytes=0-4095`, tamaño total
525580270 bytes, con firma ZIP. El adaptador comprueba en cada extracción los
primeros cuatro bytes `PK\x03\x04`; no descarga ni afirma haber leído todo el
paquete de unos 525 MB. Los documentos agrupados en ese ZIP se conservan como
**un instrumento**, con su enlace, sin generar un proyecto por PDF ni reconstruir
URLs internas. El ID se deriva de la URL documental y no del OBJECTID mutable.
Duplicados del mismo paquete se agrupan; atributos incompatibles provocan error.

## Geometría y límites

El servicio tiene referencia espacial EPSG:25830 y polígonos municipales.
No se ha verificado una geometría de ámbito del instrumento ni una capa de obra
vinculada a su expediente. Se pide `returnGeometry=false`; no se usa el polígono
municipal como geometría del proyecto ni su centroide como ubicación.
`geometry`, `lat` y `lon` quedan nulos, `publication_ready=false`.

La cobertura comprende solo el planeamiento general incluido en este inventario
regional. No incluye todas las modificaciones, planes de desarrollo, proyectos
públicos físicos, contratación ni licencias. No se extraen noticias como proyectos.
El selector `proyectos.source: ayuntamiento` es el modo de carga del adaptador en
el esquema existente; la procedencia real regional queda explícita en los registros
y el manifest. `licencias.enabled=false`, `schedule.enabled=false` y
`geocode.jitter_missing=false`.

## Verificación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villarrubia_de_los_ojos -v
```

8 pruebas pasan: fechas y procedencia, ausencia de geometría inventada,
agrupación/estabilidad, municipio incorrecto/documentos inválidos, vacío/error/
truncamiento, fechas ausentes, manifest/licencias desactivadas, recuperación en
varios lotes y conservación de la salida anterior ante un lote incompleto.

La ejecución real cargó el manifest mediante `load_manifest`, resolvió el adaptador
con `load_portal_adapter` y llamó `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Para conservar capturas se añadió `evidence_dir: evidence` a la configuración solo
en memoria. Resultado: 1 registro, 1 elemento fuente, sin errores de extracción.
`evidence/validation.json` contiene el recuento real, fuentes y limitaciones;
`live-ids.json`, `live-features-0.json` y `live-archive-0-signature.bin` son las
capturas de esta ejecución. Evidencia local, fuera de los cuatro archivos fuente.
Sin publicación, conexión a bases de datos ni cambios compartidos.
