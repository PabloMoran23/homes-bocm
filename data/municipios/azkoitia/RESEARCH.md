# Azkoitia — INE 20017, Gipuzkoa

Verificado el 2026-11-07 usando el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Adaptador real de cobertura deliberadamente parcial: **un PGOU en preparación**,
con dos documentos oficiales agrupados. No acredita aprobación definitiva del
PGOU, licencias concedidas ni cobertura completa de actuaciones municipales.

## Descubrimiento y fuentes oficiales actuales

La navegación municipal Urbanismo enlaza estos inventarios:

- [Planes de Ordenación Urbana en Tramitación](https://azkoitia.eus/es/ayuntamiento/departamentos/urbanismo/planes-de-ordenacion-urbana-en-tramitacion).
  HTTP 200 desde Python. Inventario seleccionado: una ficha de PGOU, sin
  paginación activa en la captura. Se descubre su URL desde el enlace del artículo,
  sin fijar una noticia como semilla ni generar registros a partir de navegación.
- [Ficha PGOU](https://azkoitia.eus/es/ayuntamiento/departamentos/urbanismo/planes-de-ordenacion-urbana-en-tramitacion/13571-hapo-hiria-antolatzeko-plan-orokorra).
  HTTP 200, narrativa expresa del acuerdo de inicio y dos documentos PDF.
- [Normas subsidiarias](https://azkoitia.eus/es/ayuntamiento/departamentos/urbanismo/normas-subsidiarias).
  Inventario documental identificado en la investigación web; fuera de este
  adaptador, que no pretende catalogar el planeamiento histórico vigente.
- [Anuncios](https://azkoitia.eus/es/ayuntamiento/anuncios/).
  HTTP 200 en la investigación directa. Mezcla solicitudes de licencia,
  presupuestos, ordenanzas e instrumentos urbanísticos. No se ingiere como si
  todos sus anuncios fueran proyectos o concesiones.
- [Consultas previas / En exposición pública](https://azkoitia.eus/es/gobierno-abierto/noticias-participacion).
  Inventario mixto con seis páginas observadas, también excluido. No se toma su
  primera página como histórico completo ni se mezcla con el PGOU seleccionado.

Algunas primeras peticiones con el User-Agent predeterminado de requests
recibieron HTTP 403. Las peticiones posteriores con User-Agent de navegador,
incluida la extracción real del adaptador (con identificación del scraper),
recibieron HTTP 200. No hay autenticación ni desactivación de TLS. El alias
`dokumentuak.azkoitia.eus` presentó error de certificado; no se usa.

## Registro, documentos y semántica

Identidad estable `azkoitia-proy-13571`, derivada del identificador de contenido
municipal descubierto; no se presenta como número de expediente administrativo.
Título y descripción proceden de la fuente, y `url_inventario` conserva el origen.

- `fecha_acuerdo: 2024-12-19`: inicio del procedimiento/formulación del PGOU.
- `fecha_publicacion: 2025-02-20`: publicación del anuncio en el BOG, no fecha de
  publicación o actualización de la ficha HTML (esta no ofrece fecha verificable).
- `fecha` y `fecha_aprob` son nulos. La lista de fases futuras de la ficha no se
  transforma en fases alcanzadas ni en aprobaciones.

Documentos conservados bajo el mismo instrumento, con título, URL y ficha de
procedencia:

1. [Anuncio BOG, 20/02/2025](https://egoitza.gipuzkoa.eus/gao-bog/castell/bog/2025/02/20/c2501012.pdf).
   HTTP 200, 104521 bytes. PDF descargado y texto comprobado: acuerdo plenario
   de 19/12/2024 de formulación y establecimiento del programa de participación.
2. [Programa de participación ciudadana](https://azkoitia.eus/images/HAPO/UEX0003455800000036000000012023HAPO0003DILIGENCIA_sinatuta-1.pdf).
   HTTP 200, 1012584 bytes, cabecera PDF verificada.

El adaptador conserva enlaces de documentos sin requerir descargar PDFs en cada
actualización; la comprobación documental en vivo queda en la evidencia local.
No se generan proyectos separados por PDF ni por fase del procedimiento.

## Cobertura, paginación y geometría

Se recorre la paginación del inventario seleccionado mediante sus enlaces
`.pagination` y `rel=next`, deduplicando páginas y artículos. Se rechazan enlaces
fuera del inventario, paginación declarada sin enlaces y más de 100 páginas;
los errores abortan antes de sustituir la salida, sin aceptar truncamientos.
Solo se seleccionan fichas tituladas PGOU / Plan General de Ordenación Urbana.
Otras clases de planes y el archivo de anuncios quedan explícitamente fuera.

Las fichas seleccionadas requieren narrativa de inicio, anuncio BOG fechado y
programa de participación. Cambios de estructura/semántica o documentos ausentes
fallan explícitamente. Update refresca una instantánea completa; no reconcilia
bajas con históricos anteriores ni interpreta una fuente vacía como éxito.

`geometry_status: unavailable`: no geometría vectorial ni coordenadas vinculadas
al instrumento verificadas. No se sustituye por centroide municipal, direcciones
aproximadas ni geometría inventada. `lat`, `lon` y `geometry` son nulos;
`publication_ready: false`. El clasificador compartido anota este instrumento
como `pendiente / insufficient_identity_evidence`, conservado sin modificar la
política compartida y sin afirmar elegibilidad de actividad/publicación.

## Validación y evidencia

- `python -m unittest municipio.test_azkoitia -v`: **6 tests pasan**. Comprueban
  semántica de fechas, agrupación/deduplicación documental, rechazo de contenido
  incompleto o de origen incorrecto, exclusión de solicitudes, recorrido de dos
  páginas, fallo de paginación incompleta, preservación de salida ante errores y
  carga por manifest con licencias deshabilitadas.
- Extracción real mediante `load_portal_adapter(load_manifest('azkoitia'))` y
  `backfill_proyectos`: **status ok, live_records 1**, dos fuentes HTML y dos PDF
  oficiales comprobados. Sin datos simulados en la salida en vivo.
- Evidencias locales en `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `evidence/captures/`, `evidence/document-1.pdf`, `evidence/document-2.pdf` y
  `evidence/document-1.txt`. No se incorporan como fuentes al repositorio.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`. Solo los cuatro archivos autorizados; sin cambios de
fuentes compartidas, dependencias, base de datos, publicación ni despliegue.
