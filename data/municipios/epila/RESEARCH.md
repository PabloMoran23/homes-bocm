# Épila — Zaragoza — INE 50099

Investigación y extracción en vivo: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y descubrimiento

- [Área municipal de Urbanismo](https://epila.es/areas/urbanismo-y-trafico/).
  Contiene información administrativa, formularios de solicitud y un enlace de
  exposición pública del PGOU. Los formularios no son licencias concedidas.
- [Enlace antiguo del PGOU](https://epila.sedelectronica.es/transparency/6801b35a-0989-49ac-8397-68fff44b46fd/).
  Devuelve HTTP 200 y «No se han encontrado elementos». No se sintetiza un proyecto
  a partir del texto del enlace.
- [Portal de transparencia actual](https://epila.sedelectronica.es/transparency/).
  Su carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» anuncia 14 elementos.
- [Carpeta de urbanismo](https://epila.sedelectronica.es/transparency/2e6ee3ea-81e0-46c9-84cf-e49a08e3bf20/).
  Anuncia 12 elementos de planeamiento, uno medioambiental y uno de obras públicas.
- [Inventario 7.1 de planeamiento, fuente del adaptador](https://epila.sedelectronica.es/transparency/7e75f398-8dca-4199-8066-3347c59dd4b2/).
  Incluye una referencia externa al archivo regional y 11 documentos municipales.
  La referencia regional identifica expresamente `CMUNIINE=50099`; es un directorio,
  no un instrumento adicional. No se recorre ese archivo en esta implementación.
- [Obras públicas](https://epila.sedelectronica.es/transparency/fa32b93e-a81b-4b6d-9f86-524e3b643458/)
  contiene una orden de inicio de expropiación para conexiones exteriores de la
  plataforma agroalimentaria. Se inspeccionó, pero queda fuera del alcance del
  adaptador de planeamiento. No se presenta como obra ejecutada.

La navegación de carpetas usa Wicket: se obtiene una sesión pública, se lee el
callback del HTML y se sigue `Ajax-Location` hasta la URL estable de carpeta.
No requiere autenticación, credenciales ni automatización de trámites.

## Registros y agrupación

La ejecución mediante el cargador de manifests produjo **4 registros y 11 documentos**:

| Entrada municipal | Documentos | Procedencia |
| --- | ---: | --- |
| BOP Z 188 1995.08.17 Normas subsidiarias de planeamiento de Épila | 1 | [Documento](https://epila.sedelectronica.es/preview-document/f495d756-9701-4e46-a0b0-c91e9ff2b7c5) |
| Publicación normas del SAUR 5 BOP nº 9372 de fecha 8 de noviembre de 2019 | 1 | [Documento](https://epila.sedelectronica.es/preview-document/48823410-0cf5-419c-b5e4-ecdefc7e80e5) |
| INFORMACION PUBLICA APROBACION PLAN PARCIAL AZUCARERA | 8 | [Carpeta](https://epila.sedelectronica.es/transparency/bc374671-d847-4b00-9823-f1fe0bfd9a0e/) |
| INFORMACION PÚBLICA MODIFICACIÓN NNSS SAUR 10 AZUCARERA | 1 | [Carpeta](https://epila.sedelectronica.es/transparency/7cd4a773-058c-4191-9d8a-873387e28139/) |

El Plan Parcial agrupa memoria, planos, estudio económico, catálogos, plan de
etapas, estudio ambiental, normas urbanísticas y documento ambiental estratégico.
La modificación de NNSS conserva su propia carpeta y documento; no se fusiona
con el Plan Parcial por compartir «Azucarera». Se conservan títulos originales,
descripciones, URL estable `preview-document` y página de procedencia en cada
documento. Los IDs derivan de las URL estables, nunca de los callbacks temporales.

Comprobación documental adicional: la [memoria](https://epila.sedelectronica.es/preview-document/199bcae7-d782-4ff1-9d05-966c489285f0)
sirvió un PDF real de 2.474.202 bytes, HTTP 200, `application/pdf`, firma `%PDF-`.
Sus primeras páginas identifican el Plan Parcial de los antiguos terrenos de la
Azucarera del Jalón, Épila, sector 10 y SAUR-10, como «Documento para Aprobación
inicial: 05’2022». Esto identifica el documento, sin acreditar acuerdo aprobatorio.
La vista previa muestra creación en octubre de 2025: esa fecha de carga no se
interpreta como fecha de aprobación ni publicación del instrumento.

## Cobertura y semántica

Inventario documental actualmente publicado, con documentos históricos; no es un
censo completo del planeamiento vigente, proyectos, obras ni licencias. El registro
del SAUR 5 representa la publicación normativa disponible, sin deducir un número
de expediente, aprobación o denominación de plan que el inventario no proporciona.
No se incluyen formularios, licitaciones ni noticias generales.

Solo se estructura `fecha_publicacion=1995-08-17` desde el título BOP explícito.
La fecha de publicación de 2019 se conserva literalmente en el título; no se
normaliza. Ninguna fecha de aprobación, acuerdo o fase se infiere de «APROBACION»
en una carpeta, de un nombre de archivo o de la fecha de creación en la sede.
Sin coordenadas, geometría ni localización inventada. `publication_ready=false`
y `geometry_status=unavailable` en todos los registros. Licencias deshabilitadas;
`schedule.enabled=false` y `geocode.jitter_missing=false`.

Se recorren todas las filas de cada carpeta y sus subcarpetas. El número de
documentos debe coincidir con el recuento anunciado. Controles de paginación,
carpetas desconocidas, ciclos, estructura vacía o recuentos discrepantes provocan
error antes de escribir el resultado. No hay límite que trunque registros.
Las actualizaciones refrescan el inventario completo; no afirman un histórico
incremental de altas y bajas. No se descargan todos los PDF automáticamente.

## Verificación reproducible y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_epila -v`

Seis pruebas correctas: agrupación, fechas, IDs estables, recuentos, paginación,
rechazo de estructuras vacías/desconocidas, procedencia, manifest y licencias
desactivadas. La ejecución real usó `load_manifest('epila')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`;
el resultado pasó también por la anotación de entidades del cargador compartido.

Evidencia local sin incorporar al código: `evidence/proyectos.jsonl`,
`evidence/validation.json`, HTML de descubrimiento y de todas las páginas extraídas
en `evidence/captures/`, `evidence/memoria.pdf` y
`evidence/memoria-first-pages.txt`. La validación registra el recuento vivo,
fuentes y limitaciones. No se ejecutó ningún paso de publicación, despliegue,
base de datos o sincronización.
