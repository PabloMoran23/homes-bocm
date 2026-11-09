# Argamasilla de Calatrava — INE 13020, Ciudad Real

Verificación en vivo: 2026-11-09. Cobertura **parcial** del inventario oficial
autonómico SIU. Resultado: **1 instrumento real**, Normas Subsidiarias tipo b,
con un enlace al paquete cartográfico municipal. No representa una obra nueva,
una licencia concedida ni una aprobación reciente.

## Descubrimiento y fuentes

El sitio oficial https://argamasilladecalatrava.es/ enlaza desde Ayuntamiento
las Normas Subsidiarias y la normativa aprobada, y desde Desarrollo el POM:

- https://argamasilladecalatrava.es/ayuntamiento/normas-subsidiarias/
- https://argamasilladecalatrava.es/ayuntamiento/normativa-aprobada-en-vigor/
- https://argamasilladecalatrava.es/desarrollo/pom-plan-de-ordenacion-municipal/

El buscador permite descubrir estos inventarios, pero las solicitudes directas
desde este entorno devuelven HTTP 200 con una pantalla de verificación/reCAPTCHA,
incluidos el dominio con www, HTTP y la API WordPress. `evidence/pom.html` y
`evidence/probe-*.txt` conservan esas respuestas; **no son inventarios extraídos**.
No se usa el contenido del buscador como sustituto de una extracción en vivo.
El inventario NNSS municipal muestra paginación y el de normativa contiene
instrumentos adicionales: no se declara haberlos recorrido ni cubierto.

La alternativa oficial accesible es la Junta de Comunidades de Castilla-La Mancha:

1. https://urbanismo.castillalamancha.es/planeamiento/sistema-de-informacion-urbana
   enlaza el visor SIU; captura `evidence/regional.html`.
2. https://castillalamancha.maps.arcgis.com/apps/webappviewer/index.html?id=8089ffeebd184d19b8b329daee501626
   Su configuración pública (`evidence/siu-app.json`) identifica la capa
   `Vector/SIU_municipios/MapServer/0` y sus campos de inventario y descarga.
3. https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/SIU_municipios/MapServer/0
   La consulta por `COD_INE = '13020'` devuelve OBJECTID 107, provincia CIUDAD REAL,
   municipio Argamasilla de Calatrava, PLAN_ NNSS y NOM_PLAN Normas Subsidiarias_b.
   Se verifica la identidad completa del municipio y la provincia antes de emitir.
4. El campo DESCARGA enlaza
   https://ficheroscomunes.castillalamancha.es/planeamiento/SIU/13020_ARGAMASILLA_DE_CALATRAVA.zip
   Descarga real HTTP 200, 748872 bytes. `evidence/siu-package.zip` y
   `evidence/package-contents.json` conservan el paquete y su listado: SHP, DBF,
   PRJ, SHX, metadatos y estilos. Es cartografía informativa refundida, **no** el
   expediente jurídico original ni un conjunto de proyectos independientes.

La página oficial de instrumentos advierte que la documentación disponible puede
no incluir modificaciones remitidas o refundidas y tiene carácter informativo:
https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal/instrumento-planeamiento-municipal
(`evidence/regional-inventory.html`).

## Semántica, identidad y límites

Se agrupa el paquete entero bajo las NNSS; las zonas de clasificación/calificación
del suelo no generan registros. El ID depende de la URL oficial del paquete y no
del OBJECTID, que se conserva junto a los demás atributos originales para auditoría.
El registro declara `source: jccm-siu`, distinguiendo la administración autonómica
del ayuntamiento. No se fija ninguna noticia o anuncio como semilla de extracción.

No hay fecha de publicación, acuerdo o aprobación en esta fila de inventario:
los tres campos quedan nulos. ENTREGA es un atributo del SIU, no una fecha.
Las fechas de creación/actualización de paquetes WordPress tampoco acreditarían
aprobación del planeamiento. No se atribuye al POM una aprobación ni vigencia.
Como contraste documental, el DOCM de 2024 informa que el POM no estaba en vigor:
https://docm.jccm.es/docm/verArchivoHtml.do?ruta=2024%2F10%2F21%2Fhtml%2F2024_8196.html&tipo=rutaDocm
(`evidence/alternative-2.html`). Ese dato histórico no se convierte en un estado
jurídico actual ni en una fecha del registro SIU.

No se cubren todas las modificaciones, instrumentos de desarrollo, actuaciones
municipales ni el historial de obras. No se extraen formularios, contratación,
noticias ajenas al objeto o supuestas concesiones. Licencias deshabilitadas.

`geometry_status: unavailable`: el visor ofrece límites y zonificación, pero no se
ha verificado una geometría asociada al instrumento jurídico. No se usa el límite
municipal como geometría de un proyecto ni se inventan puntos, centroides o CRS.
`publication_ready: false`; programación y jitter deshabilitados en el manifest.

## Paginación y validación reproducible

El adaptador consulta primero **todos los IDs** con `returnIdsOnly`, sin límite
de transferencia de entidades en ArcGIS. Después obtiene lotes de 100 IDs y
comprueba igualdad exacta entre los solicitados y recibidos. Errores API,
`exceededTransferLimit`, lotes incompletos, inventario vacío, cambio de instrumento,
municipio incorrecto y documentos inesperados provocan fallo sin reemplazar la
salida anterior. No hay truncamiento silencioso. La actualización repite la
instantánea completa, sin afirmar cobertura histórica ni modificar estado.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`python -m unittest municipio.test_argamasilla_de_calatrava -v`

Cuatro pruebas pasan: agrupación y estabilidad de ID; identidad, deriva y
truncamiento; recorrido de más de un lote y preservación de salida ante fallo;
manifest, actualización y licencias deshabilitadas. Fixtures sintéticos mínimos
basados en los campos observados, sin red en los tests.

Extracción real realizada cargando el manifest e invocando
`ArgamasillaDeCalatravaAyuntamientoAdapter.backfill_proyectos` con
`config.capture_dir = 'evidence'`, salida `evidence/proyectos.jsonl`.
`evidence/validation.json` registra `live_records: 1`, fuentes y limitaciones.
Las capturas `evidence/siu-*.json` incluyen URL solicitada y respuesta de cada
consulta del adaptador, además de las capturas de investigación. Todo `evidence/`
es local, no se incorpora a los cuatro archivos fuente.
