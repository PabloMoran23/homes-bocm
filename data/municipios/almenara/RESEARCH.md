# Almenara — INE 12011, Castellón

Verificación en vivo: 2026-11-09. Se implementa un solo adaptador y una cobertura
parcial y explícita: el conjunto de documentación del texto consolidado del
planeamiento municipal alojado por la Generalitat Valenciana. No es un inventario
completo de actuaciones, un registro de licencias ni una aprobación nueva.

## Fuentes oficiales descubiertas

- https://almenara.es y https://www.almenara.es: las peticiones con verificación
  TLS fallan por cadena de certificado no verificable, incluso con el almacén de
  certificados del sistema. No se desactiva la verificación TLS. El acceso HTTP
  redirige a HTTPS con el mismo problema.
- https://almenara.sedelectronica.es/transparency: HTTP 200. El portal identifica
  la sección «8. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» con 256 entradas;
  su expansión usa Wicket Ajax y parámetros de sesión. No se extrae esta sección,
  ni se presenta su contador como número de proyectos. La portada de la sede
  ofrece solicitudes/declaraciones responsables: no acreditan licencias concedidas.
- https://mediambient.gva.es/es/web/urbanismo/informacion-urbanistica: HTTP 200;
  enlaza al registro autonómico y a textos consolidados municipales.
- https://mediambient.gva.es/es/web/urbanismo/textos-consolidats-planejament-municipal:
  HTTP 200, enlaza el inventario `/auto/urbanismo/Textos_consolidados`.
- https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/ : HTTP 200,
  directorio con convocatorias. La de Orden 10/2022 enlaza específicamente
  `12011 Almenara`, descartando Almenar (Lleida) y otros homónimos.
- https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/2.%20Textos%20consolidados%2C%20Orden%2010-2022/12011%20Almenara/ :
  HTTP 200. Inventario plano de 13 PDF: índice, síntesis, plano guía de instrumentos,
  ordenanzas de NNSS y desarrollo, clasificación, zonificación, sistemas generales
  y ordenación. Se conservan todos los enlaces como documentos de un solo conjunto.

## Semántica y procedencia

El PDF `00_TC_Indice_de_documentos.pdf`, descargado y convertido con el ejecutable
preinstalado `pdftotext`, identifica expresamente el texto consolidado de Almenara.
Su portada indica octubre de 2023. La diligencia menciona un informe técnico de
22 de junio de 2023 y una firma de 13 de noviembre de 2023; el índice también
muestra 07/11/2023. Ninguna de estas fechas se transforma en publicación, acuerdo
ni aprobación. Esos campos permanecen nulos, al igual que la fecha genérica.

La propia documentación declara carácter informativo y ausencia de valor jurídico;
remite a los instrumentos originales para información con plena validez jurídica.
Por ello el registro se denomina `texto_consolidado_planeamiento`, sin fase de
aprobación inferida. No se crean 13 proyectos a partir de los 13 ficheros, ni se
atribuyen aprobaciones individuales a instrumentos incorporados en la compilación.
La procedencia identifica a la Generalitat como anfitrión de documentación municipal.
Solo se descarga y valida semánticamente el índice general, no todos los adjuntos.

## Comportamiento y límites

El adaptador lee todas las entradas PDF del directorio y elimina enlaces repetidos.
No hay paginación en el inventario observado. Cualquier enlace de siguiente página,
subdirectorio, entrada inesperada o ausencia de documentos esenciales provoca error:
no hay corte silencioso por número de entradas. Los límites de descarga de 2 MB
para HTML y 10 MB para el índice PDF abortan en vez de truncar. Los cambios de
municipio, redirecciones, HTML de login o PDF no identificable también fallan antes
de sustituir la salida. La actualización refresca el conjunto completo, sin filtros
por fecha; la identidad estable deriva del conjunto y convocatoria oficiales.

Se requieren las dependencias ya declaradas requests/BeautifulSoup y el ejecutable
Poppler `pdftotext` presente en el entorno; no se instala software. No se verifica
geometría de proyectos a partir de los planos PDF ni se utilizan centroides:
lat/lon/geometry son nulos y publication_ready es false. schedule.enabled,
geocode.jitter_missing y licencias.enabled son false en el manifest.

## Validación y evidencias locales

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_almenara -v`: 5 pruebas superadas. Comprueban la
  agrupación, fechas no confundidas, rechazo de otro municipio/formularios,
  paginación y subdirectorios, conservación de salida ante fallo y resolución del
  adaptador desde el manifest con licencias desactivadas.
- Extracción real mediante `load_portal_adapter(load_manifest('almenara'))` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 1 registro, 13 documentos.
  Se ha aplicado también el anotador compartido de entidades del cargador.
- `evidence/validation.json`: live_records, source_urls, attachment_urls,
  limitaciones, fecha UTC, resultados de pruebas y anotación de entidades.
- `evidence/inventory.html` y `evidence/index.pdf`: respuestas utilizadas por el
  adaptador; `evidence/index.txt`: texto inspeccionado. Los HTML `discovery-*`,
  `consolidated-inventory.html` y `parent-*` documentan el descubrimiento.

Las evidencias son locales, ajenas a los cuatro archivos fuente entregados.
No se han consultado credenciales, bases de datos ni herramientas de despliegue.
