# Balmaseda — INE 48090, Bizkaia

Verificación directa: 2026-11-08. Adaptador municipal de planeamiento, con
cobertura parcial explícita. No es un registro de licencias concedidas.

## Descubrimiento y fuentes oficiales

La navegación municipal permite llegar desde Urbanismo a Planeamiento urbanístico,
Ordenación estructural y PGOU:

- https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/Paginas/default.aspx
- https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/Paginas/urbanismo-planeamiento-urbanistico.aspx
- https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/Paginas/ordenacion-estructural.aspx
- https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/Paginas/ordenacion-estructural-pgou.aspx

El último enlace es el inventario vivo de fases del PGOU (0, 2, 3, 4, 5 y 6).
La fase 6 enlaza el certificado de aprobación inicial y los índices urbanístico y
ambiental. Estos índices se recorren recursivamente: documentación escrita,
gráfica, PGOU del anexo cartográfico, medio físico, clasificación, calificación y
condicionantes. Son **11 páginas HTML** contando el inventario y **136 enlaces PDF
únicos**, agrupados en **un instrumento real**, no 136 proyectos. La extracción
conserva título, URL y página(s) de procedencia de cada documento. Conserva también
los enlaces de fases anteriores, sin incorporar sus documentos al inventario de
la fase actual. No hay paginación activa observada; los enlaces de continuación
reconocidos provocan error explícito. No se corta el recorrido al alcanzar el límite
de seguridad: se rechaza toda la extracción, sin reemplazar el resultado previo.
Las listas de SharePoint pueden estar en web parts junto al campo de texto; el
parser incluye ambos dentro del cuerpo del artículo y excluye «Ir a lista».

Certificado oficial descargado e inspeccionado con `pdftotext`:
https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/pgou_fase_6/20260630_certificado_pleno_aprob_ini.pdf

Su texto certifica el acuerdo del Pleno ordinario del **30 de junio de 2026**:
aprobación **inicial**, con información pública conjunta del PGOU y del Estudio
Ambiental Estratégico. La fecha del acuerdo no es la fecha de publicación. El
adaptador infiere la fase del título explícito del certificado enlazado y exige
que sea único. No interpreta fechas de nombres de fichero, firmas ni metadatos:
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. La fecha
del acuerdo arriba indicada procede de la revisión manual del certificado, no del
parser. No se afirma aprobación definitiva ni que siga abierto el plazo de alegación.
Los documentos con «suspensión de licencias», incluso borradores, pertenecen al
PGOU y no representan concesiones de licencias.

Otras fuentes oficiales descubiertas, fuera de esta implementación:

- https://www.balmaseda.eus/es-ES/Servicios/Urbanismo/Paginas/ordenacion-pormenorizada.aspx
  enlaza planes especiales, parciales y estudios de detalle; no se rastrean en este
  adaptador. Tampoco se extraen NNSS anteriores ni inventarios de obras físicas.
- https://opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-balmaseda
  ofrece datos globales y calificación urbanística con carácter orientativo. No se
  convierten estadísticas o categorías de suelo en proyectos.
- https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador
  es el registro foral de instrumentos, fuera del alcance municipal elegido.

## Geometría y límites

`geometry_status: unavailable`. Los planos PDF se retienen como documentos; no se
vectorizan ni se asigna el centro del municipio como posición del instrumento.
El visor foral se describe en
https://www.bizkaia.eus/es/tema-detalle/-/edukia/dt/1813 . No se ha verificado una
capa vectorial específica enlazada a este PGOU. Coordenadas y geometría son nulas;
`publication_ready` es falso. No se descargan ni analizan todos los PDF: se
inventarían todos los enlaces que ofrecen las páginas recorridas. El certificado
sí se descargó como comprobación documental independiente.

Un cambio a una fase posterior a la 6, pérdida de estructura, documentos ausentes,
certificado ambiguo, enlaces de contenido externos o paginación detectada requieren
revisión y producen error; no generan registros de sustitución. Los resultados
incrementales son una nueva instantánea completa del mismo instrumento estable.
Licencias y planificación automática están deshabilitadas; no hay jitter geográfico.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_balmaseda -v`: 4 pruebas pasan. Cubren inventario,
cambio de fase, paginación, estructura ausente, enlaces externos, web parts,
normalización de URL, ciclo y deduplicación documental, procedencia, agrupación,
fechas y geometría nulas, fallo sin escribir salida, licencias y manifiesto.

Extracción real ejecutada llamando a
`BalmasedaAyuntamientoAdapter('balmaseda', {'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **1 registro, 136 documentos, 11 páginas oficiales recorridas**.
`evidence/validation.json` contiene conteos, URLs y limitaciones. Los HTML de la
extracción se guardan con nombre SHA-256 abreviado de la URL; también hay capturas
legibles de las páginas de descubrimiento y el certificado PDF/texto. Las evidencias
son locales, no forman parte de los cuatro archivos fuente entregados.
