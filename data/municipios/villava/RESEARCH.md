# Villava / Atarrabia — Navarra — INE 31258

Verificación: 2026-11-07. Adaptador de una única fuente documental municipal,
con cobertura parcial: Plan General Municipal (PGM). No es un registro de
licencias concedidas ni un inventario exhaustivo de actuaciones municipales.

## Descubrimiento y selección de fuentes

- Inventario oficial de transparencia: https://www.villava.es/transparencia/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/
  Ofrece «Plan General de Ordenación Urbana (PGOU), mapas y planos en detalle».
  El adaptador descubre ese enlace en cada ejecución, sin fijar una noticia
  individual. Su URL `/news/documentacion-del-plan-general-municipal/` redirige a
  https://www.villava.es/general/documentacion-del-plan-general-municipal/.
  Ambos recursos de la extracción final responden HTTP 200.
- https://www.villava.es/transparencia-2/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/
  Enumera obligaciones informativas, sin enlaces a expedientes en su contenido.
  No se convierte ese texto genérico en proyectos.
- https://www.villava.es/actualidad/tablon/ redirige al tablón público Sedipualba
  https://sedeelectronica.villava.es/tablondeanuncios/default.aspx.
  La captura consultada muestra siete anuncios publicados de recaudación,
  presupuestos, patrimonio y empleo. Ninguno acredita un instrumento urbanístico
  o una obra pública. No se extraen. No se ha recorrido un archivo histórico del
  tablón; no se afirma ausencia de otros instrumentos en el municipio.
- Una búsqueda exploratoria en WordPress mostró también noticias sobre PEAU.
  No se incorpora como inventario ni se atribuye cobertura a esa búsqueda:
  no se ha recorrido ni validado exhaustivamente el archivo de noticias.

## Registro y semántica

La ejecución real produce **1 instrumento** (`villava-pgm`) con **23 documentos**:
22 enlaces PDF (acuerdo, memoria, estudio ambiental en tres partes, informe
económico, catálogo, normativa, ordenanzas y planos) y un anuncio BON. Los anexos
no son proyectos separados. Se conserva título, sección, URL documental y URL
de la página que lo enlaza. Se normalizan barras repetidas de las rutas para
evitar duplicados sin perder consultas. Todos los enlaces documentales de la
sección se recorren, sin topes ni cortes por fecha.

La página narra aprobación inicial del **12 de mayo de 2015** y aprobación
provisional acordada el **25 de octubre de 2016**. Se guardan como eventos
históricos en `acuerdos_documentados`, con sus textos fuente. Las fechas generales
de publicación, acuerdo y aprobación quedan nulas: no se asigna una fecha única
ni fase actual a todo el expediente. El estado vigente **no está verificado**;
la página continúa enlazada actualmente pero su narrativa es histórica. No se
infiere fecha de publicación de las rutas de subida, de la cabecera HTTP ni de
las fechas de sesión. Tampoco se afirma aprobación definitiva.

No hay paginación en las dos páginas documentales revisadas. El parser rechaza
controles de paginación si aparecen, y exige la página del PGM, sus acuerdos,
memoria y planos. Si cambia el inventario o desaparecen elementos esenciales,
falla antes de sustituir la salida. `update_proyectos` vuelve a leer el inventario
completo de esta fuente; no mantiene un histórico de documentos retirados.

## Documentos y geometría

Se comprobó además HTTP 200 y firma `%PDF-` de la memoria:
https://www.villava.es/wp-content/uploads/2015/05/Memoria.pdf
(788850 bytes; captura local `evidence/memoria.pdf`). El adaptador conserva los
enlaces originales normalizados; no descarga ni analiza cada PDF ni verifica el
destino histórico del BON. La mezcla de documentos de distintas fechas en la
página no se presenta como una versión consolidada vigente.

`geometry_status: unavailable`. Los planos son documentos PDF. No se ha
verificado una capa vectorial asociada al identificador del PGM ni un CRS de
geometría extraíble. No se digitalizan planos ni se asignan centroides o
coordenadas inventadas. `lat`, `lon` y `geometry` quedan nulos;
`publication_ready: false`.

## Pruebas y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villava -v
```

Cuatro pruebas pasan: descubrimiento oficial y rechazo de paginación;
agrupación/deduplicación y semántica temporal; rechazo de detalles incompletos;
carga mediante manifest/registry, refresco y licencias deshabilitadas.
La extracción real se ejecutó mediante `load_portal_adapter(load_manifest('villava'))`
y `backfill_proyectos`, con `capture_dir` apuntando a `evidence` y la salida
`evidence/proyectos.jsonl`. El informe `evidence/validation.json` registra
`live_records: 1`, URLs, límites y comprobación documental. Las capturas
`inventory.html`, `pgm.html`, `discovery-0.html`, `discovery-1.html`,
`plan-discovery.html` y `tablon.html` permiten revisar la procedencia.

Solo se añaden los cuatro archivos fuente solicitados. Evidencias locales no
versionadas. `schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Sin publicación ni servicios de producción.
