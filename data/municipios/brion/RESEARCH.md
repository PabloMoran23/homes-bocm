# Brión — INE 15013, A Coruña (Galicia)

Verificación en vivo: 2026-11-08. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y selección

- Inventario municipal utilizado: https://www.concellodebrion.gal/es/urbanismo
  (HTTP 200). La sección «PXOM» identifica expresamente los documentos y gráficos
  del «Plan Xeral Urbanístico de Brión». Contiene cinco textos normativos/de apoyo
  y 21 planos de ordenación; todos los enlaces se extraen dinámicamente.
- Descubrimiento complementario: portal municipal https://www.concellodebrion.gal/
  y su sección de departamentos; la búsqueda oficial de Urbanismo lleva al
  inventario anterior.
- Transparencia municipal, «Plans e Programas»:
  https://sede.concellodebrion.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
  enlaza el PXOM al antiguo inventario autonómico
  `https://www.planeamentourbanistico.xunta.es/siotuga/inventario?idconcello=15013&inv=1`.
  Ese enlace devolvió timeout en la consulta web; no se depende de él ni se
  afirma haber extraído el inventario autonómico completo.

Se selecciona el inventario documental del departamento, no una noticia concreta
ni anuncios de contratación. Los formularios de comunicación previa/licencia y
los anuncios de asesoramiento jurídico urbanístico no prueban ninguna concesión
ni constituyen proyectos. El plan de igualdad del portal de transparencia tampoco
es un instrumento urbanístico. No se extraen esos contenidos.

## Resultado y semántica

**1 instrumento real: Plan Xeral Urbanístico de Brión (PXOM), con 26 documentos.**
La normativa, memoria, estudio económico, catálogo arqueológico y planos se
agrupan bajo `brion-pxom`; no se convierten los planos de aldeas en proyectos
independientes. Cada documento conserva título, URL, página de procedencia y el
texto del elemento de lista, incluidas las localidades cuando existen.

Se conserva la descripción municipal y no se inventan aprobación, fase, fecha de
publicación, fecha de acuerdo ni ejecución. La página no expone esas fechas. Los
números de los archivos y fechas de indexación de buscadores no se interpretan
como fechas administrativas. El inventario está disponible actualmente, pero
esto no certifica la vigencia legal de todas sus determinaciones.

Cobertura **parcial**, limitada al PXOM que publica esta página. No representa la
totalidad del planeamiento de desarrollo, modificaciones, actuaciones de obra
pública ni licencias otorgadas. Licencias deshabilitadas. Sin geometría vectorial
verificada, coordenadas ni geocodificación artificial; los planos PDF se conservan
como documentos. `publication_ready: false`.

## Comportamiento y paginación

Página documental única, sin paginación observada. Se recorren todos los enlaces
de la sección PXOM, sin límite numérico ni corte. Se deduplican URLs sin fragmento.
El parser falla ante paginación (`rel=next`, `.pager`, `.pagination`), sección
PXOM ausente/duplicada, descripción municipal cambiada, pérdida de normativa o
un enlace nuevo fuera del patrón documental revisado. Esto exige revisar cambios
de estructura y evita aceptar silenciosamente un inventario truncado. Nuevos
PDFs bajo el directorio municipal PXOM quedan incorporados al mismo instrumento.

Backfill y update generan una instantánea completa; no hay cursor cronológico
porque la fuente no facilita fechas. El archivo se sustituye después de validar
la respuesta y el parseo, conservando la salida anterior si falla la fuente.

## Validación y evidencias locales

Pruebas ejecutadas: `python -m unittest municipio.test_brion -v`, con el runtime
indicado arriba: **4 pruebas, OK**. Cubren agrupación/deduplicación, procedencia,
exclusión de formularios/noticias ajenas a PXOM, ausencia de datos inferidos,
fallos ante pérdida de contenido/paginación/enlaces desconocidos, conservación de
salida ante error, licencias vacías y configuración del manifest.

Extracción real mediante `BrionAyuntamientoAdapter.backfill_proyectos`, cargando
el manifest con `load_manifest('brion')`: **1 registro y 26 documentos**. Los 26
PDFs respondieron HTTP 200 con firma `%PDF-` (lectura de los primeros 1024 bytes,
no análisis íntegro de su contenido). Timeout 45 segundos, cuatro conexiones
como máximo en la comprobación auxiliar de documentos.

Evidencias en `evidence/` (locales, no se incorporan al código):

- `urbanismo.html`: captura obtenida por el propio adaptador en la extracción real.
- `proyectos.jsonl`: instrumento extraído con todos los enlaces documentales.
- `document_checks.json`: URLs solicitadas/finales, HTTP, MIME y firma PDF.
- `validation.json`: recuento real, URLs fuente, pruebas y limitaciones.

La captura se puede repetir instanciando el adaptador con
`config={'capture_dir': 'evidence'}` y llamando a
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
No requiere dependencias adicionales ni cambios en fuentes compartidas.
`schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Sin publicación ni servicios de producción.
