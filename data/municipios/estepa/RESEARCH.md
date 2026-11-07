# Estepa (Sevilla), INE 41041

Investigación y extracción real: 7 de noviembre de 2026. Se revisaron el contrato de `municipio/adapters/portal.py`, el cargador de manifests, el registro dinámico de adaptadores y los ejemplos de Chipiona y Manlleu antes de implementar. No se necesitan cambios compartidos ni dependencias nuevas.

## Inventarios oficiales utilizados

1. [PGOU y planeamiento de desarrollo](https://transparencia.estepa.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-planeamiento-de-desarrollo/).
   Publica bloques del Plan Especial de Protección del Conjunto Histórico de Estepa (PEPCH), con documentación de aprobación definitiva e inicial, y del PGOU. La primera modificación aparece entre los documentos del PGOU y se separa como instrumento propio. El bloque inicial del PEPCH menciona el Decreto de Alcaldía 1208/22 de 23 de junio: se conserva literalmente, sin completar una fecha por inferencia. No se detectó paginación en esta ficha.
2. [Modificaciones del PGOU y planes parciales](https://transparencia.estepa.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00045/).
   Incluye las modificaciones 13, 15, 16, 18 y 19, con memorias, estudios ambientales, resúmenes y documentos de tramitación. También replica planos y normas del PGOU. La tabla `galleryfiles-1-1` tiene dos páginas (10 y 3 enlaces PDF respectivamente). El scraper descubre y sigue todos los enlaces `pagegalleryfiles-*`, normaliza la página 1 y rechaza parámetros desconocidos. No usa un límite para devolver un resultado parcial: exceder la cota de seguridad produce error. La tabla vacía `galleryfiles-1-4` no contiene documentos.

También se localizó la [página municipal del nuevo PGOM](https://www.estepa.es/es/ayuntamiento/areas/urbanismo-y-servicios/plan-general-de-ordenacion-municipal/). No está incluida en la extracción: este adaptador cubre los dos inventarios documentales anteriores, no toda la planificación municipal. Tampoco recorre noticias, boletines, contratación ni actas. El resultado no es un inventario exhaustivo de obras o expedientes del municipio.

## Unidad de registro y procedencia

Resultado observado: **8 instrumentos**, con **90 URL PDF distintas**: PEPCH, PGOU y modificaciones 1, 13, 15, 16, 18 y 19. No se genera un registro por plano, por capítulo ni por versión. El PEPCH inicial y definitivo se agrupa; las dos galerías de la modificación 13 también se agrupan. Los identificadores dependen del instrumento, no del orden de presentación o de la página.

Cada registro conserva `documentos` con título del fichero, URL PDF, inventario de procedencia, sección, galería, descripción, narrativa de sección y fecha documental cuando existe. Se conservan observaciones distintas del mismo enlace: una URL puede tener descripciones o fechas diferentes, o aparecer en varias páginas. Por ello el número de observaciones documentales supera el de URL distintas. Las asociaciones son las publicadas por las galerías; no se ha comprobado el contenido de cada PDF. En particular, el portal reutiliza algún enlace de resumen ambiental entre galerías: no se corrige ni reasigna su contenido por suposición.

La consulta previa de la Ordenanza del Registro de Solares y Edificaciones Ruinosas (`anuncionrsyer.pdf`) se excluye. No es un instrumento de planeamiento ni una licencia otorgada. No se extraen formularios ni anuncios de contratación como proyectos.

Las descripciones publicadas de la modificación 15 distinguen aprobación inicial y definitiva. Se conservan literalmente, sin convertir la fecha del CMS en fecha de acuerdo. `documentos[].fecha_publicacion` procede exclusivamente de `time[datetime]` del CMS y tiene su advertencia de procedencia. Las fechas del registro quedan nulas porque un instrumento reúne documentos de varias etapas. No se infiere vigencia jurídica ni una fase única a partir del título genérico del inventario («aprobadas»), que también incluye documentos iniciales.

No hay coordenadas ni geometría verificadas; `geometry_status: unavailable` y `publication_ready: false`. El manifest desactiva programación, jitter y licencias. No se ha verificado un registro público de licencias concedidas.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_estepa -v`, **6 correctas**. Cubren agrupación de versiones, aislamiento entre instrumentos, exclusión de ordenanzas, semántica de fechas, rechazo de fuentes vacías/cambiadas, parámetros inesperados y recorrido completo de páginas con un documento exclusivo de la última página. Las pruebas contienen HTML sintético; la extracción real utiliza el portal vivo.

Se ejecutó directamente `EstepaAyuntamientoAdapter('estepa', config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La actualización realiza la misma instantánea completa; no elimina páginas por un cursor temporal. No se usan bases de datos ni publicación.

Evidencia local, fuera de los cuatro archivos de código/documentación:

- `evidence/proyectos.jsonl`: ocho registros reales.
- `evidence/validation.json`: recuento, URLs de las tres páginas consultadas, limitaciones, fecha UTC, hashes de capturas y comprobaciones documentales.
- `evidence/source-*.html`: cuerpos HTML capturados por el propio adaptador durante la extracción.
- Capturas exploratorias `inventory.html`, `modificaciones.html` y `modificaciones-page2.html`.
- `evidence/*-pdf-prefix.bin`: primeros 1024 bytes de tres documentos (modificaciones 1, 15 y 19). Los tres respondieron HTTP 200, `application/pdf` y firma `%PDF-`. No se descargaron íntegramente ni se verificaron todos los documentos.

Un fallo HTTP, una redirección inesperada, un inventario sin documentos, un documento no clasificable o una paginación desconocida aborta la extracción antes de escribir el JSONL. El adaptador no devuelve un placeholder ante la pérdida de la fuente.
