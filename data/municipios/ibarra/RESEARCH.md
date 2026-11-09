# Ibarra (Gipuzkoa), INE 20042

Verificado en vivo el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`,
registro de adaptadores y los ejemplos Hernani y Manlleu.

## Descubrimiento y cobertura

La portada oficial https://www.ibarra.eus/es/ enlaza Servicios municipales →
Urbanismo: https://www.ibarra.eus/es/urbanismo (HTTP 200 por requests).
La herramienta web ofrece una versión indexada y restricciones robots en algunas
consultas; la extracción real usa directamente el HTML actual por HTTPS.

Esta página contiene un inventario estático mediante pestañas: datos generales y
tres instrumentos, cada uno con documentación sustantiva. La ejecución real devuelve
**3 instrumentos y 64 documentos únicos dentro de sus instrumentos**:

- PLAN GENERAL DE URBANISMO DE IBARRA: 37 documentos, incluyendo anuncio BOG,
  libros de memoria, normas, estudio económico y planos.
- PLAN APATTA II: 23 documentos, incluyendo memoria, ordenanzas, estudios y planos.
  Contiene referencias de planeamiento tanto de Ibarra como de Tolosa: el registro
  conserva el instrumento municipal publicado, sin afirmar que todo su ámbito
  territorial esté en Ibarra. El texto «BOG ANUNCIO» no tiene enlace en esta pestaña;
  no se inventa uno.
- 1.1 GURUTZEAGA, II. ESTUDIO DE DETALLE: 4 documentos, memoria, planos de
  información, planos de ordenación y anuncio.

No hay controles de paginación en este inventario. Se recorren todas las pestañas
publicadas; una pestaña sin contenido, una discrepancia entre paneles y navegación,
controles de paginación, documentos sin UUID o un cambio de tipo causan error antes
de reemplazar la salida. No hay límite de registros que trunque resultados.
Los documentos se agrupan por instrumento, deduplicando UUID Liferay. Se conservan
las URLs originales (también las duplicadas con variantes http/https o parámetros)
en `enlaces_fuente`, y una URL HTTPS sin query para acceso e identidad documental.
Los títulos fragmentados de un mismo enlace se reúnen. El ID del instrumento deriva
del título, por lo que una renominación puede cambiarlo; no es un ID de expediente.

Cobertura **parcial**, no todo el planeamiento histórico ni un certificado de vigencia.
La pestaña DATOS GENERALES incluye normativa anterior y formularios H1–H13 y se
excluye de este inventario de instrumentos. No se interpretan como concesiones.
https://www.ibarra.eus/es/obras-servicios ofrece funciones departamentales, servicios
y trámites, no un inventario de obras concretas. https://www.ibarra.eus/es/transparencia
enlaza órganos y actas; no se extraen sus acuerdos. Tampoco se rastrean noticias,
contratación ni tablón externo. Licencias deshabilitadas.

## Fechas y procedencia documental

La página de inventario no fecha la publicación de cada instrumento ni declara
uniformemente su fase. El adaptador deja `fecha`, `fecha_publicacion`, `fecha_acuerdo`,
`fecha_aprob` y `fase` en null: no interpreta años de los planos, «Marzo 2019» de un
archivo ni parámetros `t` como fechas de aprobación. Los PDFs quedan enlazados con
procedencia de la pestaña municipal y no generan proyectos adicionales.

Como comprobación documental separada se descargaron las tres memorias y los dos
anuncios disponibles: cinco respuestas HTTP 200, con cabecera binaria PDF. Los dos
anuncios se convirtieron localmente a texto para revisión:

- El anuncio BOG del plan general está publicado el **2019-02-26**. Relata la
  aprobación definitiva del **2018-02-20**, la aprobación municipal del texto refundido
  del **2018-10-25** y una orden foral del **2019-01-18**. Son eventos distintos.
- El anuncio BOG de Gurutzeaga se publica el **2024-03-27**; relata un acuerdo de
  aprobación definitiva del **2024-02-15** y se firma el **2024-03-05**.

Estas fechas documentales se describen aquí para auditoría, pero **el parser HTML no
las extrae** ni las incorpora como constantes. No se afirma que la publicación BOG
sea la fecha de publicación de la pestaña municipal. No se verificaron individualmente
todos los enlaces a planos; quedan retenidos íntegramente en los registros.

## Geometría

`geometry_status: unavailable`. El inventario ofrece planos PDF, no una capa
vectorial vinculada a cada instrumento. El menú municipal enlaza el callejero
https://www.ibarra.eus/es/kale-izendegia; no se ha verificado un servicio vectorial
con geometrías identificables de estos expedientes. No se digitalizan los PDFs,
no se atribuye un CRS y no se inventan centroides ni coordenadas. `lat`, `lon` y
`geometry` null; `publication_ready: false`; `geocode.jitter_missing: false`.

## Reproducción y evidencia local

Pruebas: `python -m unittest municipio.test_ibarra -v` (3 pruebas, pasan).
Verifican deduplicación y enlaces originales, fechas desconocidas, rechazo de
paginación/contenido ausente, salida atómica, refresco y licencias deshabilitadas.

La ejecución real llama `IbarraAyuntamientoAdapter('ibarra',
{'evidence_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
`update_proyectos` refresca la misma instantánea completa, sin cursor ni estado
incremental ficticio. Manifest cargado correctamente con el lector existente.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/urbanismo.html`, capturas de portada,
Obras y servicios y Transparencia, cinco PDFs y dos textos de anuncios.
La validación contiene recuentos, URLs, comprobaciones binarias y limitaciones.
`schedule.enabled: false`. Sin dependencias nuevas, cambios compartidos,
base de datos, publicación ni despliegue.
