# Calamocha — INE 44050, Teruel, Aragón

Verificado el 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.calamocha:CalamochaAyuntamientoAdapter`.
Se ha revisado el contrato `municipio/adapters/portal.py`, el cargador de
manifiestos y los ejemplos de Hernani, Manlleu y Chipiona antes de implementar.

## Descubrimiento y fuentes oficiales

La portada oficial https://calamocha.es/ enlaza desde su navegación municipal:

- https://calamocha.es/p-g-o-u-documentos/ — inventario documental del Plan
  General de Ordenación Urbana: normativa, memoria/catálogo/estudio económico,
  planos generales y de sus núcleos. 21 enlaces PDF, un instrumento.
- https://calamocha.es/p-g-o-u-modificaciones/ — 24 enlaces PDF correspondientes
  a las modificaciones puntuales 1, 2, 3, 5, 6, 8 y 9. Se agrupan por número:
  doce documentos para la 9, siete para la 8 y uno para cada una de las otras.

Ambos inventarios son páginas completas de listas de documentos, sin
paginación en la captura. Los títulos de cada enlace y sus URL oficiales se
conservan en `documentos`, con `source_url` de la página que los publica.
«Vigente», «modificado» y «bis» son rótulos de documentos de un mismo
instrumento, no proyectos distintos ni fases jurídicas del expediente.
Los planos de barrios pertenecen al PGOU municipal, no a otros municipios.

Las rutas canónicas respondieron inicialmente con HTTP 403 en algunas
peticiones. Las mismas páginas públicas respondieron HTTP 200 con
`?capture=1`. El adaptador utiliza ese parámetro únicamente como segundo
intento tras un 403; comprueba host, ruta y encabezado del inventario. Los
identificadores y las referencias de procedencia mantienen la URL canónica.
No se utilizan credenciales ni sesiones autenticadas.

La portada también enlaza Urbanismo, obras públicas y medioambiente en
https://calamocha.sedelectronica.es/transparency/c56365ca-16bd-4784-8f55-93f63f5b8aa8/ .
Su HTML público devuelve HTTP 200 y anuncia dos elementos de planeamiento,
pero utiliza navegación AJAX Wicket. No se ha implementado esa navegación ni
se incorpora como un segundo registro de los mismos instrumentos. La categoría
de obras públicas e infraestructuras indica cero elementos en la captura.
La ruta municipal `/urbanismo-y-servicios/` devolvió 403 en la consulta inicial.
Estas comprobaciones de descubrimiento no son inventarios extraídos.

## Alcance, fechas y geometría

Resultado vivo: **8 instrumentos reales y 45 enlaces documentales**. Se trata
exclusivamente de la biblioteca documental publicada actualmente en las dos
páginas, con cobertura histórica parcial. No se afirma que represente todo el
planeamiento vigente o todas las modificaciones aprobadas. La consulta del BOP
provincial encontró instrumentos posteriores, por ejemplo la aprobación inicial
de la modificación 20:
https://bender.dpteruel.es/dpt/bopt.nsf/0/F69B4C1E196D7B26C1258D40004D7CCD .
Ese anuncio queda fuera del inventario extraído; no se completa la cobertura
con anuncios aislados o fechas asociadas a otro instrumento.

Los inventarios no indican fechas de publicación, acuerdo ni aprobación, ni
una fase jurídica verificable para cada instrumento. Los campos correspondientes
son nulos. El segmento `/2021/03/` de los adjuntos es una ruta de subida, no una
fecha de aprobación. No se atribuye vigencia o aprobación definitiva por disponer
de un PDF. No se extrae el texto de los PDFs para inferir esas fechas.

`geometry_status: unavailable`: se conservan los planos PDF, pero no se ha
verificado una geometría vectorial vinculada a cada instrumento. Coordenadas
y geometría nulas, `publication_ready: false`, sin centroides ni jitter.
No se extraen licencias concedidas, formularios, contratación ni noticias.
`licencias.enabled: false`, `schedule.enabled: false` y
`geocode.jitter_missing: false`.

## Comportamiento y validación reproducible

Backfill y update refrescan íntegramente ambos inventarios. Identificadores
estables basados en PGOU/número de modificación, deduplicación de URL por
instrumento y escritura atómica después de validar ambas fuentes. Ante
contenido vacío, encabezado ausente, modificación no reconocible, procedencia
inesperada o indicadores de paginación/continuación, el adaptador falla sin
reemplazar la instantánea existente. No hay límite de filas ni recorte de páginas;
si el portal introduce paginación se exige revisar su recorrido.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_calamocha -v` — 4 pruebas pasan:
agrupación/deduplicación, PGOU único, fechas y geometría nulas, procedencia,
rechazo de cambios/paginación, integración manifiesto/registro, actualización,
conservación de salida ante fallo y licencias deshabilitadas.

La ejecución viva usa `load_manifest('calamocha')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se configura
`capture_dir` localmente para conservar los HTML consultados. Evidencia local:
`evidence/proyectos.jsonl`, `evidence/validation.json`, las páginas de inventario,
portada y transparencia, y un PDF de normativa. La validación incluye recuento,
URL fuente, limitaciones y comprobación HTTP/firma PDF de un documento por
instrumento. Los otros documentos se conservan como enlaces de inventario;
no se afirma haber descargado o validado todo su contenido. Evidencia excluida
de los cuatro archivos fuente entregables. Sin cambios compartidos, dependencias,
publicación ni acceso a bases de datos.
