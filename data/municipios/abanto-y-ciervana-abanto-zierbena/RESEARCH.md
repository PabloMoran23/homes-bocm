# Abanto y Ciérvana-Abanto Zierbena — INE 48002, Bizkaia

Comprobación en vivo: 2026-11-07. Adaptador único municipal, sin publicación.

## Descubrimiento y fuentes oficiales

Desde https://www.abanto-zierbena.eus se accede a Urbanismo, vivienda y medio
ambiente:
https://www.abanto-zierbena.eus/es-ES/soy-abanto-zierbena/Urbanismo-vivienda/Paginas/default.aspx

Inventario utilizado (HTTP 200):
https://www.abanto-zierbena.eus/es-ES/soy-abanto-zierbena/Urbanismo-vivienda/Paginas/Planificacionurbanistica.aspx

Inventario adicional examinado, fuera del alcance implementado:
https://www.abanto-zierbena.eus/es-ES/soy-abanto-zierbena/Urbanismo-vivienda/Paginas/Gestionurbanistica.aspx
Ofrece proyectos de urbanización/reparcelación, programas y convenios. No se mezcla
con Planificación para evitar duplicar instrumentos y trámites relacionados.
Área de urbanismo contiene solicitudes y convocatorias de ayudas, no licencias
concedidas. No se extrae ninguna licencia.

También se descubrió el conjunto de la Diputación «Planeamiento urbanístico -
Abanto y Ciérvana-Abanto Zierbena» en Open Data Bizkaia. Su acceso directo sin www
falló por certificado TLS; no se desactivó la verificación ni se usaron sus datos.
La fuente operativa es exclusivamente municipal.

## Cobertura y semántica

El inventario de Planificación contiene 16 entradas: se recorren las 13 páginas
individuales de instrumentos; se excluye el reglamento del consejo asesor y dos
índices agregados: PGOU (dos ramas de documentación) y PERIS (varios planes
distintos). Las tres exclusiones, con sus URLs, figuran en validation.json.
No se afirma cobertura completa de todo el planeamiento municipal.

Resultado real: **13 instrumentos, 118 enlaces documentales**, incluido el estudio
T-1.2 de Abra Industrial, el plan especial UE-SF-16 Sanfuentes, la modificación del
PERI Cotarro, El Campillo 1, Santa Bárbara, PAU UE-LC-04, reparcelación SUAE LC 01,
plan parcial Parque Tecnológico y los estudios Doctor Areilza, Gallarta, San Miguel,
El Casal y Serantes. Un instrumento conserva todos sus documentos iniciales y
finales: no se cuentan memoria, planos y anuncios como proyectos independientes.
En particular, Parque Tecnológico tiene 49 documentos bajo un único registro.

El detalle de San Miguel describe el acuerdo definitivo de 25/03/2021, pero no
expone enlaces documentales: se conserva como instrumento real con documentos=[]
y documentos_status=not_exposed. Los demás enlaces se conservan como publicados,
sin afirmar haber descargado o interpretado sus PDFs. No se resuelven condiciones
de eficacia del acuerdo ni se afirma vigencia actual por aparecer en el índice.

fecha_acuerdo y fecha_aprob proceden exclusivamente de párrafos con una fecha
completa y una aprobación explícita (o sección inicial/definitiva inequívoca).
Se conserva el texto de cada acuerdo. Ejemplos: T-1.2, 27/11/2025; UE-SF-16,
24/04/2025; Cotarro, 29/05/2024. No se sustituyen por fechas de archivos adjuntos.
Párrafos con varias fechas quedan sin fecha estructurada, reteniendo la narración
original. fecha_publicacion y fecha genérica permanecen nulas; no se infiere la
publicación del acuerdo, del nombre de archivo o de la fecha de consulta.

IDs estables derivados de la URL canónica municipal, no del orden del inventario.
Cada documento guarda título, URL y página de procedencia. Los detalles admiten
las dos plantillas SharePoint observadas. Una entrada desconocida, HTML ausente,
un detalle sin documentos ni acuerdo explícito o una paginación detectada provocan
error antes de sustituir la salida. El inventario observado no tiene paginación:
no hay límite de filas ni recorte. Si aparece paginación, debe implementarse antes
de aceptar nuevas extracciones. update refresca la instantánea completa del mismo
alcance, sin watermark de fechas ni escritura de estado externo.

## Geometría y clasificación compartida

geometry_status: unavailable. No se ha verificado una geometría vectorial vinculada
a estos instrumentos. Los planos PDF no se convierten en coordenadas. lat, lon y
geometry nulos; geocode.jitter_missing=false; publication_ready=false.

La carga mediante el registro compartido añade _entity_policy. En esta extracción
los 13 registros quedan pendientes por insufficient_identity_evidence y el informe
compartido marca adapter_incident/unknown_entity_spike: el clasificador exige una
referencia oficial de expediente para reconocer estas páginas municipales como
actividad. Los instrumentos y sus documentos sí están identificados por fuente,
pero no se inventan números de expediente ni se modifica la política compartida.
Esto limita su uso posterior como actividad y requiere revisión independiente.

## Validación reproducible y evidencias locales

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_abanto_y_ciervana_abanto_zierbena -v`:
5 pruebas pasan (descubrimiento y exclusiones, deduplicación, paginación/cambios de
HTML, documentos agrupados, fases/fechas, narraciones ambiguas, carga del manifest,
licencias deshabilitadas y refresco completo).

Extracción real mediante load_manifest y load_portal_adapter,
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir']='evidence/captures'` para guardar HTML.
Resultado en evidence/proyectos.jsonl; evidence/validation.json contiene
live_records=13, source_urls, exclusiones, limitaciones e informe de clasificación.
Las capturas HTML se nombran con los primeros 16 caracteres SHA-256 de su URL;
validation.json contiene el mapa correspondiente. Se conservan además capturas
de descubrimiento. Todo evidence/ es local, no se incorpora como fuente.

schedule.enabled=false y licencias.enabled=false. Sin cambios compartidos,
dependencias nuevas, base de datos, despliegue o publicación.
