# Cantillana — Sevilla — INE 41023

Investigación y extracción en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

El [portal municipal de transparencia](https://transparencia.cantillana.es/es/)
identifica al Ayuntamiento de Cantillana y organiza sus documentos por indicadores.
El scraper lee íntegramente el [indicador 53: modificaciones del PGOU y planes parciales](https://transparencia.cantillana.es/es/transparencia/indicadores-de-transparencia/indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00021/).
La respuesta HTML actual incluye cinco galerías completas, sin controles de paginación.
No hay límite de registros ni corte por fecha. Si aparecen controles de continuación o
paginación, el adaptador falla explícitamente para evitar una instantánea incompleta.
Una galería desconocida también requiere revisión; no se descarta silenciosamente.

Resultado real: cuatro instrumentos, 22 enlaces PDF conservados:

| Galería municipal | Documentos |
| --- | ---: |
| FINCA LA PASTORA | 7 |
| PLAN PARCIAL PEDRO SANCHEZ 2 | 3 |
| PLAN PARCIAL VISTAHERMOSA DEL VIAR | 5 |
| PLAN ESPECIAL ADECUACION AMBIENTAL Y TERRITORIAL DE EDIFICACIONES IRREGULARES EN ALDEA PAJARES | 7 |

La Pastora tiene memoria, acceso al sector, anexos de parcela mínima, anexo PP y
planos. Se conserva literalmente su título municipal, sin inventar un nombre formal.
Cada galería es un instrumento: memoria, anexos, estudios, certificado y planos
reformados quedan unidos en `documentos`. El identificador deriva del título de la
galería, sin depender del número u orden de sus documentos. Los enlaces repetidos se
deduplican dentro del instrumento. Se mantienen los enlaces a versiones antiguas.

Se excluye expresamente AVANCE INVENTARIO DECRETO 2/2002: es un inventario informativo
de edificaciones/asentamientos, no un proyecto específico. No se incluyen formularios,
licitaciones ni noticias genéricas. No se afirma una cobertura completa del municipio.
La búsqueda también localizó el [indicador 54 de convenios y actuaciones](https://transparencia.cantillana.es/es/transparencia/indicadores-de-transparencia/indicador/54.-Se-publica-informacion-precisa-de-los-Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion.-00021/)
y el [indicador 55 de usos y destinos del suelo](https://transparencia.cantillana.es/es/transparencia/indicadores-de-transparencia/indicador/55.-Se-publica-informacion-precisa-sobre-los-usos-y-destinos-del-suelo.-00021/),
que el buscador muestra con un Plan Municipal de Vivienda y Suelo. Esas secciones quedan
fuera de esta implementación, limitada explícitamente al inventario del indicador 53.

## Fechas, procedencia y límites

Los `time[datetime]` de las fichas documentales se guardan únicamente como
`documentos[].fecha_catalogo`: el HTML no permite asegurar que sean la fecha legal
de publicación, acuerdo o aprobación. No se propagan al registro del instrumento.
No se utiliza una fecha genérica ni se deduce vigencia del nombre del indicador.

Para Los Pajares, la descripción municipal del plan diligenciado dice explícitamente
que fue aprobado definitivamente por acuerdo plenario de 29 de enero de 2026.
El scraper extrae `fecha_acuerdo: 2026-01-29` de esa frase y conserva el texto y enlace
en `fecha_acuerdo_fuente`. La fecha del catálogo de ese documento es 2026-04-10;
la del certificado es 2026-02-04. Son fechas diferentes, con semánticas distintas.
El certificado descargado corrobora la sesión del 29 de enero y la aprobación
definitiva, expediente 2022/URB_01/000082. La extracción no analiza PDFs ni depende
de fechas fijadas en el código.

Se descargaron dos PDFs oficiales con HTTP 200 y firma `%PDF-`: la memoria de La
Pastora (3.862.681 bytes) y el certificado de Los Pajares (180.852 bytes). La memoria
es escaneada: las dos primeras páginas no ofrecieron texto con `pdftotext`; no se ha
inferido de ellas fecha alguna. El resto de enlaces documentales se conserva sin
revisión completa de su contenido o disponibilidad. No hay coordenadas verificadas;
`geometry_status: unavailable`, `publication_ready: false`. Licencias desactivadas:
no se ha verificado un registro público de concesiones. Programación y jitter
geográfico desactivados en el manifest.

## Validación reproducible y evidencia local

Pruebas: `python -m unittest municipio.test_cantillana -v` con el runtime indicado:
7 pruebas correctas. Cubren agrupación y aislamiento de documentos, deduplicación,
identificadores estables, fechas con procedencia, rechazo de vacíos y PDFs ajenos,
paginación, conservación de salida ante fallo y resolución por manifest/registro.

Extracción real mediante `load_portal_adapter(load_manifest('cantillana')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
4 registros y 22 documentos, incluyendo la anotación habitual del registro compartido.
La política compartida devuelve `status: ok`, con categoría desconocida en los cuatro
registros; no constituye clasificación temática validada ni autorización de publicación.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/inventory-53.html`, `evidence/pastora.pdf`,
`evidence/pajares.pdf` y sus capturas de texto. El informe contiene el recuento real,
URLs de origen, comprobaciones documentales y limitaciones. No se accedió a bases de
datos ni se ejecutó publicación, geocodificación o despliegue.
