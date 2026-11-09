# Ugao-Miraballes — Bizkaia — INE 48065

Verificación en vivo: 2026-11-09. Adaptador municipal específico, sin publicación.

## Descubrimiento y cobertura

Desde la página española del Ayuntamiento se consultó el menú público de servicios
(SharePoint REST, lectura anónima), que enlaza [Urbanismo](https://www.ugao-miraballes.eus/es-ES/Servicios/Urbanismo/Paginas/default.aspx).
Este inventario enlaza «Plan General de Ordenación Urbana - Aprobación definitiva»,
«Antecedentes» y «Convenios urbanísticos». El extractor descubre el enlace del
[PGOU](https://www.ugao-miraballes.eus/es-ES/Servicios/Urbanismo/Paginas/pgou-aprobacion-definitiva.aspx)
desde Urbanismo en cada ejecución, y recorre todas sus secciones enlazadas.

Resultado: **un instrumento real, el PGOU, con 115 documentos PDF**. Incluye
memorias (9), informes (3), planos de información (28), planos de ordenación (35),
evaluación ambiental (5), cartografía ambiental (28), perspectiva de género (6)
y estudio acústico (1). La web usa bibliotecas de texto refundido y una biblioteca
ambiental con ruta antigua; se conservan las URL efectivamente enlazadas, sin
reescribirlas a partir de los títulos. En concreto, la sección ambiental enlaza
28 planos de `aprobacion_definitiva_evaluacion_ambiental_estrate`, mientras
que REST también expone otros 28 en `apro_def_texto_redifundido_cartografia`.
No se presupone equivalencia: se extrae lo enlazado y se deja documentada esta
diferencia de versiones; los planos refundidos no enlazados quedan fuera. Los documentos no se convierten en proyectos
independientes. Se conservan título, URL y páginas de procedencia de cada documento.

La cobertura es deliberadamente **parcial**: solo el PGOU de aprobación definitiva.
El inventario REST de Urbanismo también muestra planes parciales (El Jaro, Usila,
Santi Laurenti), planes especiales, modificaciones de NNSS y antecedentes del PGOU;
no se extraen ni se presume su vigencia. No hay cobertura de obras o noticias,
contratación ni registro de licencias concedidas. Los formularios no son licencias.

Se investigó también el [catálogo oficial de Open Data Bizkaia](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-ugao-miraballes).
Sus datos globales trimestrales son agregados estadísticos de suelo/viviendas y
su inventario de núcleos rurales describe asentamientos: no se crean proyectos
con esas filas ni se reutilizan sus puntos como geometría del PGOU.

## Fechas, documentos y geometría

La fase procede del título municipal «Aprobación definitiva». Las páginas extraídas
no acreditan las fechas del acuerdo, aprobación ni publicación: `fecha`,
`fecha_acuerdo`, `fecha_aprob` y `fecha_publicacion` quedan nulas. Las fechas
SharePoint de creación/modificación no se interpretan como fechas administrativas.
Los PDF se enlazan como documentos del PGOU; no se interpreta automáticamente
su contenido ni se deducen fechas a partir de sus nombres.

`geometry_status: unavailable`. Hay planos PDF, pero no se ha verificado geometría
vectorial asociada al instrumento. `geometry`, `lat` y `lon` nulos y
`publication_ready: false`; sin centroides inventados ni jitter.

## Paginación y validación reproducible

La web sí pagina: planos hasta `?page=7`, evaluación ambiental hasta `?page=6`.
Se recorren todos los enlaces de sección y página hasta agotar el conjunto,
incluidas las páginas numeradas y «>». Se deduplican documentos por URL,
conservando sus índices de procedencia. No hay corte silencioso: una expansión
superior a 100 páginas, paginación fuera del ámbito, error HTTP, ausencia de enlace
del PGOU o ausencia de documentos abortan antes de sustituir la salida.

Tres pruebas con `unittest` cubren agrupación y duplicados entre secciones,
documentos de la segunda página, fechas/geometría nulas, exclusión de enlaces
externos/formularios, cambios de fuente, paginación no soportada, conservación de
salida anterior tras fallo y licencias deshabilitadas.

Comando ejecutado:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ugao_miraballes -v
```

La extracción real usó `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, sin orquestador.
Se contrastaron las URL extraídas con los ocho directorios públicos SharePoint
efectivamente enlazados y se descargó un PDF del programa económico para verificar su
contenido PDF. Evidencias locales: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML de todas las páginas recorridas,
respuestas REST y `programa-estudio-ecfin.pdf`. No se incorporan al código fuente.

`schedule.enabled: false`, `licencias.enabled: false`,
`geocode.jitter_missing: false`. Las actualizaciones refrescan la misma instantánea
completa del PGOU y no afirman cubrir todo el urbanismo municipal.
