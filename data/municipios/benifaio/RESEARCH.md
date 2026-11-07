# Benifaió — INE 46060, provincia de Valencia

Investigación y extracción real: 7 de noviembre de 2026.

## Fuentes oficiales y descubrimiento

El [Registro de Entidades Locales de la Generalitat](https://www.entidadeslocales.gva.es/index.php?Itemid=9&id=46060&lang=es&option=com_reglocal_entloc&task=muestraEntidad&tipo=1) identifica el municipio de Benifaió. El inventario utilizado está dentro de la provincia 4 VALENCIA y el directorio 46060 BENIFAIÓ, sin confundirlo con Benifairó de les Valls o de la Valldigna.

La [página oficial de planeamiento urbanístico vigente](https://mediambient.gva.es/es/web/urbanismo/registro-autonomico-de-instrumentos-de-planeamiento-urbanistico) enlaza el índice público de documentación. Desde su rama Valencia se descubrió el [inventario específico de Benifaió](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46060%20BENIFAI%D3/). Ésta es la fuente operativa: instrumentos municipales depositados y publicados por la Generalitat, no una colección de noticias o anuncios de contratación.

Se investigaron también:

- `https://www.benifaio.es/`, la variante sin www y `/es/urbanismo`: conexiones cerradas por el servidor durante esta ejecución.
- [Sede electrónica municipal](https://benifaio.sedelectronica.es/info.0) y [transparencia](https://benifaio.sedelectronica.es/transparency): accesibles. Sus trámites no representan licencias concedidas; el árbol de transparencia requiere navegación AJAX y no se incluye en este scraper.
- [DOGV, modificación puntual número 1 del Plan General](https://dogv.gva.es/datos/2026/06/05/pdf/2026_15621_es.pdf), descubierta en la búsqueda: anuncio de información pública, con acuerdo de aprobación inicial del 29/04/2026 y publicación del 05/06/2026. No se incorpora como registro precargado: no aparece en el inventario recorrido. Es una limitación explícita de actualidad/cobertura.
- [Inventario SIGIF de planificación preventiva](https://desarrollo.vaersa.org/Planificacion/DetallePlanesMunicipio/336): identifica Benifaió, 46060 y Valencia, con PLPIF, LOTUP y plan de quemas. No se mezcla con el inventario urbanístico escogido.

## Extracción y agrupación

Resultado vivo: **2 instrumentos, 149 enlaces documentales, 20 directorios recorridos**:

1. `46060-1000 PG BENIFAIÓ 2020-0365`: Plan General, con **103 documentos**. Incluye la entrada `46060-1000B Anot.1_PGE ejecuc sentencia`, su inscripción, acuerdo, publicación, memoria y plano, además de la sentencia conservada en la carpeta principal. La anotación no se cuenta como un nuevo proyecto.
2. `46060-1001 2021-0241 CATÁLOGO DEL PG`: Catálogo de Bienes y Espacios Protegidos del Plan General, con **46 documentos**. Tiene expediente/inscripción y acuerdo propios; se mantiene como instrumento separado, sin convertir las fichas de bienes, anexos o planos en actuaciones independientes.

El identificador numérico registral determina la agrupación: el sufijo alfabético de una anotación se conserva en `entradas_registro`, junto a su título y URL original. Cada documento conserva título, URL de descarga y `inventory_url` del directorio que lo enumera. Se recorren recursivamente todas las carpetas descendientes; se ignoran enlaces de ordenación, padres y externos. No hay límites de páginas ni de registros. El índice Apache observado no tiene paginación; una marca de paginación, un índice vacío, una redirección o un cambio de estructura produce error. No se descargan masivamente los PDF.

Los índices usan ISO-8859-1 y rutas con escapes de bytes de esa codificación (`%D3`, `%C1`); se conservan esos enlaces funcionales sin convertirlos indebidamente a escapes UTF-8.

## Fechas, vigencia y límites

Se publican instrumentos documentados, sin afirmar licencia concedida, ejecución material ni vigencia jurídica completa. La presencia de una sentencia y su ejecución hace especialmente necesario mantener toda la documentación del Plan General.

El scraper no analiza el texto PDF ni asigna `fase`, `fecha_aprob`, `fecha_acuerdo` o `fecha_publicacion`. Los años de expediente y los nombres de archivo no se convierten en fechas. Publicación y acuerdo son conceptos distintos. La comprobación manual de los dos acuerdos PDF confirma que pertenecen respectivamente al Plan General (expediente 1508540) y al Catálogo (2039898-CA); no alimenta campos temporales del parser.

Cobertura parcial: sólo documentación depositada accesible en este registro. Quedan fuera instrumentos pendientes como la modificación n.º 1 de 2026, el tablón municipal completo, obras públicas, licencias y otras planificaciones. Sin coordenadas ni geometrías extraídas: `geometry_status: unavailable`, `publication_ready: false`. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` están desactivados. Las actualizaciones rehacen el inventario completo porque no existe un cursor fiable de publicaciones.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_benifaio -v
```

Cinco pruebas correctas: codificación y ámbito de enlaces, agrupación recursiva y separación de instrumentos, rechazo de vacíos/cambios/paginación/documentos huérfanos, manifiesto y licencias desactivadas, y conservación de salida anterior ante fallo de red.

La extracción real se ejecutó mediante `load_manifest('benifaio')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `portal.config.capture_dir='evidence/live-captures'` únicamente en memoria. Se aplicó también la política compartida del registro de adaptadores, sin modificarla. Esta política clasifica ambos títulos registrales abreviados como categoría desconocida; no se ha inventado una categoría física para solventarlo.

Evidencia local, excluida del cambio de fuentes:

- `evidence/proyectos.jsonl`: los 2 registros reales y sus 149 documentos.
- `evidence/validation.json`: `live_records`, `source_urls` de los 20 índices, limitaciones, comprobaciones documentales y resultado de política compartida.
- `evidence/live-captures/listing-*.html`: los 20 índices de la extracción, con correspondencia URL/archivo en validation.
- Capturas adicionales del descubrimiento municipal, GVA y SIGIF.
- `evidence/benifaio-plan-46060-1000-acuerdo.pdf` y `evidence/benifaio-plan-46060-1001-acuerdo.pdf`: HTTP 200, `application/pdf` y firma `%PDF-` comprobados. Textos derivados locales en `plan-acuerdo.txt` y `catalogo-acuerdo.txt`.

No se han utilizado credenciales, bases de datos, publicación ni despliegue.
