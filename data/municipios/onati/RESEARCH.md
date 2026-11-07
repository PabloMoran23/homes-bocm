# Oñati — Gipuzkoa — INE 20059

Verificación: 2026-11-07. Adaptador único `OnatiAyuntamientoAdapter`, conforme al
contrato de `municipio/adapters/portal.py` y al esquema de `municipio/manifest.py`.
Se revisaron también los ejemplos de Hernani, Chipiona y Manlleu.

## Descubrimiento y fuentes oficiales

La [sección municipal de Hirigintza](https://www.xn--oati-gqa.eus/eu/udala/sailak/hirigintza-eta-lurralde-antolamendua)
enlaza el [inventario Hiri-antolamendua](https://www.xn--oati-gqa.eus/eu/udala/sailak/hirigintza-eta-lurralde-antolamendua/hiri-antolamendua).
Se consulta este inventario en cada ejecución; no se usan noticias individuales
como semillas ni un listado de expedientes prefabricado.

El índice muestra las normas consolidadas y cinco apartados documentales: memoria,
planos de información/ordenación, normas generales y dos volúmenes de normas
particulares. Se descubren y recorren todos ellos. Los documentos, capítulos y
fichas de ámbitos se agrupan en **un instrumento**, sin convertir cada PDF en un
proyecto independiente. Se retiene cada URL única, su página de procedencia,
sección, nombre de archivo y texto del enlace. El mismo PDF enlazado repetidamente
se deduplica dentro del instrumento.

Desde ese mismo índice se descubren:

- [HAPO: proceso de redacción](https://www.xn--oati-gqa.eus/eu/udala/planak/hapo-edo-hiri-antolamenduaren-plan-orokorra/hapo-edo-hiri-antolamenduaren-plan-orokorraren-idazketa-prozesua).
  Contiene 50 PDF bajo «Hasierako onespenaren agiriak»: normativa general y fichas
  particulares HG/SG. Constituyen un solo HAPO. La cabecera también contiene la
  contratación de su redacción y una noticia: **no se extraen como proyectos**.
  La fecha 2017-10-24 pertenece a aquella contratación; no fecha el HAPO.
- [Arau aldaketa](https://www.xn--oati-gqa.eus/eu/udala/sailak/hirigintza-eta-lurralde-antolamendua/hiri-antolamendua/arau-aldaketa).
  Modificación sobre usos admisibles en las zonas de protección especial y
  agroganadera del suelo no urbanizable. Se conserva la descripción municipal.
  Sus tres PDF (modificación y documentación ambiental), plano JPG y enlace al
  programa de participación se agrupan en un solo instrumento.

## Resultado y semántica

La ejecución real produjo **3 registros con 157 enlaces documentales**:
102 de las normas consolidadas, 50 del HAPO y 5 de la modificación.
Las ocho páginas de inventario/detalle respondieron correctamente y sus capturas
se guardan en `evidence/captures/`. `evidence/validation.json` enumera las URLs
exactas consultadas. Se descargó además una muestra PDF de cada instrumento,
comprobando HTTP y cabecera `%PDF-`; no se descargó ni auditó íntegramente cada
uno de los 157 enlaces.

No se asignan fechas genéricas, de acuerdo, publicación ni aprobación: los campos
explícitos quedan nulos. La referencia de la página de Urbanismo al GAO del
29-06-2006 es una publicación normativa, no prueba de fecha de acuerdo. No se
utilizan años de nombres de archivos como fechas. La presencia de documentos de
aprobación inicial del HAPO no demuestra su situación legal actual completa y no
se infiere una fase vigente. Se preservan títulos originales en euskera.

Los IDs se derivan de la URL canónica del instrumento; no de títulos o posiciones.
Las variantes Unicode del dominio municipal se normalizan a IDNA. No se aceptan
redirecciones inesperadas ni documentos alojados en dominios no revisados.

## Cobertura y límites

Cobertura **parcial**, limitada al índice documental municipal consultado y sus
apartados enlazados; no constituye inventario exhaustivo de todos los proyectos,
obras, modificaciones históricas o expedientes administrativos de Oñati. No se
extraen licencias concedidas: trámites y formularios no son concesiones.
`licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`.

Las páginas revisadas no tienen paginación. El parser rechaza controles de
paginación conocidos o enlaces siguiente: no devuelve una primera página como
inventario completo. Un nuevo instrumento no reconocido en la navegación
secundaria requiere revisión explícita. La pérdida de contenido, PDFs o un fallo
HTTP aborta la extracción antes de reemplazar la salida anterior. La actualización
hace una lectura completa, sin filtro temporal ni escritura de estado incremental.

## Geometría

`geometry_status: unavailable`. La web municipal enlaza el
[visor HerriGIS de Oñati](https://herrigis.gis-cdn.net/oinati/).
Se comprobó su entrada pública (resultado en `validation.json`). No se ha
verificado una capa vectorial con identificadores asociables a estos tres
instrumentos. Los planos PDF/JPG no se convierten en coordenadas; no se inventan
centroides, geometrías ni CRS. `publication_ready=false` en todos los registros.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_onati -v
```

Las pruebas cubren descubrimiento y agrupación, deduplicación de documentos,
procedencia, exclusión de contratación/noticias, ausencia de fechas inferidas,
rechazo de paginación/cambios de host, licencias vacías y conservación de salida
ante fallo. La extracción real se ejecutó llamando a
`OnatiAyuntamientoAdapter('onati', config={'evidence_dir': 'evidence/captures'})`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas
HTML y muestras PDF. No forman parte de los cuatro archivos fuente. Sin cambios
compartidos, dependencias nuevas, despliegue, publicación ni acceso a bases de datos.
