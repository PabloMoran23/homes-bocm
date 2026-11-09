# Aielo de Malferit — Valencia — INE 46042

Investigación y extracción en vivo: 9 de noviembre de 2026. Identidad municipal:
las páginas oficiales indican Ajuntament d'Aielo de Malferit, Plaça Palau 4,
46812 Aielo de Malferit, VALÈNCIA. El manifest identifica expresamente INE 46042.

## Inventarios oficiales descubiertos

- [Transparència](https://www.aielodemalferit.es/va/ajuntament/ajuntament/transparencia)
  enlaza actuaciones urbanísticas, planes municipales y proyectos e inversiones.
- [Plans municipals](https://www.aielodemalferit.es/va/ajuntament/ajuntament/transparencia/plans-municipals)
  enlaza PGOU, movilidad sostenible y planes de emergencias/riesgos sísmicos.
- [PGOU](https://www.aielodemalferit.es/va/ajuntament/ajuntament/pgou-aielo)
  presenta documentos del plan general y de la modificación 1, además de un iframe
  de la sede electrónica. Solo los PDF publicados directamente en esta página
  forman parte de la extracción.
- [Actuacions urbanístiques](https://www.aielodemalferit.es/va/ajuntament/ajuntament/actuacions-urbanistiques)
  presenta el programa de actuación aislada de Carrer Font de la Figuera: proyecto
  de urbanización, programa y certificado de acuerdo en una misma sección.
- [Projectes i inversions municipals](https://www.aielodemalferit.es/va/ajuntament/ajuntament/projectes-i-inversions-municipals)
  contiene fichas de obras, instalaciones y estudios, mezcladas con subvenciones
  sociales y carpetas por año. Se consultaron sus 25 enlaces de primer nivel y se
  guardaron capturas locales para distinguir su contenido. Este inventario queda
  fuera del alcance implementado. Por ejemplo, la ficha del gimnasio del pabellón
  contiene únicamente una convocatoria de licitación y no se convierte en proyecto.
  Las ayudas de igualdad/violencia de género tampoco son obras físicas.

## Cobertura implementada y agrupación

Dos páginas HTML oficiales, sin paginación observada en sus inventarios
documentales. El adaptador rechaza indicadores de paginación si aparecen: no
devuelve silenciosamente una primera página. No recorre el iframe ni los otros
inventarios, boletines oficiales o noticias. Es una cobertura parcial del
inventario publicado, no un registro histórico exhaustivo ni una declaración de
vigencia urbanística. La búsqueda también localizó referencias a una modificación
3 posterior en DOGV (2026/5244), ausente de estos dos listados; no se incorpora ni
se extraen fechas de ella. No se pudo verificar su PDF con el navegador de búsqueda.

Resultado de ejecutar el adaptador real cargado desde el manifest:

| Instrumento | PDF enlazados |
| --- | ---: |
| Pla General d'Ordenació Urbana | 3 |
| MODIFICACIÓ 1 PGOU: Revisió d'usos | 4 |
| Programa actuació aïllada Carrer Font de la Figuera | 9 |

**3 registros, 16 documentos.** Se conserva cada enlace documental en
`documentos`, con título, sección y página de procedencia. Los nueve documentos
de Font de la Figuera constituyen un solo expediente; sus planos, programa y
acuerdo no se cuentan como actuaciones independientes. Las modificaciones del
PGOU se agrupan bajo sus propios encabezados, separadas del plan base. Los
enlaces repetidos dentro de un instrumento se deduplican por URL. Identificadores
deterministas derivados de página y título, sin una lista de registros precargados.
Los enlaces de iconos sin texto conservan el nombre de fichero como título y lo
declaran con `titulo_origen: filename`.

## Fechas y procedencia

Las etiquetas de la modificación 1 contienen fechas de edicto, memoria y anuncios.
Se conservan literalmente; no son intercambiables con fechas de acuerdo o de
aprobación. No se emite `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`
ni una fase deducida del tipo o del título de un documento. El certificado de
Font de la Figuera se enlaza sin interpretar su contenido ni atribuirle una fecha.
Los cuerpos de los PDF no se analizan en este adaptador.

El CMS publica enlaces HTTP. `source_url` conserva el enlace original resuelto y
`url` utiliza HTTPS en el mismo dominio municipal. Se comprobaron por petición GET
en streaming el PDF de información pública de la modificación 1, el certificado
de Font de la Figuera y el documento de normas/fichas del PGOU. Los tres dieron
HTTP 200, `application/pdf` y cabecera `%PDF-`; se guardaron únicamente los primeros
1024 bytes. No se afirma haber verificado todos los archivos completos.

Sin coordenadas, geometrías o fechas inventadas. Todos los registros llevan
`geometry_status: unavailable` y `publication_ready: false`. No hay fuente pública
de concesiones de licencias verificada: `licencias.enabled: false`. También están
desactivados `schedule.enabled` y `geocode.jitter_missing`.

## Verificación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`python -m unittest municipio.test_aielo_de_malferit -v` — 7 pruebas correctas.
Cubren agrupación y aislamiento entre modificaciones, conservación de planos y
acuerdo, exclusión de formularios/navegación, etiquetas de fecha sin inferencias,
proveniencia, títulos de iconos, cambios de estructura, paginación, orígenes
inesperados y ausencia de documentos. Se comprueba además que un fallo de red en
la segunda fuente conserva la salida previa sin generar una extracción parcial,
que update produce la misma instantánea y que las licencias están desactivadas.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` opcional
apuntando a `evidence`. La anotación local de política de entidades se ejecuta por
el registro compartido, sin modificarlo. No se usa base de datos, publicación,
geocodificación ni servicios de despliegue.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: los 3 registros extraídos en vivo.
- `evidence/validation.json`: contador real, fuentes, limitaciones, runtime,
  resultado de pruebas y comprobaciones documentales.
- `evidence/pgou-aielo.html` y `evidence/actuacions-urbanistiques.html`: respuestas
  HTML utilizadas por la ejecución del adaptador.
- Capturas de los otros inventarios y fichas investigadas, `document_checks.json`
  y los tres prefijos PDF de comprobación.

Backfill y update descargan ambas fuentes antes de escribir la instantánea.
No se simula un incremental por fechas, no se infieren eliminaciones históricas
y una fuente vacía o con estructura desconocida produce un error explícito.
