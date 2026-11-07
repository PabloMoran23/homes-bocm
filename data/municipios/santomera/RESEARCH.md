# Santomera — INE 30901, Murcia

Investigación y extracción en vivo: 7 de noviembre de 2026. Adaptador exclusivo
`municipio.adapters.santomera:SantomeraAyuntamientoAdapter`. Se revisaron el
contrato `portal.py`, el cargador de manifests, el registro de adaptadores y los
ejemplos de Chipiona y Manlleu antes de implementar.

## Fuentes oficiales y cobertura

Inventario actual del Ayuntamiento:
https://santomera.es/planeamiento/

El índice enlaza tres páginas documentales que también se extraen completas:

- https://santomera.es/planeamiento/pgmo/
- https://santomera.es/planeamiento/plan-parcial-sector-mz-16
- https://santomera.es/planeamiento/plan-parcial-sector-cb01/

La búsqueda descubrió asimismo la página municipal
https://santomera.es/urbanismo-obras-y-servicios/ y la sección de instancias y
solicitudes. Se seleccionó el inventario de planeamiento porque publica
instrumentos concretos y sus documentos; los formularios no acreditan licencias
concedidas. No se extraen noticias ni anuncios de contratación como proyectos.
No se utiliza santomera.info como fuente ni se presupone su oficialidad.

Resultado real: **8 instrumentos, 156 enlaces documentales**:

| Instrumento | Enlaces |
| --- | ---: |
| PGMO | 80 |
| Subsanación de deficiencias 1 | 6 |
| Subsanación de deficiencias 2 | 11 |
| Modificación 8 | 6 |
| Modificación puntual 10 | 9 |
| Modificación puntual 11 | 5 |
| Plan parcial MZ-16 | 19 |
| Plan parcial CB-01, en trámite, versión preliminar | 20 |

Un registro por encabezado de instrumento del inventario, con identidad estable
derivada de su título y todos sus documentos agrupados. Los volúmenes, planos,
memorias, anuncios y certificados no generan proyectos independientes. Cada
documento conserva título, URL y página de procedencia. Se respeta la grafía del
portal, incluso «Municipación». El inventario y las tres páginas de detalle no
mostraron paginación; si aparecen controles de paginación el adaptador falla
explícitamente para evitar una cobertura truncada. También falla ante páginas
vacías, ausencia de documentos o enlaces documentales a dominios inesperados.

Cobertura parcial del municipio: se extrae este inventario informativo actual,
no un histórico exhaustivo de planeamiento, obras o licencias. Las actualizaciones
repiten una instantánea completa; no se afirma recuperación de registros retirados.

## Fechas, procedencia y anomalías

El texto del índice atribuye al PGMO aprobación definitiva el 9 de septiembre de
2008: se conserva como `fecha_aprob`. Las fechas expresamente escritas en los
títulos documentales se conservan en el propio documento: `fecha_publicacion`
para el BORM y `fecha_acuerdo` para certificados del Pleno o Junta de Gobierno.
Por ejemplo, en la modificación 10 se distinguen publicación de 21/02/2025,
acuerdo de 30/01/2025 y acuerdo inicial de 29/02/2024. El certificado de CB-01
identifica el acuerdo inicial del 07/03/2024; no es una aprobación definitiva.
No se eligen entre esos eventos fechas genéricas para el instrumento. No se
deducen fechas de los nombres PDF, directorios de subida, metadatos del CMS o
de búsquedas; no se interpretan los textos interiores de todos los PDF.

Dos defectos de la fuente se mantienen visibles:

- MZ-16 enlaza como partes 15 y 16 dos PDF cuyos nombres identifican CB-01.
  Se retienen en el grupo donde el Ayuntamiento los publica, con advertencia
  `source_warnings` y procedencia. No se afirma que su contenido sea de MZ-16.
- SD.2 usa la misma URL de MZ-22 tanto para la ficha MZ-22 como para la ficha
  de núcleos especiales lineales. Se conservan ambas etiquetas originales.

La propia página del PGMO advierte del carácter informativo y posibles
modificaciones posteriores. No se afirma vigencia jurídica de cada documento.
Sin coordenadas ni geometrías inventadas; `publication_ready: false`.
Licencias, programación y jitter desactivados en el manifest.

## Acceso y validación

El HTTPS del portal no valida su cadena de confianza en este entorno, ni con las
CA del runtime ni con `/etc/ssl/certs/ca-certificates.crt`; curl también falla.
La lectura pública real fue posible con verificación TLS desactivada. El manifest
declara expresamente `verify_tls: false`; el código usa verificación por defecto
cuando no recibe esa configuración, y no silencia la advertencia de requests.
Esta excepción reduce la garantía de autenticidad del transporte y queda reflejada
en `evidence/validation.json`. No se modifica la configuración TLS compartida.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas ejecutadas: `python -m unittest municipio.test_santomera -v`, cinco
correctas. Comprueban agrupación y aislamiento documental, fechas de publicación
frente a acuerdos, exclusión de formularios, páginas vacías/cambiadas/paginadas,
dominios inesperados, lectura de detalles, actualización sin duplicados y manifest.

La ejecución real invocó `backfill_proyectos(Path('evidence/proyectos.jsonl'))`
con la configuración del manifest y `capture_dir='evidence/captures'`. Evidencia
local, sin publicar ni incorporar a los fuentes:

- `evidence/proyectos.jsonl`: ocho registros reales.
- `evidence/validation.json`: recuento, fuentes, fecha de comprobación y límites.
- `evidence/captures/*.html`: las cuatro respuestas HTML usadas por el adaptador.
- `evidence/document-sample-prefix.bin`: primeros 1024 bytes del anuncio BORM de
  la modificación 10; HTTP 200, `application/pdf`, firma `%PDF-` comprobada en
  https://santomera.es/wp-content/uploads/2026/01/20250221_PGMO_Mod10_Anuncio-BORM.pdf .

No se descargó ni verificó individualmente la disponibilidad o el contenido de
los 156 enlaces PDF; son enlaces publicados por la fuente. No se instalaron
dependencias ni se modificaron fuentes compartidos.
