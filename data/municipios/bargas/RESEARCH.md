# Bargas (Toledo), INE 45019

Investigación y extracción verificadas el 2026-11-07. Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y alcance

El portal oficial de transparencia enlaza «Información sobre urbanismo y obras»:
https://www.bargas.es/transparencia/urbanismo-y-obras/
Desde allí se descubre el inventario «Anuncios expedientes de planeamiento y PAUs»:
https://www.bargas.es/transparencia/urbanismo-y-obras/anuncios-expedientes-de-planeamiento-y-paus/
Ambas páginas responden HTTP 200. El inventario actual es una página estática con
una sección «UA – Nº 8» y nueve enlaces PDF. No tiene paginación activa.

Se extrae **un proyecto real**, «Proyecto de urbanización UA-8». Seis documentos
son partes técnicas (anexos, dos memorias y tres conjuntos de planos); los otros
tres son anuncio de licitación, pliego y resolución de selección de contratista.
Todos permanecen enlazados dentro de un solo registro, con título, tipo documental
y URL del inventario como procedencia. Los documentos de contratación por sí solos
no generan proyectos, licencias ni fases de aprobación.

Se descargó y examinó la memoria 1:
https://www.bargas.es/wp-content/uploads/2023/11/proyecto-de-urbanizacion-ua-8-memoria-1.pdf
Su portada identifica un proyecto de urbanización **parcial** de la unidad de
actuación nº 8 de Bargas (Toledo), para terminar el proceso de urbanización. Incluye
pavimentación y redes de servicios; identifica promotor privado LANDCOMPANY 2020,
S.L. La revisión técnica indicada es marzo de 2023: no se transforma esa referencia
en fecha de publicación, acuerdo o aprobación. La evidencia contiene PDF y texto
extraído. El proyecto existe por sus documentos técnicos, no por su licitación.
El título del registro conserva el rótulo del inventario municipal.

También se examinó el inventario oficial de normativa:
https://www.bargas.es/transparencia/urbanismo-y-obras/normativa-urbanistica/
Contiene NNSS, modificaciones, normas de PERI y planos. No se incorpora en esta
versión: mezcla documentación general y modificaciones con agrupación ambigua que
requiere investigación propia. La sección de Urbanismo y edificación y la búsqueda
oficial muestran además noticias y otras actuaciones; tampoco se recorren. Una
publicación DOCM de 2026 relativa a UAE-10 apareció en el descubrimiento:
https://docm.jccm.es/docm/verArchivoHtml.do?ruta=2026%2F09%2F18%2Fhtml%2F2026_6428.html&tipo=rutaDocm
No se incluye ni se interpreta como concesión. Esto confirma que el inventario
municipal seleccionado **no representa el histórico completo ni todas las
actuaciones actuales**. El extractor no pretende cubrir DOCM, BOP, sede electrónica,
convenios, normativa ni el archivo paginado de noticias.

## Semántica y mantenimiento

No hay fechas explícitas de publicación o aprobación en las filas del inventario:
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son null. Las carpetas
WordPress de los PDF no sirven como fechas administrativas. No se asigna fase por
la existencia de un pliego o una resolución de selección de contratista.

El identificador depende de la unidad de actuación, no de cada PDF. Las URLs de
cada documento se conservan y se deduplican. Se reconocen dinámicamente las
secciones UA del inventario; cambios de estructura, unidades inconsistentes,
URLs ajenas o paginación provocan error explícito. No hay límite de registros ni
recorte de enlaces. Si desaparece toda la documentación técnica se falla, sin
reemplazar la evidencia por un inventario vacío. `update_proyectos` realiza una
instantánea completa y no modifica el estado incremental.

Se verifica HTTP y firma `%PDF-` de los nueve enlaces antes de escribir resultados;
no se descargan íntegros todos los grandes planos. Los documentos son fuentes,
no instrucciones. Los métodos de licencias producen cero registros y están
deshabilitados. No hay publicación, sincronización ni acceso a servicios privados.

## Geometría

`geometry_status: unavailable`. Hay planos PDF, pero no se ha verificado una capa
vectorial con geometría vinculada al identificador de la actuación. No se han
vectorizado planos ni deducido posiciones de un centroide municipal. `lat`, `lon`
y `geometry` son null; `publication_ready` es false. Sin coordenadas inventadas ni
jitter. Programación automática deshabilitada.

## Validación reproducible

- `python -m unittest municipio.test_bargas -v`: cuatro pruebas con agrupación y
  deduplicación documental, estabilidad del ID, fechas desconocidas, rechazo de
  formularios/contratación aislada, cambios de fuente y paginación, manifest y
  licencias deshabilitadas.
- Extracción real mediante `load_manifest('bargas')`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: un registro y nueve PDF
  verificados. Se ejecuta también la anotación compartida de política de entidades.
- Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/paus-live.html`, `evidence/document-checks.json`, capturas de los índices,
  `evidence/ua8-memoria-1.pdf` y su texto. No se incluyen como fuentes a versionar.
