# Lardero — INE 26084, La Rioja

Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuentes oficiales y selección

- [Urbanismo municipal](https://www.aytolardero.org/tramites-administrativos/urbanismo/): publica requisitos de solicitud, instancia urbanística, autoliquidaciones y normativa general. Enlaza expresamente el Plan General Municipal. No es un registro de licencias concedidas; estos formularios no se convierten en actuaciones. `licencias.enabled=false`.
- [Inventario del Plan General Municipal](https://www.aytolardero.org/plan-general-municipal/): fuente implementada. La página sirve el inventario completo observado en su HTML, con secciones desplegables Elementor. Contiene 380 enlaces únicos de descarga municipal PDF bajo `/Descargar/`. No se observó paginación. Si aparecen controles de paginación, el parser falla explícitamente para evitar una cobertura truncada.

Se extrae **un instrumento real**, el Plan General Municipal de Lardero, con sus **380 documentos**, no 380 proyectos. El contenido incluye catálogo de edificios protegidos y arqueológico, normativa y ordenanzas, fichas de suelo urbanizable y unidades de ejecución, y documentación gráfica (esquema director, suelo no urbanizable/urbanizable/urbano y estructura territorial). Se retienen título literal, URL, categoría de origen de la descarga y página de procedencia para cada documento. Las etiquetas repetidas, como SP-1 en secciones diferentes, conservan sus enlaces diferenciados. Se deduplica únicamente la URL idéntica.

El parser exige la página y título esperados, el contenedor de contenido municipal y documentos con el formato de descarga observado. Rechaza inventarios vacíos y enlaces de descarga con formato inesperado. No toma formularios, navegación, noticias ni anuncios de contratación como proyectos. El identificador estable corresponde al instrumento, no a una posición del listado. Las actualizaciones refrescan el inventario completo; no afirman mantener un historial incremental ni detectar bajas históricas.

## Semántica y límites

La cobertura es parcial: solo la colección documental del PGM que el ayuntamiento publica actualmente. No se afirma exhaustividad de modificaciones posteriores, obras, licencias u otros expedientes en la sede o registros autonómicos. No se han utilizado esos otros portales como fuentes de extracción.

La publicación actual de documentos no acredita por sí sola la vigencia consolidada ni una fase de tramitación. Los nombres de algunos archivos contienen `feb-2007`; esa referencia documental no se interpreta como fecha de acuerdo, aprobación o publicación. No se incorporan fechas de negocio ni se usan las fechas técnicas del CMS. No hay coordenadas ni geometría extraídas de los planos. Cada registro declara `publication_ready=false`, `geometry_status=unavailable` y las limitaciones. El manifest desactiva programación, licencias y jitter geográfico.

Se comprobaron tres descargas representativas: catálogo de edificios protegidos (12028), normativa urbanística general (12035) y plano territorial P1_2–B2 (12428). Las tres devolvieron HTTP 200, `application/pdf` y firma `%PDF-`; se guardaron sus bytes en evidencia. No se descargaron ni verificaron individualmente los 380 archivos, y el adapter conserva enlaces sin afirmar que cada PDF esté disponible.

## Validación reproducible

Runtime preinstalado utilizado:

```text
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_lardero -v
```

Resultado: cinco pruebas correctas. Cubren agrupación y deduplicación, separación de categorías con etiquetas repetidas, exclusión de formularios/enlaces ajenos, ausencia de fechas y geometría inferidas, rechazo de inventarios ausentes/paginación/formato desconocido, refresco y preservación de la salida ante error, licencias desactivadas e identidad/configuración del manifest.

Extracción en vivo ejecutada mediante `load_manifest('lardero')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir='evidence'` como configuración local. Se utilizó el wrapper normal del registro de adaptadores, incluida su anotación de política de entidades. Resultado: un registro y 380 documentos. La política no identifica categoría especializada para este instrumento general (`unknown=1`, estado `ok`); no se fuerza una categoría de obra.

Evidencia local, fuera de los cuatro archivos fuente entregables:

- `evidence/proyectos.jsonl`: registro extraído realmente.
- `evidence/validation.json`: cantidad real, fuentes, limitaciones, resultado de pruebas y comprobaciones documentales.
- `evidence/pgm-live.html`: captura de la petición hecha por el adapter.
- `evidence/pgm.html`, `evidence/urbanismo.html`: capturas de investigación.
- `evidence/document_checks.json` y `evidence/document-{0,5,379}.pdf`: comprobaciones de las tres descargas.

No se usaron bases de datos, publicación, geocodificación, despliegues ni procesos globales del pipeline.
