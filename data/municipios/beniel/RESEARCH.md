# Beniel — INE 30010, Murcia

Investigación y extracción real: 7 de noviembre de 2026. Un único adaptador municipal.

## Descubrimiento y fuente elegida

Se revisaron primero `municipio/adapters/portal.py`, el cargador de manifests y los
ejemplos de Chipiona y Hernani. La identificación municipal es Beniel, provincia
de Murcia, código INE 30010; la sede oficial utiliza también `entidad=30010`.

`https://www.beniel.es/` redirige a `https://sede.beniel.regiondemurcia.es/`.
Su página de inicio enlaza mediante `cargarServicios()` al portal de transparencia:
https://sede.beniel.regiondemurcia.es/web/transparencia?entidad=30010&idioma=1

El árbol público es: 7. Urbanismo, obras públicas y medio ambiente (epígrafe 11)
→ 7.1. Planeamiento urbanístico (34). El inventario actual elegido es:
https://sede.beniel.regiondemurcia.es/web/transparencia/QXl1bnRhbWllbnRvIGRlIEJlbmllbEBAQDM0/30010

El portal codifica `Ayuntamiento de Beniel@@@<epígrafe>` en base64 para construir
las rutas. Esto es un identificador público del árbol, no una credencial. Los
fragmentos HTML de carpetas y documentos vienen en literales JavaScript del
servidor. El parser decodifica únicamente esos literales con JSON y BeautifulSoup;
no ejecuta JavaScript ni accede a sesiones autenticadas.

## Cobertura observada y agrupación

La extracción mediante el adaptador cargado desde el manifest produce **3 registros
y 10 enlaces documentales**, uno por carpeta/instrumento:

| Epígrafe | Instrumento | Documentos |
| --- | --- | --- |
| 669 | Modificación puntual nº 1, no estructural del PPI El Mojón | Aprobación definitiva, documento inicial estratégico y proyecto de modificación |
| 670 | Estudio de detalle revisado nº 01/24 | Publicación definitiva, memoria, planos y anexos |
| 681 | Plan General Municipal de Ordenación | Memoria del avance, publicación BORM y acuerdo JGL 30/05/24 de sometimiento del avance a información pública |

Se conservan los títulos exactos publicados, los identificadores y enlaces de todos
los documentos. Los enlaces se construyen con la misma acción pública `verDoc` del
portal: `/web/transparencia.do?opcion=6&entidad=30010&idioma=1&idDoc=<id>`.
No se generan registros separados para memoria, planos o anuncio del mismo plan.
Los IDs estables corresponden a la carpeta, no al texto ni al orden del listado.

Cuatro documentos se descargaron y comprobaron por firma `%PDF`: 303658 (PPI),
315437 (estudio de detalle), 319446 (BORM del avance) y 315627 (acuerdo JGL).
El resto de enlaces se conserva según el inventario, sin afirmar comprobación de
su contenido. El PDF 303658 distingue publicación BORM **22/04/2024**, acuerdo del
Pleno **21/03/2024** y fecha de firma del anuncio **09/04/2024**. El adaptador no
extrae fechas de PDFs: ninguna de estas fechas se transforma en fecha genérica ni
se propaga al resto de documentos. El título del acuerdo JGL también se conserva
literalmente, sin convertir automáticamente su fecha en fecha de aprobación.

No se observó paginación en este árbol: el servidor devuelve todas las carpetas y
todos sus documentos. Se recorren todas las carpetas del inventario, sin límite de
registros. Cada cantidad de documentos debe coincidir con el contador de la
carpeta. Los enlaces sin interpretar, carpetas anidadas nuevas, tipos de instrumento
desconocidos o paginación detectada producen error antes de sustituir la salida.
La paginación del buscador global de trámites es ajena a este inventario.

## Límites y fuentes descartadas

Cobertura completa del epígrafe actual 7.1, pero **parcial respecto al municipio**:
no representa todo su histórico de proyectos ni todas sus obras físicas. El árbol
7.4 Obras públicas e infraestructuras mostraba cero entradas. El tablón público
se consultó para descubrir fuentes, pero no se utiliza como inventario de proyectos.
Los trámites de solicitud/informe urbanístico no acreditan licencias concedidas.
`licencias.enabled=false`, `schedule.enabled=false` y `geocode.jitter_missing=false`.
No se inventan coordenadas, fases, vigencia jurídica ni fechas. Los registros
declaran `publication_ready=false` y `geometry_status=unavailable`.

También se descubrió el portal regional oficial URBmurcia y su guía de consulta
de planeamiento general de septiembre de 2025:
https://urbmurcia.carm.es/documents/75246/76802/Urbmurcia%2Bguia%2Bconsulta%2BP%2BGeneral%2B2025-Septiembre.pdf/7eab11ec-8b52-6585-bac6-62949356ade5?t=1760951652386

Las peticiones de extracción a URBmurcia devolvieron captcha Radware. Los resúmenes
indexados del buscador solo ayudaron al descubrimiento; no alimentan registros.
No se intentó eludir el captcha. La fuente elegida es la sede municipal accesible.

## Verificación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_beniel -v`: **8 correctas**. Cubren
agrupación, aislamiento de documentos, contadores, títulos Unicode, exclusión de
formularios/contratación/noticias, fallos de estructura/paginación y conservación de
la salida anterior ante un inventario incompleto. También verifican manifest y
licencias desactivadas.

Ejecución real con `load_manifest('beniel')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La política compartida
anotó los tres registros como entidad desconocida sin bloquear la extracción;
no equivale a aprobación para publicar. El parámetro local opcional `capture_dir`
guardó las cuatro páginas consultadas en `evidence/live/`.

Evidencias locales, sin comprometerlas: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML y cuatro PDFs con sus hashes y estado HTTP
en la validación. No se usaron bases de datos ni publicación/despliegue.
