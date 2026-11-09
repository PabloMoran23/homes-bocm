# Blanca — Murcia — INE 30011

Investigación y extracción real: 2026-11-09. Adaptador exclusivo para Blanca,
conforme al contrato `municipio/adapters/portal.py` y al esquema leído en
`municipio/manifest.py` y los ejemplos Chipiona, Hernani y Manlleu.

## Descubrimiento y fuentes oficiales

- Web municipal: https://blanca.es/nuevaweb/ y categoría
  https://blanca.es/nuevaweb/category/urbanismo/ . La búsqueda web permite leer
  noticias, pero las peticiones HTTP directas desde Python terminaron con
  `RemoteDisconnected`, también con www y HTTP. No se utiliza el buscador como
  extracción del adaptador, ni se convierten anuncios de contratación en proyectos.
- Sede oficial, identificada como Ayuntamiento de Blanca, entidad 30011:
  https://sede.blanca.regiondemurcia.es/cargaMenuWeb.do?entidad=30011&idioma=1 .
  Su función `cargarServicios` enlaza el portal público de transparencia:
  https://sede.blanca.regiondemurcia.es/web/transparencia?entidad=30011&idioma=1 .
- La sección 7 «Urbanismo, obras públicas y medio ambiente», epígrafe 11, enlaza
  «7.1. Planeamiento urbanístico», epígrafe 34. Inventario de entrada del scraper:
  https://sede.blanca.regiondemurcia.es/web/transparencia/QXl1bnRhbWllbnRvIGRlIEJsYW5jYUBAQDM0/30011 .
  Las rutas Base64 son las que construye la navegación pública; no son sesiones.
- Se revisaron también https://urbmurcia.carm.es/ y su consulta pública
  https://urbmurcia.carm.es/urbmurcia/faces/pla/query.jsp . Python recibió HTTP 200
  con página «Radware Captcha Page», no expedientes. No se intenta resolver ni
  eludir el CAPTCHA. https://sitmurcia.carm.es/planeamiento-urbanistico identifica
  su cartografía como informativa y fecha los datos de Blanca en noviembre de
  2008; no se usa esa cartografía histórica como geometría de los instrumentos.
- El tablón público de la sede se consultó como alternativa. La pantalla inicial
  utiliza búsqueda de los últimos 90 días por defecto y resultados mediante JS;
  no se incorpora ni se presenta como un registro histórico de licencias.

## Cobertura comprobada

El inventario de planeamiento devuelve dos documentos resumen y seis carpetas.
Se solicitan **las seis**, incluidas las vacías. Resultado real:

| Carpeta pública | ID de epígrafe | Documentos | Registros |
| --- | --- | ---: | ---: |
| Planeamiento General / PGMO de Blanca | 495 | 22 | 1 |
| Sector UBRS-2 — Plan Parcial Runes | 518 | 0 | 0 |
| Sector UBRS-5 — Plan Parcial Isla Blanca I | 519 | 0 | 0 |
| Sector UBRS-6 — Plan Parcial Monteclaro | 520 | 0 | 0 |
| Plan Parcial San Roque II.1 | 1165 | 10 | 1 |
| Plan Parcial San Roque II.2 | 1164 | 13 | 1 |

Cada carpeta con documentos constituye un instrumento, sin separar memoria,
planos, programa, normas, informes y certificado de aprobación en actuaciones
ficticias. Los títulos de los planes parciales proceden del inventario; la carpeta
«Planeamiento General» se denomina PGMO según sus documentos. El identificador
estable es el ID de la carpeta, no un supuesto número de expediente.

Los dos PDFs raíz «Planeamiento General» (88705) y «Planes Parciales» (88737)
se conservan en `documentos_contexto_inventario` de cada registro. Son resúmenes,
con otros instrumentos y modificaciones: no se emiten como proyectos adicionales
ni se afirma que los tres registros cubran todo su contenido. Las carpetas sin
documentación no generan registros basados únicamente en un nombre.

La sede incluye las tarjetas y enlaces en literales JS generados por el servidor.
El parser reconstruye únicamente esos literales con JSON y BeautifulSoup, sin
ejecutar JavaScript. Los enlaces `verDoc(ID)` se conservan como GET público
`/web/transparencia.do?opcion=6&idDoc=ID&entidad=30011&idioma=1`.
Se verificaron cuatro descargas completas (88705, 88737, 368452 y 88707): HTTP 200,
`application/pdf`, firma `%PDF-`. Las copias están bajo `evidence/`; el adaptador
no descarga masivamente los PDFs en cada actualización.

No hay paginación del inventario observada: todos los elementos se entregan en
la misma respuesta de cada carpeta. Se verifica el contador de cada carpeta
contra documentos e hijos recibidos. Contenido ausente, contador discrepante,
paginación nueva o subcarpetas nuevas producen error explícito antes de sustituir
la instantánea. Update vuelve a consultar el inventario completo; no aplica una
ventana temporal ni un límite silencioso de registros.

## Semántica y límites

Cobertura parcial del inventario documental actualmente accesible. No acredita
vigencia, consolidación normativa, totalidad de modificaciones, ejecución de obras
ni licencias concedidas. Los PDFs contienen fechas: por ejemplo, el BORM del PGMO
88707 distingue la orden de 14/02/2012 de la publicación de 14/03/2012 y menciona
aprobaciones parciales previas. El adaptador no analiza el texto PDF: deja
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` en null y no deduce fase del
nombre «certificado» ni de fechas de firma, títulos o reloj de la sede.

No se ha obtenido geometría vectorial vinculada a estos instrumentos. Planos PDF
no se convierten en puntos ni en centroides municipales. Latitud, longitud y
geometry son null; `publication_ready` es false. El manifest desactiva licencias,
ejecución programada y jitter de coordenadas. Los modelos de solicitud y
declaraciones responsables no se interpretan como concesiones.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_blanca -v`: seis pruebas correctas. Comprueban
identidad y enlaces documentales, agrupación entre instrumentos, exclusión de
carpetas vacías, fechas y coordenadas desconocidas, rechazo de CAPTCHA/paginación,
contadores discrepantes sin sobrescribir resultados, subcarpetas nuevas y flags
del manifest/licencias.

Extracción real mediante `load_manifest('blanca')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local
`evidence/live`: **3 registros y 45 documentos propios**, más dos documentos de
contexto compartidos. Siete respuestas de inventario capturadas en esa ejecución.
La anotación compartida de política de entidades devuelve tres categorías
desconocidas; se conserva esa salida sin inventar una tipología residencial.

`evidence/validation.json` recoge recuentos, URLs, límites, pruebas y verificaciones
PDF. Las evidencias son locales y no forman parte de los cuatro archivos fuente.
No se modificaron dependencias ni fuentes compartidas ni se ejecutaron publicación,
base de datos, despliegues o comandos del pipeline completo.
