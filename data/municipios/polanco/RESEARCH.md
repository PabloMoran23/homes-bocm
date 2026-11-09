# Polanco — Cantabria — INE 39054

Verificación en vivo: 2026-11-09. Adaptador exclusivo de Polanco, sin cambios
compartidos ni dependencias nuevas. Se revisaron el contrato de `portal.py`, el
cargador de manifests y los ejemplos Hernani y Manlleu antes de implementarlo.

## Descubrimiento y fuente oficial

La portada municipal https://www.aytopolanco.org/ contiene el menú **Planeamiento**,
con diez fichas hijas. Es el inventario que recorre el adaptador, descubierto en
cada ejecución, sin fijar noticias individuales ni una lista estática de PDFs.
https://www.aytopolanco.org/planeamiento/ redirige a la ficha del PGOU; por ello no
se interpreta su cuerpo como el índice completo. Las fichas están bajo
https://www.aytopolanco.org/planeamiento/ y son:

| Ficha (ruta relativa) | Documentos únicos | Resultado |
| --- | ---: | --- |
| plan-general-de-ordenacion-urbana/ | 108 | Un PGOU, no 108 proyectos |
| modificacion-puntual-no-1/ | 34 | Un instrumento; incluye anuncio y corrección |
| modificacion-puntual-no-2/ | 2 | Un instrumento con dos tomos |
| modificacion-puntual-no-3/ | 3 | Un instrumento con informe y anuncio |
| modificacion-puntual-no-4/ | 3 | Un instrumento con informes |
| modificacion-puntual-no-5/ | 1 | Un instrumento |
| estudio-de-detalle-urb-8/ | 1 | Un instrumento |
| estudio-de-detalle-ua-p1/ | 2 | Un instrumento con informe ambiental |
| estudio-de-detalle-aam4/ | 1 | Un instrumento |
| plan-parcial-urb-10/ | 3 | Excluida por conflicto de identificación |

La última ficha titula «Plan Parcial URB-10», pero su contenido enlaza proyectos
de compensación. Dos archivos se llaman `P.-COMPENSACIÓN-URB-8.pdf` y
`MOD.-URB-8.-BOC-134.-13.07.2021.pdf`, mientras las etiquetas indican URB10.
No se presupone que correspondan al mismo instrumento. La exclusión y su URL
quedan explícitas en el resultado del adaptador y en `evidence/validation.json`;
la ficha completa queda capturada para revisión.

## Semántica y cobertura

Resultado real: **9 instrumentos y 155 enlaces PDF**, agrupados por ficha. Se
retienen título del documento, sección, página de procedencia, URL original y
URL HTTPS normalizada con espacios/caracteres codificados. No se generan
registros para formularios, contratación, noticias, planos, informes ni tomos
por separado. Los IDs derivan de la URL estable de la ficha, no de una fecha.

En la modificación 1, los enlaces de la sección «Aprobación Definitiva» indican
BOC extraordinario nº 5 de **2018-02-01**. La corrección de **2018-03-13** permanece
como documento separado del mismo instrumento. En la modificación 3, el enlace
«BOC NÚM. 156 de 14/08/2020. Aprobación definitiva» acredita la publicación
**2020-08-14**. Estas son fechas de publicación del anuncio BOC, no del acuerdo,
ni de publicación de la página web. `fecha_publicacion_tipo` lo declara.
`fecha`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas. En las demás fichas
no se atribuye fase ni fecha desde nombres de archivo, rutas de subida, fechas
WordPress o sellos de documentos no analizados. Las fechas identificables de
anuncios ambientales se guardan únicamente en el documento correspondiente.

Cobertura parcial: catálogo actualmente enlazado por el municipio, sin garantía
de histórico completo, modificaciones no enlazadas, registro de obras físicas o
expedientes de licencias. No se ha verificado un inventario público de licencias
concedidas: `licencias.enabled=false` y sus métodos escriben cero registros.
Los métodos update refrescan la instantánea completa; no usan marcas temporales
para descartar documentos antiguos. No hay paginación en las fuentes revisadas;
si aparecen controles de paginación, el adaptador falla expresamente. No se
limita el número de fichas ni de documentos. Cambios de estructura, ficha sin
PDF, redirecciones imprevistas o tipos nuevos fallan antes de sustituir la salida.

## Geometría

geometry_status: unavailable

La página oficial https://www.aytopolanco.org/galeria-geoportal/ enlaza dos visores
Citymap (callejero y urbanismo), con identificadores:

- https://citymap.tecnogeows.com/user/100958574317662245279/map/NHPmip4nWcTz8w6ULgFH3d
- https://citymap.tecnogeows.com/user/100958574317662245279/map/4JbGXzoGVEq5HK53X6UF4H

No se ha verificado una capa vectorial pública vinculable a cada ficha. Los
planos PDF no se vectorizan. Coordenadas y geometría nulas; sin centroides ni
coordenadas inventadas. `geocode.jitter_missing=false`, `publication_ready=false`
y `schedule.enabled=false`. El guard compartido anota los nueve registros como
entidades de tipo desconocido; no se ha forzado elegibilidad de actividad.

## Reproducción y evidencia local

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_polanco -v` — **7 pasan**. Cubren
descubrimiento y duplicados, documentos agrupados, semántica temporal, ausencia
de fechas/geometría, sector ambiguo, paginación, recorrido completo, actualización,
preservación de salida ante fallo y carga del manifest/licencias deshabilitadas.

Extracción real mediante `load_portal_adapter(load_manifest('polanco'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se configuró solamente
`capture_dir='evidence/live'` en esa ejecución para conservar respuestas HTML.
Timeout 35 segundos, pausa 0,2 segundos entre fichas. Salida escrita atómicamente.

Evidencias locales, fuera del commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live/*.html`, capturas iniciales del catálogo
y geoportal. Se comprueba una cabecera PDF por instrumento; los archivos
`*.pdf-prefix.bin` son muestras incompletas de 1024 bytes. Los demás enlaces se
retienen sin afirmar que todos sus destinos se hayan descargado o que el texto
PDF se haya analizado. El informe de validación recoge resultados HTTP, cantidad
real de registros, fuentes, exclusión y limitaciones. No hay publicación ni
acceso a servicios de despliegue o bases de datos.
