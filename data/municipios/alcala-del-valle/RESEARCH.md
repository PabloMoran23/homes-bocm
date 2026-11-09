# Alcalá del Valle — Cádiz — INE 11002

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.alcala_del_valle:AlcalaDelValleAyuntamientoAdapter`.

## Fuentes oficiales y alcance

El [portal del Ayuntamiento](https://www.alcaladelvalle.es/) enlaza el
[índice municipal de artículos](https://www.alcaladelvalle.es/noticias).
Es un inventario Joomla accesible sin sesión. La ejecución recorrió **22 páginas**,
con inicio en `/noticias` y final en `/noticias?start=210`, siguiendo `a.next`.
Se verifica el contador «Página X de Y», la secuencia, la estabilidad del total y
la ausencia de ciclos. Una página intermedia sin enlace siguiente, un cambio de
estructura o un inventario sin instrumentos causa error, sin sustituir la salida
anterior. No hay límite que recorte silenciosamente la paginación.

Se seleccionan títulos de modificaciones puntuales del PGOU o del planeamiento
urbanístico y se requiere documentación PDF municipal en su ficha. No se convierte
el índice ni una noticia genérica en un proyecto. Se excluyen formularios,
contratación y noticias ajenas. La selección es deliberadamente parcial: no cubre
instrumentos mencionados únicamente en artículos de título genérico, ni todos los
proyectos u obras del municipio. Los títulos nuevos que no cumplan la selección
necesitan revisión del alcance.

Resultado comprobado: **2 instrumentos, 3 documentos**:

1. [Innovación por modificación puntual del suelo no urbanizable del PGOU](https://www.alcaladelvalle.es/noiticias/199-innovación-por-modificación-puntual-del-suelo-no-urbanizable-del-pgou-de-alcalá-del-valle).
   Publicación documental para recabar opiniones ciudadanas. Conserva juntos el
   [borrador](https://www.alcaladelvalle.es/images/Documentacion/DOCUMENTO_BORRADOR_INNOVACION_SNU_F-comprimido.pdf)
   y el [documento inicial estratégico](https://www.alcaladelvalle.es/images/Documentacion/DIE_INNO_SNU_ALCALA_DEL_VALLE_F.pdf).
   El borrador incorpora registro/sello de diciembre de 2021; ello no acredita
   aprobación ni fecha de publicación del artículo. Se guarda un registro por
   instrumento, con enlaces y procedencia por documento.
2. [Consulta previa para la modificación puntual en suelo rústico](https://www.alcaladelvalle.es/noiticias/218-apertura-de-consulta-pública-previa-para-la-modificación-puntual-en-suelo-rústico-del-planeamiento-urbanístico-de-alcalá-del-valle).
   Instrumento concreto sobre edificabilidad máxima de actividades agropecuarias,
   respaldado por el [anuncio firmado](https://www.alcaladelvalle.es/images/Documentacion/ANUNCIO_APERTURA_CONSULTA_PBLICA_FIRMADO.pdf).
   La lectura local del PDF confirma que reproduce la Resolución 141/2022 de
   apertura de consulta de 18 de octubre de 2022; el anuncio está fechado el 26
   de octubre. Ninguna de esas fechas se convierte en aprobación urbanística ni
   en fecha de publicación web. El scraper conserva el enlace y no analiza fechas
   del PDF ni mantiene valores precargados de expedientes.

Se descargaron íntegramente los tres PDF: HTTP 200, `application/pdf`, firma
`%PDF-`. Se conservan capturas y hashes SHA-256 en la evidencia. Los documentos
se agrupan dentro de cada ficha, deduplicando enlaces repetidos; los dos
instrumentos son distintos. No se realiza conciliación general de expedientes
entre boletines, sede y noticias de diferente título.

## Otras fuentes descubiertas y límites

El Ayuntamiento enlaza directamente el
[PBOM provincial](https://www.dipucadiz.es/asistencia-a-municipios/asistencia-tecnica/planeamiento-urbanistico/ayuntamientos/alcala-del-valle/pbom/).
La [página provincial del municipio](https://dipucadiz.es/asistencia-a-municipios/asistencia-tecnica/planeamiento-urbanistico/ayuntamientos/alcala-del-valle/)
describe el planeamiento vigente y la asistencia al nuevo plan. El PBOM indica
actos preparatorios: los documentos de diagnóstico, avance y documento inicial
estratégico están pendientes; las fases de aprobación inicial y definitiva
figuran como no iniciadas. Incluye explicaciones generales de todas las fases,
que no son hitos alcanzados. El aviso legal provincial además remite al
Ayuntamiento para obtener documentación oficial. Se captura la página como
contexto, sin generar un registro documental sintético del PBOM.

La sede enlazada por el Ayuntamiento es
https://sede.alcaladelvalle.es/opencms/opencms/sede . No se ha verificado un registro
público de licencias concedidas: `licencias.enabled=false`. Los listados de
licitaciones y pliegos no se utilizan como actuaciones ejecutadas ni licencias.
La investigación localizó asimismo referencias BOJA al PGOU de 2008 y a una
aprobación inicial de 2024; no se integran boletines ni se deduce el estado vigente
de los instrumentos desde los antiguos artículos municipales.

Todos los registros son un inventario documental parcial, con
`publication_ready=false` y `geometry_status=unavailable`. Sin coordenadas ni
fechas normalizadas de publicación, acuerdo o aprobación, ni fase actual inferida.
No se confunden sellos registrales, anuncios de consulta y acuerdos urbanísticos.
`schedule.enabled=false` y `geocode.jitter_missing=false`.

## Verificación reproducible

Runtime requerido:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_alcala_del_valle -v
```

**8 pruebas correctas**: documentos agrupados, procedencia, ausencia de metadatos
inventados, exclusiones, estructura ausente, enlaces externos, paginación
incompleta/cíclica, conservación de la salida ante errores, URLs con tildes,
manifest y licencias desactivadas.

Extracción real con `load_manifest('alcala-del-valle')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Configurar opcionalmente `manifest.portal.config['capture_dir']` antes de cargar el
adaptador guarda las páginas HTML consultadas. El método incremental repite la
instantánea completa: no existe una marca temporal fiable para estos artículos.

Evidencia local, fuera de los cuatro archivos fuente:

- `evidence/proyectos.jsonl`: 2 registros reales, pasando por el cargador del registro.
- `evidence/validation.json`: recuento vivo, 24 URLs consultadas (22 índices y 2
  fichas), limitaciones, política de entidades y comprobaciones reales de los PDF.
- `evidence/live-captures/`: HTML capturado por el propio adaptador.
- `evidence/live-document-*.pdf`: documentos completos comprobados.
- `evidence/pbom.html`, `evidence/discovery-*.html` y otras capturas de investigación.

Sin cambios compartidos, dependencias, base de datos, geocodificación o publicación.
