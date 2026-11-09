# Bunyola — INE 07010, Illes Balears

Verificación y extracción en vivo: 2026-11-08, con el Python preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

La web del Ayuntamiento identifica Bunyola, dirección sa Plaça 4, 07110, Illes
Balears, y enlaza expresamente su sede electrónica. Desde «Normativa: Informació
jurídica», https://ajbunyola.net/en/node/4443, se descubrieron:

- «Normativa urbanística»: https://bunyola.sedelectronica.es/transparency/528cc9cb-49b8-4d43-88bb-01277f60bbc5/
- «Consulta aquí els projectes en tramitació»: https://bunyola.sedelectronica.es/transparency/76a259ac-8942-48d2-9fa9-c642e2d131b1/

La primera fuente se identifica como «7. URBANISME, OBRES PÚBLIQUES I MEDI
AMBIENT / 7.1. NORMATIVA URBANÍSTICA VIGENT / Nucli de Bunyola». Es el inventario
implementado, no una noticia ni un anuncio contractual. Se conservan las URLs
estables de las carpetas y los enlaces públicos `preview-document/<uuid>`.
La segunda fuente contiene reglamentos administrativos y algunos planes sectoriales
(catálogo de caminos, ordenación de montes); se inspeccionó durante el descubrimiento,
pero queda fuera del alcance del adaptador. No se convierten los reglamentos en obras.

## Cobertura y agrupación

Resultado real: **7 registros, 26 enlaces documentales**, a partir de 17 entradas
principales y cinco carpetas. Se recoge la documentación del PGOU del núcleo,
las modificaciones UA-1 (2/2014), PGOU de 1996, supresión de calles (1985), Can Gual,
y los estudios de detalle Can Far (1994) y Cas Metge Toni (1992).

La colección general del PGOU agrupa 11 documentos: normas, planos y cuadros
sueltos del inventario y la carpeta «PGOU de 1982 i modificacions publicades al BOIB».
Esta recopilación no genera un instrumento adicional. Los anexos sueltos sin una
asociación expresa a otra carpeta se conservan en esta colección del PGOU;
no se afirma que constituyan un texto consolidado o una nueva modificación.
Las restantes carpetas agrupan sus documentos escritos, gráficos y anuncios;
no se cuentan memoria, plano, aprobación inicial y definitiva como cuatro proyectos.
Las modificaciones publicadas como un único documento conservan su propio enlace.

La etiqueta «vigent» corresponde al inventario municipal, sin nueva verificación
jurídica de cada documento. El título «aprovada definitivament» de Can Gual se
retiene literalmente, sin inventar fecha ni extrapolar ese estado a otras filas.
No se extraen fechas del reloj de la sede, años de títulos, números de modificación
ni del nombre de un PDF. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son
nulas. Los enlaces son de consulta oficial; no se pretende haber analizado el texto
íntegro de los 26 documentos ni certificar la vigencia jurídica de sus determinaciones.

Cobertura municipal **parcial**: únicamente Nucli de Bunyola, sin garantía sobre
Palmanyola, Sa Coma, otras urbanizaciones, histórico, nuevas obras, ni proyectos
en tramitación. No hay registro verificado de licencias concedidas; formularios,
anuncios contractuales y noticias no se convierten en licencias o proyectos.
`licencias.enabled=false`; los métodos correspondientes escriben cero filas.

## Paginación y controles

La página inicial ofrece diez entradas. El botón «Veure’n més» usa un callback
público Wicket: se solicita en la misma sesión, se leen todos los componentes XML
y se continúa hasta desaparecer el botón (siete entradas adicionales en vivo).
Cada carpeta se resuelve mediante la cabecera `Ajax-Location` a su UUID estable;
se recorre también su paginación y se verifica el número anunciado de documentos.
Un callback de sesión nunca se utiliza como identidad del instrumento.

El adaptador falla antes de escribir si encuentra recuentos inconsistentes,
paginación repetida, enlaces desconocidos, carpetas anidadas no cubiertas,
respuestas inesperadas o supera 100 páginas. No devuelve las primeras diez filas
como inventario completo. La actualización vuelve a leer la instantánea completa;
no usa estado incremental ni afirma cubrir entradas retiradas.

## Geometría y validación

geometry_status: unavailable

La web municipal enlaza la guía urbana https://sitmun.idelma.cat/guia_bunyola.
No se ha verificado una geometría vectorial asociada por identificador a estos
instrumentos. Los planos documentales no se convierten en coordenadas.
`geometry=null`, `publication_ready=false`, `geocode.jitter_missing=false`.
`schedule.enabled=false`.

Siete pruebas con `python -m unittest municipio.test_bunyola -v`: estructura de
carpetas, componentes XML, recorrido de páginas, rechazo de repetición y paginación
no soportada, recuento de documentos, procedencia, fechas nulas, manifiesto y
licencias deshabilitadas. Extracción real mediante
`BunyolaAyuntamientoAdapter('bunyola', {'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local en `evidence/`: `proyectos.jsonl`, `validation.json`, capturas HTML
y XML numeradas de las solicitudes del adaptador y capturas de descubrimiento.
`validation.json` incluye `live_records`, `source_urls`, limitaciones y archivos de
captura. La evidencia no forma parte de los cuatro archivos fuente entregados.
