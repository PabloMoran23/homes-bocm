# Villares de la Reina — INE 37362, Salamanca

Comprobado en vivo el 9 de noviembre de 2026. Adaptador limitado al inventario
oficial de obras que sigue publicado en la web municipal. No representa el estado
actual verificado de las obras ni un registro completo del municipio.

## Fuentes e inventarios

- https://villaresdelareina.es/ — HTTP 200. El menú Transparencia enlaza
  «Proyectos» a https://villaresdelareina.es/proyecto/.
- https://villaresdelareina.es/proyecto/ — HTTP 200. Inventario íntegro en una
  página: 5 obras en «Fase de obras», 3 en «Fase de contratación», 2 en «Fase de
  licitación» y 3 en «Fase de redacción». Son actuaciones físicas identificadas
  por nombre en un inventario del Ayuntamiento, no anuncios de contratación
  convertidos en proyectos. Incluye nave multifuncional, vestuarios de piscina,
  rotonda de Aldeaseca, pista de pádel, alumbrado, pavimentación y otras obras.
- https://villaresdelareina.es/wp-json/wp/v2/pages/3367 — HTTP 200. Metadatos
  públicos de la misma página: publicada `2021-02-22T08:26:15`, modificada
  `2021-10-28T13:04:47` (campos locales de WordPress, sin zona declarada).
  Son fechas de la página, **no** fechas de publicación, acuerdo o aprobación
  de las obras. La frase «En estos momentos» no acredita vigencia en 2026.
- https://villaresdelareina.es/ayuntamiento/500-2/ — HTTP 404; destino del
  acceso «Planeamiento Urbanístico» de la portada. No produce registros.
  Este adaptador no cubre las NUM ni modificaciones del archivo autonómico.
- https://villaresdelareina.sedelectronica.es/info.0 — HTTP 200. Catálogo de
  trámites, incluidas declaraciones responsables y solicitudes; no se ha
  verificado un registro público de licencias concedidas. No se extraen como
  concesiones los formularios, comunicaciones o anuncios del tablón.

## Semántica y alcance

Se conserva el texto completo de cada entrada y su encabezado de fase. Las fases
son afirmaciones de la fuente de 2021, no comprobaciones de ejecución actuales.
La entrada que contiene «Aprobación del proyecto» conserva ese texto, pero no
recibe una fecha ni una fase de aprobación inventada. Las fechas individuales
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.
No se inventan números de expediente ni promotores.

La página no contiene enlaces a documentos de cada obra ni geometría. El parser
conserva enlaces dentro de una entrada en `documentos`, sin generar registros
por cada documento. Duplicados con el mismo título se agrupan; fases
contradictorias se rechazan. Las dos entradas de piscina describen obras
distintas (vestuarios/administración y vasos/cafetería), no documentos duplicados
de un instrumento acreditado. Identidad local por hash del título normalizado,
independiente de la fase; cambiar el título puede cambiar esa identidad.

No hay paginación en el inventario observado. Se recorren todas sus listas sin
límite de filas y se rechazan cambios de fase, listas incompletas o indicadores
de paginación para evitar truncamiento silencioso. Actualizar refresca toda la
instantánea. Las respuestas HTTP se limitan a 2 MB con timeout de 30 segundos;
fallos HTTP, redirecciones a otro dominio y metadatos ajenos abortan la ejecución.

Cobertura parcial: se excluyen noticias, archivo histórico, contratación pública
y fuentes autonómicas. No hay coordenadas verificadas: `lat`, `lon`, `geometry`
son nulos y `publication_ready` es falso. La política común del repositorio marca
las 13 filas `pendiente` / `insufficient_identity_evidence` y reporta
`adapter_incident` / `unknown_entity_spike` porque no hay referencias oficiales
individuales. No se elude esa política fabricando expedientes. Las filas son
obras reales del inventario, pendientes de enriquecimiento para ingestión.
Licencias, programación y jitter están desactivados en el manifest.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_villares_de_la_reina -v`: 4 pruebas correctas,
con fases, fechas nulas, enlaces agrupados, identidad estable, rechazo de cambios
de estructura/paginación, metadatos y carga del adaptador mediante el manifest.

Extracción real con `load_portal_adapter(load_manifest('villares-de-la-reina'))`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 13 registros únicos,
5/3/2/3 por fase, INE 37362, sin coordenadas ni fechas de aprobación fabricadas.
La anotación de la política común queda conservada en la evidencia.

`evidence/validation.json` contiene recuentos, URLs, limitaciones y resultado de
la política; `projects-live.html` y `projects-metadata.json` capturan las respuestas
usadas por el adaptador. `home.html`, `planning.html` y `sede.html` documentan el
descubrimiento. La evidencia es local y no forma parte de los cuatro archivos
fuente entregables.
