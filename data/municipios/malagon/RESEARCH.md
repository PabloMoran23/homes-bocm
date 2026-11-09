# Malagón — INE 13052, Ciudad Real (13)

Investigación y extracción real: 8 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y autoridad

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py` y los
manifests/adaptadores de Manlleu, Chipiona y Hernani. No se modifican fuentes compartidas.

- Web municipal: https://malagon.es/ . Enlaza la sede
  https://sedescr.dipucr.es/malagon/ y el portal
  https://aytomalagon-transparencia.dipucr.es/portal/147 . El portal devuelve una
  aplicación JavaScript; no se utiliza como inventario de licencias. La búsqueda
  municipal https://malagon.es/?s=urbanismo contiene noticias, páginas de trámites
  y una exposición de arbolado; no se convierte ese listado en proyectos ni concesiones.
- Información oficial autonómica:
  https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal . Enlaza
  el visor https://mapasjccmold.maps.arcgis.com/apps/webappviewer/index.html?id=e97e8c22f2044b1187051687f8f64d88 .
- Configuración pública del visor:
  https://www.arcgis.com/sharing/rest/content/items/e97e8c22f2044b1187051687f8f64d88/data?f=json .
  Remite al mapa `931bbc73b34c4e5586e72bc2a5d3eed8`, cuya configuración pública
  identifica la capa de Planeamiento Municipal y etiqueta `FECHA_APRO` como
  «Fecha de aprobación».
- Inventario utilizado:
  https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0 .
  Consulta pública HTTP filtrada por `COD_INE = '13052'`, sin geometría. El objeto
  1060 identifica `MUNICIPIO=Malagón`, `COD_PROV=13`, `PLAN_=NNSS-B`,
  `NOM_PLAN=Normas Subsidiarias tipo b`, `FECHA_APRO=608428800000` (1989-04-13).
- Documentación enlazada por ese registro:
  https://ficheroscomunes.castillalamancha.es/planeamiento/CIUDAD_REAL/13052_MALAGON.zip .
  El archivo mide 160515106 bytes y publica 119 entradas ZIP, incluidas carpetas y
  metadatos de sistema. Se lee mediante HTTP Range su directorio central completo
  (131072 bytes finales). Se comprueban EOCD, offsets, longitud, número de entradas
  y ausencia de rutas inesperadas. No se extraen archivos al sistema de ficheros.

## Registros y agrupación

La ejecución viva devolvió **7 instrumentos y 60 documentos**:

| Instrumento según la carpeta oficial | Documentos |
| --- | ---: |
| NNSS Normas Subsidiarias 1989 | 16 |
| MP-1 VARIOS | 5 |
| MP-2 UE-13, PERI Y OTROS | 13 |
| MP-3 ALINEACION C_DR JULIAN RUIZ MOYANO | 2 |
| MP-4 CREACION UA NORTE 1 | 8 |
| MP-5 CREACION SECTOR NORTE 1 | 6 |
| MP-6 MOD Y AMPLIAC POL IND PPI2 | 10 |

Cada registro agrupa normativa, planos y acuerdos de su instrumento conforme a
la jerarquía publicada; no crea un proyecto por PDF o imagen. Se excluyen
`.DS_Store`, archivos `._*`, `Thumbs.db` y entradas de directorio. Se conservan en
`documentos` el nombre, URL real del ZIP y `archivo` (ruta interna); no se inventan
URLs de descarga individual. Los identificadores derivan de la carpeta oficial.
El registro contiene también los atributos originales y la procedencia autonómica.

Primero se solicita el inventario completo de IDs y después todos sus registros,
en lotes de 50, comprobando la igualdad de IDs devueltos. Un error del servicio,
`exceededTransferLimit`, IDs omitidos, directorio central incompleto o estructura
no reconocida impide escribir un nuevo snapshot. No hay corte silencioso de páginas.
La actualización vuelve a consultar el inventario y no usa una lista de proyectos
precargada. El contrato `portal.adapter` permite cargar el módulo sin tocar el registro
compartido; `proyectos.source=ayuntamiento` selecciona ese canal de ejecución, mientras
los registros identifican expresamente al organismo autonómico como fuente.

## Semántica y límites

Solo las NNSS reciben `fecha_aprob=1989-04-13`, procedente del campo explícito del
inventario. `FECHA_ACTU` es un metadato del inventario y no se transforma en fecha
de publicación o aprobación. Las modificaciones conservan el prefijo de su carpeta
como `fecha_carpeta_sin_semantica`; no se infieren acuerdos ni aprobaciones a partir
del nombre del archivo. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fase`
quedan sin determinar. No se afirma vigencia actual individual.

La página oficial de instrumentos advierte que el depósito es informativo y puede
omitir documentación aprobada por ayuntamientos y no remitida o no refundida:
https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal/instrumento-planeamiento-municipal .
Por tanto esta es cobertura parcial del depósito, no un historial municipal completo,
ni un inventario de obras actuales. No se incorporan noticias o anuncios de contratación.
La muestra PDF se comprueba como documento real, pero el adaptador interpreta el
inventario y las rutas, no el contenido de todos los documentos técnicos.

No se ha acreditado un registro público de licencias concedidas: licencias desactivadas.
Sin coordenadas ni geometrías inventadas; `lat`, `lon`, `geometry` nulos,
`publication_ready=false`, `geometry_status=unavailable`. La geometría municipal de
la capa no se utiliza como geometría de cada instrumento. Programación desactivada y
`geocode.jitter_missing=false`.

## Validación reproducible y evidencia local

Pruebas: `python -m unittest municipio.test_malagon -v` con el runtime indicado:
6 pruebas correctas. Cubren separación documental, semántica de fechas, identidad
municipal/provincial, host documental, cambios de estructura, directorio ZIP incompleto,
exclusión de metadatos, licencias desactivadas y conservación del snapshot previo
cuando el inventario falla o indica truncamiento.

Extracción real mediante `MalagonAyuntamientoAdapter(...).backfill_proyectos` con
`config.capture_dir=evidence`; salida `evidence/proyectos.jsonl`. Resumen y URLs
exactas en `evidence/validation.json` (`live_records=7`). Capturas:
`inventory-ids.json`, `inventory-0.json`, `archive-tail.bin`,
`archive-directory.json`, páginas de descubrimiento y configuraciones del visor/mapa.

Muestra adicional `sample-mp4-agreement.pdf`: miembro
`2001-12-21 MP-4 DOCM APROB DEF.pdf`, recuperado por rango desde el mismo ZIP,
74941 bytes descomprimidos, firma `%PDF-` y CRC comprobados. El SHA-256 está
registrado en validation.json. Esta comprobación no atribuye automáticamente una
fecha de acuerdo al instrumento. La evidencia es local y no forma parte de las
cuatro fuentes entregadas. No se ejecutan bases de datos, publicación o despliegue.
