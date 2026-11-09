# Plentzia — INE 48077, Bizkaia

Verificación en vivo: 2026-11-09. Cobertura parcial: **un PGOU en elaboración**,
con dos documentos agrupados. No es un censo de proyectos ejecutados, ni acredita
aprobación del PGOU o concesión de licencias.

## Descubrimiento y procedencia

- Web municipal: https://www.plentzia.eus/es-ES/Paginas/default.aspx — HTTP 200,
  pero el HTML recuperado muestra la estructura de SharePoint sin un inventario
  urbanístico aprovechable. Captura local `evidence/home.html`.
- Catálogo oficial de la Diputación Foral de Bizkaia:
  https://www.opendatabizkaia.eus/es/organizacion/plentzia/catalogo/planeamiento-urbanistico-plentzia
  — HTTP 200. Ofrece datos globales de planeamiento 2023–2026 y 2019–2022,
  y calificación pormenorizada 2019–2022. La ficha advierte de su carácter
  orientativo. Se revisó la ficha, sin convertir sus recursos agregados en
  proyectos ni atribuirles geometría de un instrumento. `evidence/catalog.html`.
- Portal específico: https://plentziaplanorokorra.eus/ — HTTP 200. Localizado
  mediante búsqueda pública de PGOU y urbanismo municipal. La presentación está
  firmada por Aitor Garagarza Cambra como alcalde de Plentzia y explica que el
  Ayuntamiento implementa esta web para la participación en el PGOU. El pie
  enlaza la web del Ayuntamiento e identifica al equipo redactor (Territorio y
  Ciudad y TAPER Arkitektura). Es un portal promovido por el Ayuntamiento,
  alojado en dominio propio y mantenido por el equipo redactor; no se describe
  como sede electrónica ni como registro administrativo. `evidence/pgou.html`.

## Inventario implementado

Se lee la sección `#documentos` del portal del PGOU, no noticias ni anuncios de
contratación. El título original es «PGOU Plentzia». El marcador explícito
«FASE ACTUAL: 1» se conserva como fase: la web describe esa etapa como análisis,
diagnóstico y participación. El resto de las pestañas explica fases futuras y
**no** prueba que el plan esté aprobado. El identificador local `plentzia-pgou`
agrupa el instrumento y no se presenta como número de expediente oficial.

Documentos descubiertos y descargados en la extracción real:

1. Manual de participación, bilingüe:
   https://plentziaplanorokorra.eus/wp-content/uploads/2026/06/PLENTZIA-MANUAL_merged.pdf
2. Programa de participación ciudadana del PGOU de Plentzia:
   https://plentziaplanorokorra.eus/wp-content/uploads/2026/06/PT-PPC-Plentzia-cas.pdf

Los PDF se inspeccionaron con `pdftotext`. El programa identifica expresamente
su objeto como organizar la participación en la redacción del PGOU de Plentzia;
el manual explica el futuro plan y sus mecanismos de participación. Son
documentos de apoyo de un instrumento real en elaboración; no generan dos
proyectos separados. Se guardan título, URL del documento, sección de
procedencia, tamaño y SHA-256 de cada descarga. Las versiones repetidas de los
enlaces «Descarga» y los enlaces con fragmentos se deduplican por URL.

La plantilla contiene además un enlace vacío a un PDF de Peñaflor: se excluye
porque no pertenece a un bloque de documento nombrado del inventario de
Plentzia. Los enlaces externos inesperados dentro de bloques documentales
provocan un error, al igual que nuevos enlaces nombrados sin interpretar.

## Fechas, geometría y límites

No hay fecha de publicación o acuerdo verificada para el PGOU en elaboración.
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulas. Ni el directorio
de subida `2026/06`, ni la fecha HTTP de modificación de un fichero prueban un
acto administrativo. La fecha de aprobación de las antiguas Normas Subsidiarias
mencionada en la presentación tampoco se traslada al PGOU nuevo.

`geometry_status: unavailable`: no se ha verificado geometría vectorial vinculada
a este instrumento. No se crean coordenadas, centroides, CRS ni jitter.
`publication_ready: false`. No se extraen licencias: no se ha verificado un
registro público de concesiones. Tampoco se convierten formularios, contratación
del equipo redactor o referencias a estudios dentro de los PDF en actuaciones.

El inventario observado es una sección íntegra sin paginación. El parser rechaza
enlaces de siguiente página, parámetros de página y contenedores habituales de
paginación, en lugar de aceptar una extracción truncada. Rechaza también cambios
de identidad, ausencia de sección/fase/documentos, descargas que no sean PDF y
redirecciones fuera del dominio de procedencia. Las escrituras de proyectos son
atómicas y solo ocurren después de comprobar todas las descargas. Los métodos
incrementales vuelven a leer la instantánea actual; no reconstruyen documentos
retirados ni el histórico de otros instrumentos de Plentzia.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_plentzia -v` con ese runtime:
**6 pruebas pasan**. Cubren agrupación y exclusiones, fechas sin inferencia,
lectura de fase actual, cambios de fuente/paginación, descargas inválidas,
preservación de salida ante fallo y restricciones del manifest/licencias.

Extracción real: cargar `load_manifest('plentzia')`, importar la clase indicada
en `portal.adapter`, construirla con slug/config/base_url y ejecutar únicamente
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La validación utilizó
`config['evidence_dir']` para conservar además las respuestas originales.
Resultado: **1 registro, 2 PDF descargados**. `evidence/validation.json` contiene
el momento de consulta, `live_records`, `source_urls` y las limitaciones.
`evidence/documento-*.pdf` conserva los bytes descargados por el adaptador.
Estas evidencias son locales y no forman parte de los cuatro archivos fuente.

El manifest mantiene `schedule.enabled: false`, `licencias.enabled: false` y
`geocode.jitter_missing: false`. No se han ejecutado publicación, despliegues,
base de datos ni orquestador completo.
