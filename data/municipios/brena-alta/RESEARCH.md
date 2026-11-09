# Breña Alta — INE 38008

Investigación y extracción real: 9 de noviembre de 2026. Provincia: Santa Cruz de Tenerife; comunidad autónoma: Canarias.

## Fuentes oficiales y selección

El [portal municipal de transparencia](https://transparencia.brenaalta.es/ordenacion-del-territorio/plan-de-ordenacion/) enlaza el [PGO municipal](https://www.balta.org/pgo/index.php?id=01#a1). El resto de sus descargas son instancias, comunicaciones previas, certificados y tasas: **no son licencias concedidas ni proyectos individuales** y se excluyen. La fecha de actualización del portal tampoco se interpreta como fecha de un acuerdo.

Se descubrió y verificó el [inventario oficial de planeamiento de Breña Alta del Gobierno de Canarias](https://datos.canarias.es/catalogos/general/dataset/planeamiento-urbanistico-de-brena-alta). Su productor es el Gobierno de Canarias, con normalización de GRAFCAN; no se atribuye este catálogo al Ayuntamiento. La [API CKAN package_show](https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=planeamiento-urbanistico-de-brena-alta) permite obtener el paquete completo, sin búsqueda paginada. En la ejecución, `num_resources=11` coincide con los once recursos recibidos. El adaptador comprueba esa igualdad y procesa todos los recursos; una respuesta vacía, incompleta, de otro municipio o con recursos inesperados provoca error.

También se inspeccionó la [sección municipal de obras públicas en ejecución](https://transparencia.brenaalta.es/obras-publicas/obras-publicas-fase-ejecucion-administracion/). Enlaza al perfil de contratación y hojas de contratos de obras de 2022–2025. No se incorporan esos contratos: la cobertura implementada es exclusivamente el inventario de planeamiento. No se han usado anuncios de licitación ni noticias como sustituto de proyectos.

`proyectos.source: ayuntamiento` selecciona la ruta de adaptador municipal del esquema existente. La procedencia efectiva se declara en las notas del manifiesto y en cada registro (`source: gobierno_canarias`, `organismo_fuente`, `source_url`, `inventory_url`). No requiere modificar el esquema ni el registro compartido.

## Registros y documentos

| Instrumento del catálogo | Distribuciones | PDF enlazados |
| --- | ---: | ---: |
| [Plan General de Ordenación](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/BreA/458/indice.html) | 4 | 147 |
| [Sectores SUNSE-1 / SUNSD-1 Bajamar](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/BreA/459/indice.html) | 4 | 3 |
| [Modificación puntual nº1 La Grama 2](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/BreA/mp1-lagrama2/indice.html) | 3 | 2 |

Resultado real: **3 instrumentos, 11 distribuciones y 152 enlaces PDF**. Las distribuciones de consulta, documentación y sistematización ZIP del mismo instrumento se agrupan por título normalizado; el identificador se deriva de la URL de su índice documental. No se precargan registros de ejemplo ni se genera una actuación por cada plano. `distributions` conserva IDs CKAN, títulos, descripciones, formatos y enlaces de cada recurso. `documentos` conserva los enlaces PDF relativos resueltos y su índice de procedencia, sin mezclar directorios de distintos instrumentos.

Los tres índices son listados estáticos completos, sin paginación observada. El scraper recorre todos sus enlaces, deduplica por URL y falla si aparece paginación reconocible o desaparecen los documentos. Los límites de tamaño producen error, nunca una extracción truncada. Solo se escribe el resultado tras completar todos los instrumentos. La actualización vuelve a extraer la instantánea completa; no afirma detectar bajas ni mantener un histórico incremental.

## Fechas, alcance y limitaciones

Las fechas de boletines aparecen en `publicaciones`, con boletín y referencia separados: PGO, BOC 15/12/2010 y BOP 08/02/2011; Bajamar, BOC 23/01/2012; La Grama 2, BOP 06/01/2023 y BOC 26/01/2023. No se elige arbitrariamente una fecha única de publicación. Solo Bajamar tiene `fecha_acuerdo=2011-12-23`, extraída de la expresión explícita «por pleno COTMAC 23/12/2011» en el título del catálogo. No se usan fechas de creación o modificación del catálogo, nombres de ZIP o fechas de boletines para inventar una aprobación.

La página municipal del PGO describe aprobación definitiva **parcial** el 23/11/2010; el título del catálogo regional dice «Aprobación Definitiva». Se conserva esa denominación de origen, sin deducir de ella vigencia íntegra ni rellenar una fase normalizada. El contenido de los PDF no se interpreta. La ejecución comprobó un PDF de cada instrumento (HTTP 200, `application/pdf`, firma `%PDF-`), guardando solamente sus primeros 1024 bytes; no comprobó individualmente los 152 archivos ni los ZIP.

Cobertura parcial, no inventario de todas las obras ni licencias municipales. Sin coordenadas o geometrías verificadas; no se inventan. Todos los registros declaran `publication_ready: false` y `geometry_status: unavailable`. Licencias, programación y jitter están desactivados. La política compartida de entidades conserva los tres registros como `pendiente` (`unknown=3`); no se fuerza su clasificación ni se reclama elegibilidad para publicación.

## Verificación y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_brena_alta -v
```

**7 pruebas correctas**: agrupación, separación de fechas, identidad estable, rechazo de inventarios vacíos/incompletos o ajenos y formularios/anuncios, aislamiento de documentos, actualización completa, fallo sin sustituir una instantánea anterior, licencias desactivadas e identidad/configuración del manifiesto.

Extracción real mediante el cargador existente, sin publicación ni base de datos:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

manifest = load_manifest('brena-alta')
manifest.portal.config['capture_dir'] = 'evidence/captures'
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local excluida de los cambios de código: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas de la API y de los índices en `evidence/captures/` (cuerpo, URL, estado HTTP, tipo y SHA-256), HTML de descubrimiento y tres prefijos PDF. `validation.json` registra `live_records=3`, URLs consultadas, conteos documentales, pruebas y limitaciones. El cargador genera además su informe de política de entidades. No se han modificado fuentes compartidas, dependencias ni herramientas de despliegue.
