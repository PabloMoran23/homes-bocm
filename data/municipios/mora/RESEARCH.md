# Mora — INE 45106, Toledo

Verificación: 2026-11-07. Un adaptador real, de planeamiento general. Ejecución
programada, licencias y geocodificación por desplazamiento deshabilitadas.

## Descubrimiento y procedencia

Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el cargador de
adaptadores y los ejemplos de Hernani, Manlleu y Chipiona antes de implementar.
La identidad es Mora, provincia de Toledo, Castilla-La Mancha, código INE 45106
(no Mora de Rubielos ni Móra d'Ebre).

1. Área municipal: https://www.mora.es/areas/obras
2. Inventario municipal de planeamiento:
   https://www.mora.es/areas/OBRAS/Normativa/planeamiento
   Indica que la digitalización municipal está en curso y remite a la Consejería
   y al visor de Planeamiento Municipal de Castilla-La Mancha.
3. Visor enlazado literalmente por el ayuntamiento:
   https://mapasjccmold.maps.arcgis.com/apps/webappviewer/index.html?id=e97e8c22f2044b1187051687f8f64d88
4. Configuración pública del visor:
   https://mapasjccmold.maps.arcgis.com/sharing/rest/content/items/e97e8c22f2044b1187051687f8f64d88/data?f=json
   Su buscador identifica la capa regional `Planeamiento municipal`:
   https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0

La capa responde HTTP 200 y expone `COD_INE`, `COD_PROV`, `MUNICIPIO`, `PLAN_`,
`NOM_PLAN`, `FECHA_APRO`, `FECHA_ACTU`, `ZIP`, `DESCARGA` y metadatos de tipos.
La consulta del adaptador filtra exactamente `COD_INE = '45106' AND COD_PROV = '45'`
y valida también el nombre del municipio de cada resultado. No se recorre ni
se extraen municipios vecinos. Un primer acceso municipal sin User-Agent de
navegador devolvió 403; con User-Agent de navegador respondió 200. El adaptador
consulta directamente la API regional pública descubierta, con ese User-Agent.

## Resultado real y semántica

La ejecución mediante `load_portal_adapter(load_manifest('mora'))` devuelve **1
registro real**: `Normas Subsidiarias tipo b de Mora`, código `NNSS-B`, OBJECTID
1753. La fecha de aprobación de la ficha regional (`FECHA_APRO`, milisegundos
UTC, tipo fecha según metadatos) es **1989-07-27**. La fecha de actualización de
la ficha (`FECHA_ACTU`) es **2019-05-17**. No equivalen a publicación ni a un
acuerdo fechado: `fecha_publicacion`, `fecha_acuerdo` y la fecha genérica quedan
nulas. No se afirma una fase de aprobación definitiva no expresada por la ficha.
Se conservan los atributos originales y la procedencia de cada fecha explícita.

El enlace documental de la ficha es:
https://ficheroscomunes.castillalamancha.es/planeamiento/TOLEDO/45106_MORA.zip

Descarga verificada HTTP 200, 135086155 bytes, ZIP válido, 40 archivos (39 PDF y
un Thumbs.db). Incluye memoria, normas urbanísticas, planos y documentación de
modificaciones; algunos planos se denominan CANCELADO. Se retiene el paquete
completo como un enlace documental del instrumento general, sin convertir cada
plano en proyecto ni afirmar que todo el archivo esté vigente. El inventario de
miembros y la huella SHA-256 se guardan en las evidencias locales. Las
modificaciones internas **no se extraen como expedientes independientes**:
esta fuente no aporta fichas individualizadas de ellas. Los nombres de archivos
no se interpretan como acuerdos ni fechas de aprobación. El enlace agrupa la
documentación suministrada por el organismo, no pretende ser un PDF individual.

## Cobertura y límites

Es una instantánea del inventario regional de planeamiento general enlazado por
el ayuntamiento, no una relación exhaustiva del urbanismo municipal ni del estado
jurídico vigente de cada documento histórico. No cubre obras físicas, todas las
modificaciones, expedientes en tramitación, noticias ni contratación. Los modelos
de solicitud de obra mayor/menor y otras licencias de la navegación municipal no
son licencias concedidas y no se extraen. No se verificó un registro público de
concesiones; los métodos de licencias producen cero filas y estado deshabilitado.

La capa tiene polígonos y CRS ETRS89 / UTM 30N (EPSG:25830), pero representan
cobertura municipal del inventario, no un emplazamiento de obra ni el perímetro
verificado de una actuación concreta. Se pide `returnGeometry=false`, y se dejan
latitud, longitud y geometría nulas. `publication_ready=false`. No se usa el
centroide municipal ni se generan coordenadas artificiales.

## Integridad y validación

Se consulta `returnIdsOnly=true` (sin límite de primera página de entidades), se
recuperan todos los IDs en lotes de 100 y se comprueba igualdad exacta de IDs y
recuento. Se rechazan errores ArcGIS, lotes truncados, duplicados, fichas vacías,
identidades incorrectas y enlaces documentales ajenos al repositorio oficial de
Mora. Los IDs de salida dependen del código del plan, no del OBJECTID mutable.
La actualización refresca la misma instantánea completa; no borra el resultado
anterior si la consulta o el parser fallan. No hay truncamiento silencioso.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_mora -v` — **5 pruebas, todas pasan**.
Cubren datos reales de la ficha, fechas nulas y semántica temporal, estabilidad
del ID, rechazo de resultados inválidos/ambiguos, 101 entidades en dos lotes,
integridad de IDs, conservación del archivo ante error, manifest y licencias.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live-ids.json`,
`evidence/live-features-0.json`, `evidence/layer.json`, configuración del visor,
captura HTML municipal, ZIP descargado y `evidence/archive-inventory.json`.
La extracción real pasó por el cargador y la anotación compartida de entidades:
esta clasifica la ficha como `unknown` (no actividad acreditada). No se fuerza
una reclasificación ni se afirma publicación lista. `ready` significa scraper
implementado y verificado, sujeto a revisión independiente (`accepted=false`).
