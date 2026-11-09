# Vega de San Mateo — INE 35033, Las Palmas

Investigación y extracción en vivo: 8 de noviembre de 2026.

## Fuente implementada

Inventario municipal oficial [Documentos Urbanismo](https://www.vegadesanmateo.es/urbanismo/documentos-urbanismo), consultado mediante HTTP GET sin autenticación. Se examinó el contrato de `municipio/adapters/portal.py`, el cargador/esquema `municipio/manifest.py` y los ejemplos Chipiona y Hernani antes de implementar.

El cuerpo Drupal de la página contiene tablas de documentos. Los encabezados de instrumento abren un registro y las siguientes tablas temáticas aportan documentos al mismo instrumento hasta el siguiente encabezado. Se extraen los nombres de instrumentos y documentos de la respuesta actual, no de una lista de registros precargados. Los nombres de sección se conservan en cada documento. Una hoja del PGO titulada «10E-PLAN ESPECIAL DE PROTECCIÓN Y REFORMA INTERIOR» permanece como documento del PGO: no se interpreta como un expediente separado.

Resultado real: **3 instrumentos y 74 enlaces PDF**:

- Texto refundido de la adaptación básica del P.G.O.: 31 documentos.
- Plan parcial Hoya Viciosa: 22 documentos.
- Plan parcial La Vegueta: 21 documentos.

Cada registro conserva `inventory_url`; cada documento conserva nombre, sección, URL original y `source_url`. La URL principal del registro es su primer documento (la memoria), mientras que su identificador estable deriva del título del instrumento. Se conservan los enlaces HTTP originales tal como los publica el Ayuntamiento. Los 74 enlaces respondieron HTTP 200 con firma `%PDF-` durante la validación; se leyeron solamente los primeros 128 bytes de cada PDF. Esto verifica acceso y tipo, no integridad completa ni contenido jurídico. Se guardaron tres muestras binarias parciales, una memoria por instrumento, con extensión `.pdf.prefix` para no presentarlas como PDFs completos.

La página observada es un inventario único sin paginación. Se procesan todas sus tablas sin límite de registros. Los marcadores de paginación, secciones desconocidas con potencial cambio de agrupación, enlaces documentales inesperados, cuerpo ausente o instrumentos vacíos provocan error antes de sustituir el resultado. No se afirma cobertura completa del urbanismo municipal.

## Otras fuentes oficiales descubiertas y límites

El [catálogo del Gobierno de Canarias](https://datos.canarias.es/catalogos/general/dataset/planeamiento-urbanistico-de-vega-de-san-mateo) ofrece planeamiento sistematizado, modificaciones, corrección, estudio de detalle y documentación de sentencias en varios formatos. No se ingiere en este adaptador: sus distribuciones y fases requieren agrupación y conciliación con el inventario municipal para evitar duplicados. Sus fechas de actualización de catálogo no son fechas de acuerdo urbanístico.

La [exposición pública de la fase I del nuevo PGO](https://www.vegadesanmateo.es/noticia/el-ayuntamiento-de-vega-de-san-mateo-abre-el-periodo-de-exposicion-publica-de-la-fase-i-del) enlaza documentación externa de estudios previos. Es evidencia de que este inventario documental no cubre todo el planeamiento más reciente; no se incorpora esa noticia como si fuese un plan aprobado. La fecha visible de publicación de la noticia y el plazo de consulta no son fechas de aprobación del PGO. Estas dos páginas se capturaron para documentar el alcance pendiente.

No se extraen modelos de solicitud de licencia, convocatorias de contratación ni noticias generales. No se verificó un registro público de licencias concedidas: `licencias.enabled=false` y sus métodos escriben un resultado vacío explícitamente desactivado.

El inventario implementado no acredita vigencia jurídica, fechas de publicación, acuerdos o aprobaciones. Se omiten esas fechas y las fases en lugar de deducirlas del CMS, nombres de archivo o títulos. No se inventan coordenadas; `geometry_status=unavailable` y `publication_ready=false`. El manifest desactiva programación y desplazamiento de coordenadas ausentes.

## Verificación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_vega_de_san_mateo -v` — 4 pruebas correctas. Cubren agrupación/aislamiento de documentos entre instrumentos, procedencia, ausencia de fechas/coordenadas inferidas, duplicados, exclusión de formulario ajeno, rechazo de vacíos/cambios/paginación, backfill/update y conservación del resultado anterior ante error.

Ejecución real: carga del manifest con `load_manifest('vega-de-san-mateo')`, construcción de `VegaDeSanMateoAyuntamientoAdapter` y llamada a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se utilizó una envoltura de captura que delega a `requests.get` real para conservar la respuesta exacta consumida por el adaptador; no se sustituyó la red por fixtures.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json` (conteo, fuentes, limitaciones y comprobación de cada PDF), `evidence/inventory.html`, `evidence/research-1.html`, `evidence/research-2.html` y tres muestras `.pdf.prefix`. Sin bases de datos, publicación, instalación ni cambios compartidos.
