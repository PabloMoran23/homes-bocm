# Moya — Las Palmas — INE 35013

Comprobación en vivo: 2026-11-08. Un adaptador, sin cambios compartidos ni dependencias.

## Descubrimiento e identidad

- Web municipal: https://www.villademoya.es/ y área https://www.villademoya.es/areas/urbanismo (HTTP 200).
- Sede: https://moya.sedelectronica.es/info.0 (HTTP 200). Su enlace «Planeamiento Urbanístico de Moya» lleva a https://moya.sedelectronica.es/transparency/557f7138-2b5e-43f0-9db7-8cc2bc938eaf/ .
  Esta sección histórica (hasta 2019) ofrece dos documentos de normas y enlaza el archivo autonómico con `provincia=35&municipio=13`:
  https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?provincia=35&municipio=13 .
  El enlace se documenta como descubrimiento; ese archivo no se usa como extracción.
- Inventario oficial autonómico: https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-moya .
  API usada: https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-moya (HTTP 200).
  Productor: Gobierno de Canarias, Consejería de Política Territorial, Cohesión Territorial y Aguas; normalización GRAFCAN.
  Paquete identificado por UUID `5e5b27a4-0c5e-49de-9886-ce68ff3732ef`.
  El portal estatal/regional también lo describe: https://datos.canarias.es/catalogos/general/dataset/planeamiento-urbanistico-de-moya .

No se trata de Moià (Barcelona) ni Moya (Cuenca). No se extraen formularios de la sede como concesiones.
`proyectos.source: ayuntamiento` es la ruta de adaptador del esquema existente;
los registros identifican expresamente su procedencia efectiva como `source: sitcan`.

## Cobertura real

`package_show` devuelve las **18 distribuciones completas**, sin paginación de resultados.
Se comprueba `num_resources == len(resources)`, identidad del paquete, ausencia de
continuación y unicidad de IDs. No hay límite de registros ni recorte de páginas.
Cada instrumento se agrupa por su denominación oficial, separando el sufijo de publicación.
Su ID deriva de esa denominación, independiente del orden de distribuciones.
Un formato de título, host, duplicación o ausencia de índice no revisados provoca error.

Los cinco registros son:

| Instrumento | Publicaciones indicadas por SITCAN |
| --- | --- |
| Normas Subsidiarias | 1999-11-10, BOC 149/99 |
| Modificación Puntual Nº55 de Normas Subsidiarias | 2002-12-23, BOC 170/02 |
| Modificación Puntual Nº27 de Normas Subsidiarias | 2005-09-16, BOC 183/05 |
| Estudio de Detalle de Calle La Fonda | 2022-06-01, BOC 107/22 |
| Estudio de Detalle en Calle Argentina y Camino Moreto | 2020-06-10, BOC 115/20; 2024-01-29, BOP 013/24 |

Se retienen las 18 URLs de distribución FIP/SIPU/consulta/documentación, sus IDs,
formatos y descripciones originales. Se recorren los cinco índices IDECanarias
descubiertos en el paquete, todos HTTP 200, y se añaden **76 enlaces PDF** con la URL
del índice como procedencia. No se generan registros separados por documento.
Índices: bajo `https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Moya/`,
directorios `522`, `523`, `524`, `ed-lafonda`, `ed-arg-mor`, archivo `indice.html`.
Si aparece navegación siguiente o desaparecen los PDFs se detiene la extracción.
No se descargaron todos los binarios ni se verificó individualmente su disponibilidad.

La fase «aprobación definitiva» reproduce el catálogo; no certifica vigencia jurídica
actual. Las fechas son publicaciones de boletín según los metadatos, no acuerdos,
ni metadatos de creación/actualización de CKAN. `fecha_publicacion` contiene la primera
publicación identificada y `publicaciones` conserva todas con boletín y número.
`fecha`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. No se deducen fechas de ZIPs.

La cobertura municipal es **parcial**, restringida al inventario SITCAN. La página
https://www.villademoya.es/ayuntamiento/plan-general-de-ordenacion-urbanistica-2025
también existe (HTTP 200), describe un PGO en elaboración y enlaza
https://villademoya.es/PGO2025/DOCUMENTO_ALCANCE__PGO_MOYA.pdf .
Ese PGO no está incluido en los cinco instrumentos del paquete y queda fuera de esta
implementación. También quedan fuera PMUS, ARRU, noticias, contratación, obras no
inventariadas en SITCAN y licencias. Los métodos update refrescan la instantánea completa;
no prometen un histórico de eliminaciones ni continuidad incremental por fechas.

## Geometría y revisión

`geometry_status: not_extracted`. Se preservan archivos FIP/SIPU y planos PDF como
enlaces, pero no se han inspeccionado sus capas ni verificado un CRS o una geometría
asociada a cada instrumento. No se inventan puntos ni se geocodifica el centro municipal.
Todos los registros llevan geometría y coordenadas nulas y `publication_ready: false`.
El clasificador compartido del registro de adaptadores marca los cinco como
`pendiente / insufficient_identity_evidence`: no hay número de expediente reconocido
por sus reglas. Se conserva este resultado, sin fabricar referencias para eludirlo.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_moya -v`: **4 pruebas, OK**. Cubren agrupación,
doble publicación, identidad estable, rechazo de paquetes incompletos/ajenos,
formularios, duplicados, paginación documental y licencias deshabilitadas.

Extracción real mediante `load_manifest('moya')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, usando
`manifest.portal.config['capture_dir']='evidence'` sólo para esta ejecución.
Resultado: **5 registros**, 18 distribuciones y 76 PDFs enlazados.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/package-live.json`, cinco índices capturados y páginas de descubrimiento.
No se versionan evidencias. Programación deshabilitada, licencias deshabilitadas,
`geocode.jitter_missing: false`. Sin publicación ni acceso a servicios de producción.
