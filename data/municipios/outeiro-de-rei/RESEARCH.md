# Outeiro de Rei — Lugo — INE 27039

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Inventario oficial y selección

El [inventario municipal de Urbanismo](https://outeiroderei.gal/urbanismo/) contiene tres enlaces de contenido. Dos son paquetes documentales de instrumentos urbanísticos concretos:

- [Plan de sectorización CC1-1 fase: Modificación da ordenanza industrial](https://outeiroderei.gal/urbanismo/plan-de-sectorizacion-cc1-1-fase-modificacion-da-ordenanza-industrial/): dos PDF, modificación puntual y plano del proyecto.
- [Núcleo rural Cartel. Modificación normas subsidiarias de planeamento](https://outeiroderei.gal/urbanismo/nucleo-rural-cartel/): siete PDF, contenido aprobado provisional, documento ambiental estratégico, memoria, normativa, índice de planos, planos y ficha del núcleo.

El tercer enlace, [Parque empresarial](https://outeiroderei.gal/urbanismo/parque-empresarial/), presenta el ámbito industrial y no contiene paquetes PDF en el formato de las dos fichas anteriores. Se excluye para no introducir una actuación genérica que solape el plan CC1-1. El inventario observado no tiene paginación; si aparecen controles de paginación el adaptador falla explícitamente para exigir revisar el recorrido, sin aceptar una primera página parcial.

Fuentes alternativas descubiertas: [SIOTUGA](https://siotuga.xunta.gal/siotuga/urb?lang=es_ES), inventario autonómico de planeamiento, no integrado en este adaptador; [sede municipal](https://outeiroderei.sedelectronica.gal/info.0), catálogo de trámites, no registro verificado de concesiones. Los [impresos de Urbanismo](https://outeiroderei.gal/servizos-municipais/impresos-para-tramites/urbanismo/) son solicitudes y formularios y se excluyen. No se usan anuncios de contratación ni noticias como proyectos. Esta implementación solo cubre los dos paquetes documentales del inventario municipal, no el conjunto histórico de planeamiento u obras del municipio.

## Extracción y semántica

Descubre enlaces de instrumentos en encabezados h2 del inventario, sin tomar los menús de navegación. Descarga cada ficha y conserva todos sus PDF de contenido con etiqueta original, URL y ficha de procedencia. Un registro por instrumento, no por PDF. IDs estables derivados de la URL de la ficha; enlaces duplicados se consolidan dentro de cada paquete. Si el inventario queda vacío, una ficha carece de PDF, aparece paginación o hay un error HTTP, falla antes de reemplazar la salida. La actualización vuelve a recorrer el inventario completo; no usa fechas del CMS como cursor.

No se extraen fechas de aprobación, acuerdo o publicación: ni fechas del CMS ni nombres de archivos acreditan por sí solos una fecha de acuerdo. Las etiquetas originales (incluida «Julio 2020») quedan en los documentos sin convertirlas a fechas exactas. No se afirma aprobación definitiva ni vigencia actual a partir del inventario. No se generan geometrías ni coordenadas. `publication_ready=false`, `geometry_status=unavailable`. Licencias, programación y jitter están desactivados en el manifest.

## Verificación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_outeiro_de_rei -v` — cinco pruebas correctas: selección frente a formularios/navegación, agrupación y procedencia, ausencia de fechas/coordenadas inferidas, rechazo de vacíos/paginación, actualización y conservación de salida ante fallo, carga por manifest y contrato de configuración.

Extracción real mediante `load_manifest('outeiro-de-rei')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 registros, 9 enlaces documentales**. `evidence/validation.json` recoge recuento, URLs, limitaciones, comprobaciones y capturas HTML con SHA-256. La primera petición exploratoria sin User-Agent de navegador recibió HTTP 403; las peticiones de la ejecución real con el User-Agent declarado en el adaptador devolvieron HTTP 200 para las tres páginas.

Se comprobó el primer PDF de cada paquete mediante HTTP Range: ambos respondieron 206, `application/pdf` y cabecera `%PDF-`. Las capturas `.pdf-head.bin` conservan solo 1024 bytes; no equivalen a una descarga completa ni a la validación del contenido jurídico. Los otros siete PDF se conservan como enlaces del inventario, sin comprobar individualmente su disponibilidad. La evidencia es local y no se incorpora a los cuatro archivos fuente. Sin publicación, base de datos ni despliegue.
