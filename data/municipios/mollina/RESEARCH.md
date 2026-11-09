# Mollina — Málaga — INE 29072

Comprobación en vivo: 2026-11-09. Adaptador de cobertura deliberadamente parcial:
un único instrumento real, el **Plan Básico de Ordenación Municipal de Mollina
(PBOM)**, actualmente en **FASE 1. PARTICIPACIÓN CIUDADANA** según su ficha
específica. No se presenta como plan aprobado, licencia concedida ni obra ejecutada.

## Fuentes oficiales e inventarios comprobados

- https://www.mollina.es/ — HTTP 202, respuesta de protección sin inventario
  municipal extraíble. Captura local `evidence/mollina.html`. No se intenta eludir
  la protección ni acceder a sesiones autenticadas.
- https://www.idemap.es/ — HTTP 200, Geoportal de la Diputación de Málaga.
  Su JavaScript público `js/funciones.js` enlaza `/pbom/`; se conserva esa
  procedencia en `evidence/funciones.js`. No se usa la noticia como proyecto.
- https://www.idemap.es/pbom/ — HTTP 200, catálogo público de PBOM. El script
  `js/index.js` documenta la consulta pública paginada de municipios y la ruta de
  sus fichas. Los formularios de acceso de la cabecera no impiden la lectura
  anónima de estas fichas; no se usan credenciales.
- https://www.idemap.es/pbom/php/api/municipios_obtener.php?page=1&search=Mollina
  — HTTP 200; `total=1`, `page=1`, `limit=5`, municipio `cod_mun=29072`,
  `nombre=MOLLINA`. Es el endpoint HTTP público que usa el catálogo, no una
  conexión directa a una base de datos. Se recorren todas las páginas declaradas,
  verificando tamaño, total constante e identidad exacta, sin truncar resultados.
- https://www.idemap.es/pbom/php/municipio/municipio.php?cod_mun=29072
  — HTTP 200. Ficha municipal con narrativa de elaboración, fase actual explícita
  y cinco PDF de participación. El contexto menciona NNSS de 1999 y adaptación
  parcial de 2009; esos años no se convierten en fechas del nuevo PBOM ni en otros
  registros extraídos. Las fases futuras explicadas en las preguntas frecuentes
  tampoco son acuerdos administrativos del municipio.
- https://www.idemap.es/pbom/php/documentos/documentos.php?cod_mun=29072
  — HTTP 200. Inventario técnico con cuatro pestañas, todas vacías: avance y
  documento inicial estratégico; aprobación inicial y evaluación ambiental;
  documento final; aprobación definitiva. Se inspeccionan también las pestañas
  ocultas en el HTML, sin confundir sus títulos con el estado actual del PBOM.
  `js/documentos/documentos.js` solo controla interfaz, sin carga paginada oculta.

## Unidad documental y enlaces

Los cinco PDF de la ficha se agrupan dentro del mismo PBOM. Tríptico, guía,
plan de participación y dos encuestas **no** son cinco proyectos ni licencias.
Sus títulos, enlaces originales absolutos y página de procedencia se conservan
en `documentos`. Se respeta `<base href="/pbom/">` al resolver las rutas:

- [Tríptico informativo](https://www.idemap.es/pbom/docs/29072/participacion/archivo_6a66ff55bcc657.94094878.pdf)
- [Guía de participación PBOM](https://www.idemap.es/pbom/docs/29072/participacion/archivo_6a67029d673206.93633318.pdf)
- [Plan de participación PBOM](https://www.idemap.es/pbom/docs/29072/participacion/archivo_6a68a2b0881313.06731238.pdf)
- [Encuesta infantil](https://www.idemap.es/pbom/docs/29072/participacion/archivo_6a6702ecbb4425.67922108.pdf)
- [Encuesta de participación](https://www.idemap.es/pbom/docs/29072/participacion/archivo_6a6703053f9e82.58186584.pdf)

Los cinco enlaces devolvieron HTTP 200 y `application/pdf`. Copias locales:
`evidence/participacion-1.pdf` a `participacion-5.pdf`. Se comprobó el texto del
plan de participación con `pdftotext` (`evidence/plan-participacion.txt`): describe
las acciones de comunicación y participación para elaborar el PBOM. La evidencia
del instrumento es la ficha municipal con su narrativa y estado concreto,
respaldada por esa documentación, no un formulario aislado.

## Semántica, alcance y límites

La identidad estable `mollina-pbom-29072` identifica la ficha única del PBOM, no
un número de expediente inventado. `source=ayuntamiento` responde al contrato de
la fuente del adaptador; `source_organismo` identifica al publicador real,
Diputación Provincial de Málaga — IDEMAP. No se afirma alojamiento municipal.

No constan fechas verificables de publicación, acuerdo o aprobación del PBOM en
estas páginas. Los cuatro campos de fecha quedan nulos; el copyright y la fecha
de consulta no se usan como fechas administrativas. No hay geometría de proyecto
verificada: latitud, longitud y geometría quedan nulas, `publication_ready=false`.
No se sustituye por el centroide municipal ni se añade jitter.

No se cubren todos los proyectos municipales, licencias, obras, instrumentos
históricos ni el planeamiento vigente completo. No se ha verificado un registro
público de licencias concedidas: `licencias.enabled=false`. La programación y el
jitter también están desactivados. Las actualizaciones refrescan la ficha completa
con la misma identidad y sus documentos; no simulan un historial de eventos.

El parser exige identidad municipal, narrativa de elaboración, fase actual,
plan de participación y un inventario técnico completo. Si cambian esos elementos,
aparece paginación HTML o falla una petición, lanza error antes de escribir la
salida; no convierte una página de acceso o de navegación en un registro.

## Validación reproducible y evidencia local

Runtime utilizado (sin instalar dependencias):
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_mollina -v`: **9 pruebas satisfactorias**.
  Cubren agrupación y deduplicación documental, resolución de rutas con base,
  pestañas ocultas, fechas y geometría nulas, fase actual frente a ejemplos de
  aprobación, rechazo de contenido incompleto/otro municipio, paginación de varias
  páginas y errores de continuidad, métodos desactivados y contrato del manifest.
- Extracción real: `MollinaAyuntamientoAdapter('mollina',
  {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
  Resultado: **1 registro, 5 documentos**, sin coordenadas ni fechas fabricadas.
- `evidence/validation.json`: recuento `live_records`, URLs consultadas,
  limitaciones y resultado de pruebas. `live-inventory-1.json`,
  `live-mollina.html` y `live-documentos.html` son capturas de las respuestas
  utilizadas por el propio adaptador durante la extracción.

Solo se añaden los cuatro archivos de fuente solicitados. Las capturas y salidas
bajo `evidence/` son artefactos locales para revisión y no se incorporan a commits.
