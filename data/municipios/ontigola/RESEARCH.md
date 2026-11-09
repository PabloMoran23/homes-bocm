# Ontígola — Toledo — INE 45123

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes e inventario seleccionado

Se inspeccionaron primero `municipio/manifest.py`, el contrato de
`municipio/adapters/portal.py`, los adaptadores Chipiona/Hernani y el registro
de carga. Se añaden únicamente los cuatro archivos solicitados.

La [sección municipal de Urbanismo](https://www.ontigola.es/mi-ayuntamiento/urbanismo/)
es un archivo de tres noticias, incluida rehabilitación de firme y campo de
fútbol, junto a un aviso de mantenimiento de alumbrado. No es un registro de
licencias concedidas ni un inventario completo de planeamiento. Una primera
petición sin User-Agent devolvió 403; con User-Agent de navegador respondió 200.
La [sede electrónica](https://ontigola.sedelectronica.es/info.0) ofrece trámites y
un tablón; su catálogo de solicitudes no acredita concesiones y no se ingiere.

La fuente implementada es el [inventario oficial de acuerdos urbanísticos de
JCCM filtrado por título Ontígola](https://urbanismo.castillalamancha.es/acuerdos-expedientes?title=Ont%C3%ADgola).
El formulario declara «Fecha del acuerdo», su campo de búsqueda es `title` y
las tarjetas incluyen título, fecha, población cuando consta y enlaces PDF.
El filtro acentúa Ontígola pero también devuelve títulos sin tilde. La respuesta
real anuncia «Mostrando 1 - 9 de 9 expediente/s encontrados»: nueve tarjetas,
sin paginación en este resultado. El inventario general sí tiene paginación.
El adaptador sigue los enlaces `next`, conserva el filtro municipal, detecta
ciclos y duplicados y contrasta el total anunciado con las tarjetas recuperadas
antes de sustituir el resultado. No hay límite de páginas ni truncamiento.
Un cambio de estructura, ausencia de PDF, filtro perdido o cobertura incompleta
produce error. Los errores de configuración de vocabularios mostrados por el
servidor no impidieron recuperar y contar las nueve tarjetas válidas.

## Resultado y agrupación documental

**8 registros reales, 9 acuerdos y 9 documentos PDF**, con fechas de acuerdo
entre 16/01/2020 y 22/09/2026:

- Nuevo Centro Logístico, polígono 2 parcelas 01, 15 y 18.
- Subestación elevadora TAGUS e infraestructura de evacuación TAGUS 1 y 2.
- Planta fotovoltaica TAGUS 2.
- Planta fotovoltaica TAGUS 1.
- PAU subárea 1.5.2: el certificado identifica «Cerro de la Fuente II» y trata
  la resolución de la adjudicación del PAU; no se presenta como obra ejecutada.
- Modificación puntual 1 del Plan Parcial Los Albardiales III: se agrupan
  el documento CCI de 08/07/2021 y el CPOTU de 20/12/2021. Las primeras páginas
  escaneadas de ambos se revisaron visualmente: identifican el mismo expediente
  24/21 PL. Se conservan los dos enlaces, títulos y fechas en `acuerdos`.
- PAU, PERIM y proyecto de urbanización PR Logistic Park: un paquete documental.
- Modificación puntual 1 del Plan Parcial Dehesa de la Plata I.

TAGUS 1 y 2 se extienden también por Ocaña según los PDF: su vinculación a
Ontígola no significa exclusividad territorial. No se fusionan las plantas y
la subestación, que tienen expedientes distintos (064/23, 065/23 y 033/24 SNU).
El PAU sin campo población contiene Ontígola expresamente en el título y PDF.
Cada instrumento conserva documentos y procedencia por acuerdo; no se generan
registros para cada plano ni para la página genérica de resultados.

## Semántica y límites

Cobertura **parcial**, limitada a acuerdos que mencionan Ontígola en su título
en este inventario autonómico. No se afirma cubrir todo el planeamiento, obras
municipales, licencias ni boletines históricos. Se filtran entradas sin términos
de instrumentos/proyectos y se excluyen formularios y anuncios de contratación;
el resultado informa de los descartes (cero en esta ejecución).

Las fechas son `fecha_acuerdo` en cada evidencia, nunca fechas de publicación ni
aprobaciones definitivas inferidas. En un instrumento con varias fechas no se
atribuye una fecha única al conjunto. El tipo no se transforma en fase. No se
deduce vigencia, licencia concedida, ejecución ni coordenadas. Los proyectos
pueden ser privados; la fuente pública regional no implica titularidad municipal.
Todos los registros llevan `publication_ready: false` y geometría no disponible.
El manifest desactiva licencias, programación y jitter. El valor `ayuntamiento`
en `proyectos.source` selecciona el canal de adaptador portal del esquema existente;
la procedencia real de cada registro es `source: jccm`, declarada explícitamente.

## Validación reproducible y evidencia local

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ontigola -v`.
Siete pruebas correctas: agrupación y aislamiento de documentos, semántica de
fechas, ámbito municipal, exclusión de formularios/contratación, cambios de
estructura y documentos ausentes, recorrido completo de páginas y rechazo de
truncamiento/ciclos sin sobrescribir un resultado anterior; manifest y licencias.

Se ejecutó realmente `OntigolaAyuntamientoAdapter.backfill_proyectos` con el
manifest y `capture_dir=evidence`, escribiendo `evidence/proyectos.jsonl`.
`evidence/validation.json` contiene `live_records`, URLs, limitaciones y resultados.
`live-inventory-1.html` captura la respuesta usada por el adaptador; las capturas
`discovery-*.html` y `acuerdos-0.html` documentan la investigación. Se descargaron
los nueve PDF (`acuerdo-0.pdf` a `acuerdo-8.pdf`), todos HTTP 200 y firma `%PDF-`.
`pdftotext` produjo texto en los cinco primeros y confirmó que los cuatro últimos
son escaneados sin texto extraíble; se conservaron también los textos y las dos
imágenes revisadas de Los Albardiales III. El parser no depende de OCR ni del
directorio de evidencia. La evidencia es local y no forma parte de los fuentes.

No se ejecutaron publicación, geocodificación, bases de datos ni despliegues.
