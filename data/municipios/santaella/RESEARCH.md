# Santaella (Córdoba), INE 14060

Investigación y extracción real: 2026-11-09. Se revisaron antes el contrato
`municipio/adapters/portal.py`, el cargador `municipio/manifest.py`, el registro de
adaptadores y los ejemplos Chipiona y Hernani. No hay cambios compartidos.

## Descubrimiento de fuentes oficiales

- https://santaella.es/ y https://transparencia.santaella.es/: HTTP 403 desde
  este entorno, también en las rutas `/urbanismo/`. Capturas en `evidence/`.
  Los resultados de búsqueda de presupuestos, ordenanzas y formularios no se
  convierten en obras, proyectos ni licencias concedidas.
- https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf : consulta
  pública oficial de planes urbanísticos y territoriales de Andalucía (SITUA).
  Se selecciona «Planes urbanísticos y territoriales aprobados», municipio
  Santaella, código 14060. El editor es Junta de Andalucía, no el Ayuntamiento.
  El manifiesto usa `proyectos.source: ayuntamiento` como categoría admitida por
  el pipeline; los registros explicitan `source: junta_de_andalucia`.
- La web usa JSF y DataTables. La búsqueda POST reproduce los campos públicos
  `municipiosseleccionados=14060`, `munNomCod=[{"id":"14060","nombre":"Santaella"}]`
  y `radioButton=aprobado`, con ViewState del formulario actual. Su inventario
  POST `https://ws132.juntadeandalucia.es/situadifusion/pages/figuras.jsf`
  recibe `codigos=14060`, `iDisplayStart` e `iDisplayLength`. Se recorren todas
  las páginas hasta `iTotalDisplayRecords`, comprobando estabilidad del total,
  identidad, provincia y municipio. Páginas vacías, duplicadas, cambiantes o
  estructura inesperada abortan sin sustituir el archivo anterior. No se
  impone un máximo de registros ni se limita la salida a la primera página.

## Resultado y procedencia documental

La ejecución viva devuelve **1 instrumento**, ID SITUA **32790**, «PGOU - Plan
General de Ordenación Urbanística — Santaella — 2016», con **68 documentos
únicos**. El objeto `2016`, la figura, el estado literal del catálogo y su fecha
se extraen de la ficha, no de valores precargados. Cada instrumento descubierto
abre su propia ficha mediante el comando JSF `tipoPlaneamiento` y `codFigura`.
El array JSON `mapa` contiene todos los documentos del árbol; se lee como JSON,
sin ejecutar JavaScript. Se deduplica por URL de documento, reteniendo todas
las claves de grupo/hito en `grupos_fuente`. Normas, memoria, fichas, planos,
certificaciones y BOJA son documentos del PGOU, no proyectos independientes.
Los nombres repetidos con distintas URLs se conservan.

La URL general del registro es la entrada pública de consulta: la ficha JSF
requiere navegación con sesión, por lo que no se presenta una URL de sesión
como permalink. `source_id` y `source_request` permiten reproducir la selección.
Las URLs documentales `descargaDocumentos.jsf?doc=…` son las publicadas por
SITUA. Una petición sin sesión al documento 145050 terminó en
`errorDescargaDocumentos.jsf`, HTTP 200 HTML en vez de PDF: se conserva como
limitación explícita. No se afirma haber descargado o validado los 68 binarios.
La captura de ese intento es HTML, no un PDF válido.

Contraste oficial del mismo instrumento, expediente P-68/07:

- https://www.juntadeandalucia.es/boja/2016/224/107 : publicación **22/11/2016**,
  acuerdo **26/10/2016**, aprobación definitiva parcial con suspensiones.
- https://www.juntadeandalucia.es/boja/2017/200/80 : publicación **18/10/2017**,
  acuerdo **20/09/2017**, aprobación definitiva del cumplimiento de resolución.

El catálogo mantiene `26/10/16` en «Fecha de Aprobación». Se conserva como
`fecha_aprob: 2016-10-26` con alcance explícito: fecha de la ficha, no último
acuerdo ni prueba de vigencia consolidada. El literal «Vigente» se conserva
únicamente como `estado_fuente`. No se deducen fecha de publicación, fecha de
acuerdo, fase de obras ni concesión de licencia. Los dos anuncios anteriores
no generan dos instrumentos adicionales. Las fechas de contraste se documentan
aquí, sin sustituir silenciosamente la fecha del inventario.

## Límites de cobertura

Sólo consulta de planes aprobados de SITUA para Santaella; no se afirma cubrir
el libro de registro completo, modificaciones, planeamiento detallado o en
tramitación, obras públicas, expedientes de contratación ni concesiones de
licencia. La imposibilidad de consultar los portales municipales impide ampliar
esa cobertura. Los documentos históricos del PGOU también incluyen La Guijarrosa:
se conservan como documentos históricos del instrumento, sin atribuir nuevas
actuaciones al término municipal actual. No se extraen actuaciones separadas de
los nombres de planos. No hay coordenadas ni geocodificación; `publication_ready`
es falso y `geometry_status` es `unavailable`. Licencias, programación y jitter
están desactivados. Update repite la captura completa y no adelanta estados.

## Validación y reproducción

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_santaella -v` (7 pruebas correctas):
agrupación documental, semántica de fechas, rechazo de municipio/ficha incorrectos,
mapa ausente o JavaScript en vez de JSON, contrato del manifiesto, paginación con
varios instrumentos, rechazo de páginas repetidas sin sobrescribir resultados y
licencias desactivadas. Fixtures sintéticos autónomos, sin dependencia de evidencia.

Extracción real mediante `load_manifest('santaella')`, configuración opcional
`manifest.portal.config['capture_dir'] = 'evidence/live'`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
La evidencia guarda el formulario, respuesta de búsqueda, página JSON completa
y ficha HTML con su mapa documental. `evidence/validation.json` registra
`live_records: 1`, 68 enlaces, URLs consultadas, hora UTC y limitaciones. No se
requieren credenciales, base de datos, instalación, publicación ni despliegue.
La evidencia es local y queda fuera de los cuatro archivos fuente solicitados.

Además del HTML de BOJA se descargaron sus dos PDFs oficiales firmados desde
las URLs «Descargar PDF»: HTTP 200, `application/pdf` y cabecera `%PDF-` en
ambos. Capturas `evidence/boja-2016.pdf` y `evidence/boja-2017.pdf`; URLs exactas,
tamaños y SHA-256 en `validation.json`. Esto verifica documentos del instrumento,
sin afirmar que funcionan las descargas homónimas de SITUA.
