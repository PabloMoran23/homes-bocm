# La Solana — Ciudad Real — INE 13079

Investigación y extracción real: 7 de noviembre de 2026. Adaptador único:
`municipio.adapters.la_solana:LaSolanaAyuntamientoAdapter`.

## Fuentes oficiales y cobertura

1. https://www.lasolana.es/portal-de-transparencia-instrumentos-de-desarrollo-y-complementarios/
2. https://www.lasolana.es/portal-de-transparencia-plan-general-de-ordenacion-urbana-pgou/

Son inventarios publicados por el Ayuntamiento en su portal de transparencia.
La sección de Obras y Urbanismo también se revisó durante el descubrimiento:
https://www.lasolana.es/departamento/obras-y-urbanismo/ . Sus formularios y
trámites de solicitud no acreditan concesiones y no se extraen como licencias.
La búsqueda inicial también encontró `/plan-de-ordenacion-municipal/`; el
contenido servido actualmente presenta la misma documentación de la fuente 2,
por lo que no se utiliza como inventario adicional ni se duplica el POM.

El contenido actual de los dos inventarios contiene cuatro documentos PDF,
agrupados en tres instrumentos reales:

- Modificación del Catálogo de Bienes y Espacios Protegidos del POM: un documento.
- Segunda modificación puntual de las Ordenanzas Municipales de Edificación:
  texto y plano, agrupados en un solo registro con ambos enlaces.
- Modificación puntual número 2 del POM: un documento. Es un instrumento distinto
  de la segunda modificación de las ordenanzas, pese a compartir numeración.

Se selecciona exclusivamente `.als-post-content`, evitando navegación, noticias
relacionadas y pie de página. No hay paginación en estos dos listados actuales.
No se impone límite de registros. La aparición de controles de paginación provoca
error explícito; también se rechazan contenedores vacíos, documentos desconocidos,
redirecciones inesperadas y planos sin correspondencia inequívoca. Los registros
se escriben después de completar ambas fuentes, mediante reemplazo de fichero.
Las actualizaciones vuelven a leer el inventario completo; no usan un corte temporal.

## Procedencia documental y fechas

Cada registro conserva `inventory_url`, la URL del primer PDF y `documentos` con
título, URL y página de procedencia de cada documento. Los identificadores se
calculan a partir del título del instrumento, sin depender del orden de enlaces.
Las dos páginas muestran **4 de mayo de 2026**: `fecha_publicacion` describe la
publicación de la página del inventario, expresamente indicada mediante
`fecha_publicacion_provenance.scope=pagina_del_inventario`. No equivale a fecha
de publicación del BOP, de acuerdo o de aprobación.

Se descargaron los cuatro PDF completos a `evidence/document-0.pdf` hasta
`document-3.pdf`: todos devolvieron HTTP 200, `application/pdf` y firma `%PDF`.
`document-checks.json` conserva URL, tamaño y resultado de las comprobaciones.
La lectura local con `pdftotext` de los documentos 1 y 3 confirmó su contenido:
el texto de las ordenanzas es el BOP de 25/07/2013, que menciona un acuerdo
provisional de 04/06/2013 y elevación automática a definitivo; el texto del POM
es el BOP de 01/06/2009, que cita aprobación definitiva de 30/09/2008. Estas
fechas documentales no se convierten en metadatos del scraper: éste no interpreta
PDF ni deduce acuerdos a partir del nombre del fichero. La fecha del CMS tampoco
se usa como fase o aprobación. Las transcripciones locales se conservan como
evidencia, no como fuente de registros precargados.

Cobertura parcial: inventarios documentales actuales, sin garantizar todos los
instrumentos históricos, obras públicas, actualidad jurídica o ejecución material.
No se afirma que publicar un documento en 2026 implique aprobarlo en 2026.
Sin coordenadas inventadas, fases inferidas ni registro de licencias concedidas.
`publication_ready=false`, `geometry_status=unavailable`; licencias, programación
y jitter de geocodificación desactivados en el manifest.

## Validación reproducible

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_solana -v` — seis pruebas correctas:
agrupación y procedencia, IDs estables, ausencia de fechas/posiciones inventadas,
rechazo de inventarios vacíos o planos huérfanos, paginación/hosts externos,
conservación del resultado anterior si falla una fuente y carga del manifest.

Ejecución directa real de `backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
**3 registros, 4 documentos**, a partir de ambas páginas descargadas de nuevo.
`evidence/validation.json` contiene `live_records`, `source_urls`, comprobaciones
documentales y limitaciones. Capturas HTML en `evidence/source-0.html` y
`source-1.html`; `source-2.html` es la ruta histórica inspeccionada. Toda la
evidencia permanece local y fuera de los cuatro archivos fuente a entregar.
Sin base de datos, publicación, despliegue ni cambios compartidos.
