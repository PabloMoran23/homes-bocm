# A Laracha — INE 15041, A Coruña, Galicia

Verificación en vivo: 2026-11-07. Un adaptador municipal; cobertura documental
parcial, sin licencias, publicación ni acceso a sistemas de producción.

## Fuentes y descubrimiento

Entrada oficial: https://www.alaracha.gal/gl/pagina/177/urbanismo/
Su navegación de Urbanismo identifica estos dos inventarios de planeamiento:

- https://www.alaracha.gal/gl/pagina/195/plan-xeral/
- https://www.alaracha.gal/gl/pagina/200/equipamentos-educativos/

El extractor descubre esas URLs por sus etiquetas en la página municipal en cada
ejecución. Recorre todos los enlaces de contenido de cada instrumento, incluyendo
subapartados, sin seleccionar una noticia o fijar un documento como registro.
Se limita al bloque de contenido `h3.kopa-title` dentro de `.row`; no mezcla
formularios, enlaces laterales, redes sociales o contratación con proyectos.

El PXOM enlaza cuatro apartados: estrutura xeral (194), núcleos rurais (193),
núcleos urbanos (192) y normativa (191). El plan especial enlaza anexos (199),
información (198), ordenación (197) y publicacións oficiais (196). Los once HTML
(entrada, dos instrumentos, ocho apartados) respondieron HTTP 200 y se capturaron.
No existe paginación en los inventarios revisados. Se recorren todos los enlaces;
si aparece paginación se falla explícitamente, sin escribir un resultado parcial.
También se rechazan secciones esperadas ausentes, contenido vacío, enlaces de
contenido no reconocidos y cambios de dominio/redirección. El límite de seguridad
de 100 páginas produce error, nunca un corte silencioso.

## Registros y semántica

Extracción real mediante el adaptador resuelto desde el manifest:

- **Plan Xeral: 1 instrumento, 296 URLs PDF distintas**.
- **Plan Especial Equipamentos Educativos: 1 instrumento, 26 URLs PDF distintas**.

Total: **2 registros, 322 documentos enlazados**. Cada documento conserva título,
URL y referencias a su sección/página de procedencia. Se agrupan los documentos
por instrumento y se deduplican URLs, conservando etiquetas diferentes. No se
interpretan mapas de núcleos como proyectos de obra independientes.

Se preservan anomalías del inventario municipal: «ESTRUTURA XERAL 5» y «6»
apuntan ambos a `Estrutura_Xeral_6.pdf`; la lista rural repite NR-O-19 y NR-O/P-60
y no enlaza NR-O-20. No se reconstruyen enlaces supuestos ni documentos ausentes.

Los HTML no declaran fechas de publicación, acuerdo o aprobación de estos
instrumentos. Todos esos campos, la fecha genérica y la fase quedan nulos.
Urbanismo menciona el PXOM desde 2003; no se convierte ese año en una fecha diaria.
El plan especial incluye un enlace rotulado «ANUNCIO BOP APROBACIÓN INICIAL»:
es procedencia documental, no prueba de aprobación definitiva ni de vigencia.
El adaptador no extrae texto de PDF ni deduce fechas de nombres de archivo,
cabeceras HTTP o fecha de consulta. No se afirma que este conjunto sea la versión
consolidada vigente. Dos muestras PDF (índice normativo PXOM y anuncio BOP del
plan especial) se descargaron con HTTP 200 y firma PDF válida; no se comprueba en
esta ejecución la disponibilidad individual de los otros 320 enlaces.

No hay cobertura exhaustiva de modificaciones del PXOM, registro autonómico,
obras, acuerdos plenarios ni histórico de noticias. La navegación también ofrece
Inventario de Camiños Públicos y Plan de Mobilidade Sostible; este último tiene
un PDF municipal, pero ambos quedan fuera de los dos inventarios de planeamiento
urbanístico implementados. No se han verificado concesiones de licencias;
formularios y solicitudes se excluyen. Los métodos de licencias devuelven vacío
y estado disabled.

## Geometría y límites de publicación

`geometry_status: unavailable`. Las fuentes recorridas ofrecen planos PDF sin
geometría vectorial enlazada por identificador de instrumento. No se vectorizan
planos, no se toman centroides del municipio y no se inventan coordenadas ni CRS.
`lat`, `lon` y `geometry` son nulos; `publication_ready: false`.
El clasificador compartido anota ambos registros como `pendiente` por ausencia
de identidad de expediente suficiente para sus reglas: se conserva esa anotación
sin inventar números de expediente ni forzar elegibilidad para actividad.

## Validación y reproducción

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_a_laracha -v` — **6 pasan**.
Cubren agrupación, deduplicación con referencias, fechas desconocidas, ausencia
de truncamiento con 350 enlaces, rechazo de paginación/secciones ausentes/enlaces
ajenos, conservación del fichero previo ante fallo y carga del manifest/adapter.

Extracción: `load_manifest('a-laracha')`, `load_portal_adapter(manifest)`,
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Para capturas se usó `manifest.portal.config['evidence_dir']` apuntando al directorio
local `evidence/` antes de resolver el adaptador. `update_proyectos` refresca la
instantánea completa; no afirma disponer de un historial incremental.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, informe de clasificación, HTML y dos muestras PDF.
La validación incluye URLs de fuente, recuento real, limitaciones y muestras.
Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`. No se modifican fuentes compartidas ni dependencias.
