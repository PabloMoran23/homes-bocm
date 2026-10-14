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
conserva sin validación vigente. La migración bloquea escrituras concurrentes,
retiene los campos inválidos del legado en `raw._geography_quarantine`, y limpia
solo su geografía antes de activar CHECKs completamente validados, todo en una
transacción. No transforma ni supone CRS. De ese modo los UPDATE de raw/fase de
H01/H02 siguen funcionando; ninguna nueva geografía inválida entra por SQL.
El snapshot conservado sigue entrando en la cola readonly hasta su recuperación.
La geografía válida y las demás columnas permanecen intactas. Si la migración
falla, se revierte también la cuarentena; hay una prueba que inyecta un fallo
tras limpiar los campos y verifica la recuperación completa. Una recuperación
posterior usa el normalizador y evidencia CRS, sin restaurar campos inválidos.

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

El workflow `geography-control.yml` separa dos certificaciones locales (unittest
y PostgreSQL/PostGIS desechable) del control operativo. Los PRs solo ejecutan
las pruebas, sin secretos de producción, acceso a fuentes ni scan de la DB.
El job readonly y su artefacto de cola se ejecutan exclusivamente por schedule o
workflow_dispatch, y fallan si quedan controles incompletos o cuarentenas.
Un CRS desconocido se rechaza sin pedir límites por red innecesariamente.
El pipeline diario municipal ya ejecuta enrich, geocode y sync para cada lote.

## Pendiente operativo

Esta PR no modifica producción. Falta recuperar originales de los 327 casos
identificados en el corte, ejecutar su backfill/replay e ingesta, revisar una
muestra visual por adaptador y desplegar la cuarentena/constraints en el entorno
autorizado. La migración ya se probó en PostgreSQL 16.15/PostGIS 3.4.2 local,
incluido el replay real de #857 sobre un outlier histórico y el UPDATE raw H01.
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

Pruebas SQL reproducibles en una DB local desechable cuyo nombre empiece por h03_:

```bash
H03_TEST_DB_URL=postgresql://postgres:password@127.0.0.1:5432/h03_geography_tests python -m unittest db.test_geography_postgres -v
# Integración adicional con el checkout de #857, sin editarlo:
H03_TEST_DB_URL=... H03_SEMANTICS_ROOT=/ruta/checkout-857 python -m unittest db.test_geography_postgres -v
```

El validador SQL usa `Box3D`. Solo captura errores de parseo de la entrada;
`UndefinedFunction` y fallos de implementación se propagan y abortan la migración,
comprobado contra PostGIS real y mediante autocomprobación al aplicar la regla.
