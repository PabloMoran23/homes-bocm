# H03: control y reproceso geográfico

Toda ejecución de geocode/enrich y toda escritura por `db.ingest.save_proyectos`
/ `save_licencias` aplica `municipio.geography_control.normalize_record`.
Los CRS y órdenes deben venir del registro (`geometry_crs`,
`geometry_axis_order`, `coordinates_crs`, `coordinates_axis_order`) o de
`geometry.validation` del manifest (`source_crs`, `axis_order`,
`coordinates_crs`, `coordinates_axis_order`). Nunca se infieren por magnitud.
GeoJSON usa xy; GML con EPSG:4326 usa el orden latitud/longitud declarado por
ese CRS. L'Alfàs conserva el posList original y su declaración en la evidencia.

El límite municipal se obtiene del IGN por nombre exacto y se retiene junto a
su URL; también se puede configurar `municipal_boundary` (GeoJSON WGS84 o
objeto con geometry/crs/axis_order/source). Un fallo o una coincidencia ambigua
no ubica el registro. No se elige el municipio más cercano.

Para un ámbito supramunicipal se requieren `municipality_scope` (lista de
nombres, incluyendo el municipio de la ingesta), `multimunicipal_evidence`
(referencia al instrumento que lo acredita) y `municipal_boundaries` para todos
los nombres. Se exige contención en la unión de esos límites, incluso en ese caso.

La cuarentena afecta a los campos geográficos. `geography_original` conserva
su entrada, `geography_validation` registra versión, hashes, CRS, ejes y causas.
La geografía inválida no se sustituye por un centroide municipal. El registro
puede mantenerse sin ubicación. El upsert borra explícitamente coordenadas
antiguas cuando la nueva evidencia falla; una ubicación anterior tampoco se
conserva sin validación vigente. Los CHECK NOT VALID de la migración impiden
nuevas coordenadas/topologías inválidas incluso para escritores SQL directos;
no corrigen ni validan el histórico existente.

## Reproceso local reproducible

```bash
# Por defecto, solo inspección y cola, sin escritura a DB ni JSONL.
python -m municipio.geography_replay --report /tmp/geography-report.json
python -m municipio.geography_replay --slug leganes --slug san-sebastian-de-los-reyes --slug l-alfas-del-pi
# Originales retenidos fuera del checkout (se mantienen intactos sin --apply):
python -m municipio.geography_replay --input-root /ruta/output/municipios --slug leganes --report /tmp/leganes.json
# Control de producción de solo lectura: cola desde la evidencia raw, sin UPDATE/INSERT.
python -m municipio.geography_replay --database --report /tmp/live-geography-report.json
# Tras revisar el informe, regenerar derivados locales desde originales retenidos.
python -m municipio.geography_replay --slug leganes --apply
```

El cambio de regla o configuración reproduce los originales, nunca transforma
por segunda vez la geometría ya normalizada. Una modificación real de la fuente
crea una nueva entrada de evidencia. Repetir el mismo reproceso no añade filas.
Un histórico sin declaración CRS queda en cola hasta recuperar el original con
su declaración: ejecutar el adaptador/backfill correspondiente y el pipeline
normal. No añadir EPSG por intuición al histórico.

El workflow `geography-control.yml` ejecuta pruebas y replay diario; sube la cola
como artefacto y falla cuando no puede completar un control o quedan cuarentenas.
El pipeline diario municipal ya ejecuta enrich, geocode y sync para cada lote.

## Pendiente operativo

Esta PR no modifica producción. Falta recuperar originales de los 327 casos
identificados en el corte, ejecutar su backfill/replay e ingesta, revisar una
muestra visual por adaptador y validar los CHECK contra el histórico saneado.
Con secreto DB configurado, el control diario lee producción en una sesión
readonly y encola originales y causas por ID, incluyendo los nuevos casos.
Sin ese secreto, cubre los JSONL disponibles en checkout; no certifica
producción. La cola no reemplaza la recuperación/backfill inicial de fuentes.

Las fuentes que aún no declaran CRS/coordenadas o no tienen límite municipal
verificable pierden la ubicación hasta completar su configuración con evidencia.
Ese caso queda registrado en la cola; el registro se conserva sin mapa.

En la comprobación local de originales ignorados se procesaron 363 registros
de Leganés y 62 de San Sebastián de los Reyes, reproduciendo respectivamente
241 y 17 pares fuera de rango. Se generó la cola en /tmp, sin modificar los
originales ni publicar geografía por inferencia del CRS. No había copia local de
L’Alfàs del Pi. Estas cifras son evidencia del corte, no constantes de las reglas.
