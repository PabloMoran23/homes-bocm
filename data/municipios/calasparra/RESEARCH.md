# Calasparra — Murcia — INE 30013

Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuentes oficiales descubiertas

La web municipal https://calasparra.org/ identifica al Ayuntamiento y enlaza el portal de transparencia, sección Urbanismo y Medio Ambiente: https://transparencia.calasparra.org/#!/urbanismo-obras-publicas-y-medio-ambiente . Ese portal cerró la conexión en la comprobación directa y no se usa para extraer registros.

El inventario municipal https://calasparra.org/urbanisme/ está indexado públicamente, pero devuelve HTTP 403 a requests desde este entorno. Su contenido actual sí responde HTTP 200 en la API pública del mismo Ayuntamiento:

https://calasparra.org/wp-json/wp/v2/pages?slug=urbanisme&per_page=100&page=1

La respuesta identifica la página publicada 59359, slug urbanisme y enlace canónico exacto. No se utiliza una copia del buscador como extracción. La fecha CMS de creación es 2020-06-15; no acredita la publicación ni aprobación de los instrumentos. Tampoco se deducen fechas de las carpetas de subida.

## Cobertura y agrupación

Se obtienen **15 registros y 29 enlaces PDF** del inventario actual:

- Normas subsidiarias: cuatro tomos, catálogo de edificación y cinco planos, un único registro con diez documentos.
- Once delimitaciones de núcleos rurales: La Estación FFCC, La Ñora, La Palmera, Las Reposaderas, Los Donates, Los Madriles, Los Marines, Milicianos, Milicianos Altos – Casa del Reloj, Valentín y El Reolid. Las tres hojas de Valentín se agrupan por núcleo, sin inventar expediente o fecha común.
- Plan parcial Riñales fase III: plan y parcelario; fase II: plan, en registro separado.
- Plan parcial Cañada Manrique fase II: plan, ordenanzas particulares y parcelario agrupados.

Se excluyen expresamente dos planos de parcelario Riñales fases I–II (normal y reducido), cuya relación con un solo instrumento no se ha establecido. Sus enlaces y motivo se conservan en validation.json. Los modelos de licencia, trámites electrónicos, noticias y anuncios de contratación no se convierten en proyectos ni licencias concedidas.

Cobertura parcial del inventario documental municipal, no registro histórico completo. Se conserva el título literal de cada documento, URL oficial, inventario de origen y API. Los títulos agrupados describen el instrumento o conjunto documental, no una aprobación. No se verifican vigencia, ejecución, fechas de acuerdos, fechas de publicación de cada instrumento ni geometrías. Todos los registros declaran publication_ready=false y geometry_status=unavailable. Licencias, programación automática y jitter de geocodificación están desactivados.

## Integridad y comprobación

La API declara X-WP-Total=1 y X-WP-TotalPages=1. El adaptador exige esos totales y una única página publicada con identidad correcta. Si aparecen más páginas, paginación interna, cambios de estructura, enlaces documentales ajenos al dominio o documentos sin clasificación, falla explícitamente antes de reemplazar la salida. No hay límite silencioso de registros. La actualización vuelve a extraer el inventario completo; no utiliza fechas CMS como cursor incremental.

Runtime empleado: /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python.

Pruebas: `-m unittest municipio.test_calasparra -v` (cinco pruebas). Verifican agrupación, aislamiento entre fases, procedencia, ausencia de fechas/posiciones inferidas, identificadores estables, fallo ante cambios y paginación, conservación de salida previa al fallar y carga desde manifiesto.

Extracción real mediante CalasparraAyuntamientoAdapter.backfill_proyectos, sin base de datos ni publicación. Evidencia local en evidence/proyectos.jsonl y evidence/validation.json; captura JSON y cabeceras de la respuesta efectiva en live-inventory.json y live-headers.json. Otras capturas documentan los sondeos iniciales.

Muestreo documental: CALAS-3.pdf y P-P-CAÑADA-MANRIQUE-FASE-II.pdf responden HTTP 200, application/pdf y firma %PDF válida. Se conservan solamente los primeros 1024 bytes de cada muestra (normas-prefix.bin y plan-prefix.bin). No se afirma haber descargado o validado íntegramente todos los PDF.
