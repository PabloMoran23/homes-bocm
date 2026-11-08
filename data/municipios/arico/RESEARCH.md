# Arico — INE 38005

Municipio: Arico. Provincia: Santa Cruz de Tenerife. Comunidad: Canarias.
Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuentes oficiales descubiertas

- Área municipal: https://www.ayuntamientodearico.com/urbanismo-vivienda-y-catastro/ . Describe funciones y contacto, no ofrece un registro de licencias concedidas. Consultada mediante búsqueda/web; la captura directa con requests falló por certificado TLS (no se desactivó su validación). No se extraen noticias ni formularios como proyectos.
- Catálogo del Gobierno de Canarias: https://datos.canarias.es/catalogos/general/dataset/planeamiento-urbanistico-de-arico . Productor: Consejería de Política Territorial, Cohesión Territorial y Aguas. Los metadatos describen normalización por GRAFCAN y financiación del programa Urbanismo en Red 2010–2015. La actualización del catálogo no equivale a una nueva aprobación ni acredita vigencia.
- API de inventario: https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=planeamiento-urbanistico-de-arico . Respuesta real HTTP 200, `success=true`, 87 recursos. `package_show` entrega el array completo, sin páginas de búsqueda: se exige coincidencia de `num_resources` y longitud del array. No hay corte por fecha, número de registros o páginas.
- Archivo regional: https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=5&provincia=38 . Identifica ARICO y muestra 7 instrumentos generales y 16 de desarrollo. No coincide con los 22 grupos del catálogo; por ello la cobertura se declara parcial. No se utiliza el archivo como una supuesta lista adicional de proyectos ni se inventa el instrumento que falta.

## Unidad de registro y documentos

Un registro por denominación completa de instrumento/aprobación del catálogo, agrupando recursos HTML, consulta GRAFCAN, ZIP SIPU y ZIP FIP. Las modificaciones y textos refundidos son instrumentos diferenciados. Se conserva cada ID de recurso, descripción literal, formato, URL y ficha del catálogo. Los enlaces PDF se resuelven dentro del directorio del índice de ese instrumento y se deduplican. No se convierten capítulos ni planos en proyectos adicionales.

Resultado real: **22 registros**, agrupando los **87 recursos** y **332 enlaces PDF no ambiguos** (419 entradas documentales en total). Ejemplos: modificación Nº5 La Jaca/Las Maretas/El Viso/Arico El Viejo/La Cisnera/El Río, plan parcial La Jaca-Oeste SAU-R8, PERI Jardín del Atlántico, Normas Subsidiarias, Los Abriguitos y Los Llanos del Porís. El adapter descarga el inventario y todos los índices enlazados en cada ejecución; no contiene registros precargados.

Inconsistencia comprobada: el catálogo asigna tanto al PERI Las Eras como al texto refundido del PERI Porís de Abona el índice https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Aric/510/indice.html . Su encabezado dice «Plan Especial de Reforma Interior de Las Eras». Ambos registros conservan sus recursos declarados por el catálogo y llevan `source_warnings` y `document_index_status=ambiguous_catalogue_association`; ninguno recibe la expansión PDF del índice compartido. No se intenta corregir la fuente inventando otra URL. Los identificadores de registro distinguen ambas denominaciones.

Se comprobó una muestra del índice 516: https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Aric/516/PIP/mp07nnss_aric_pi01.pdf respondió HTTP 200 con tipo PDF y firma `%PDF-`. Solo se capturaron los primeros 1024 bytes. No se afirma haber validado todos los PDF o los ZIP completos.

## Semántica y límites

`fecha_acuerdo` procede exclusivamente de la cláusula de acuerdo del metadato; `fecha_publicacion` de «publicado el» y se refiere al boletín. Se mantienen separadas. Fechas ausentes se omiten; fechas contradictorias causan error. No se usa la creación/modificación de CKAN, el nombre del archivo ni la fecha de captura para atribuir aprobación. `fase=aprobacion_definitiva` refleja la denominación del catálogo y no acredita vigencia jurídica actual ni ejecución material. La descripción original se conserva dentro del recurso documental.

Son instrumentos de planeamiento reales documentados, sin expediente administrativo inferido, sin coordenadas y sin licencias concedidas. `source_entity_type=documento` expresa la naturaleza documental de esta cobertura; la política común los clasifica como documentos, sin actividad publicable. `publication_ready=false`, `geometry_status=unavailable`. La procedencia regional se declara en cada registro aunque el esquema de manifest usa `proyectos.source=ayuntamiento` para el pipeline municipal. Licencias, ejecución programada y jitter desactivados. Actualizar equivale a refrescar el inventario completo, no a simular incrementalidad.

## Validación reproducible y evidencia local

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_arico -v`: siete pruebas correctas. Cubren agrupación, fechas separadas y ausentes, conflictos, inventario incompleto/ajeno/vacío, rechazo de formulario, aislamiento de PDF, deduplicación, índice compartido y manifest/licencias sin red.
- Ejecución real mediante `load_manifest('arico')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, usando `capture_dir=evidence` solo en la configuración local de esa ejecución.
- `evidence/proyectos.jsonl`: registros reales con anotación de política común.
- `evidence/validation.json`: cuenta, URLs, limitaciones, resultado y pruebas.
- `evidence/catalogo.json`, `evidence/indice-*.html`, `evidence/archivo-regional.html`: capturas de fuentes; `sample-pdf-check.json` y `sample-pdf-prefix.bin`: comprobación parcial de documento.

La evidencia es local y no forma parte de los cuatro archivos fuente. Sin accesos a bases de datos, publicación, despliegue o modificaciones compartidas.
