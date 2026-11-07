# Calatayud — INE 50067

Prueba 2026-11-07. Instrumentos actuales publicados en el inventario municipal.

## Fuente y extracción

https://www.calatayud.es/urbanismo — HTTP200.
Se descubren tres páginas oficiales desde la sección y su navegación: PGOU,
anteproyecto de urbanización Marivella y Plan Especial de Reforma Interior y
Protección del Conjunto Histórico Artístico. Cada página se descarga, verifica
encabezado e inventaría los adjuntos `/admin/resources/planos/` publicados.

Resultado directo: **3 instrumentos, 18 documentos únicos por instrumento** (7PGOU,
8Marivella,3PERI), **0 licencias**. Se agrupan documentos y se eliminan enlaces
repetidos «archivos adjuntos»/título. PDF, planos JPG y anexos no son proyectos
separados. Las páginas son inventarios actuales, no noticias puntuales fijadas.
No se inventan fecha completa, descripción duplicando título ni estado de ejecución.
El alcance es cada instrumento publicado, no todas sus fases/cambios históricos.

Páginas obtenidas:
- https://www.calatayud.es/urbanismo/plan_general_ordenacion_urbana
- https://www.calatayud.es/urbanismo/anteproyecto_marivella
- https://www.calatayud.es/urbanismo/plan_especial_reforma_interior

La página declara codificación HTML que se respeta pasando bytes al parser;
`requests.text` interpretaba incorrectamente algunos acentos. Corregido y repetida
extracción: los tres títulos se reconocen sin pérdida de instrumentos.

## Geometría / visor

geometry_status: unavailable

El ayuntamiento enlaza SIUA Aragón:
https://icearagon.aragon.es/SIUa/archivo/buscador?MUNICIPIO=Calatayud
Los inventarios municipales contienen documentos/plano PDF/JPG, sin polígonos o
endpoint vectorial ligado a las tres fichas. No se vectorizó cartografía ni se
utilizó centroide municipal. Queda pendiente vincular los ámbitos a geometría real.

## Validación

2 pruebas pasan: descubrimiento y deduplicación, agrupación de documentos, fallo
ante documentos ausentes. Extracción timeout25s y pausa0,35s. Límite30 instrumentos
con fallo, no truncamiento; inventarios revisados sin paginación. Evidencias en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/calatayud/`.
`schedule.enabled: false`, licencias deshabilitadas, `geocode.jitter_missing: false`.
Sin orquestador/DB/publicación/cola. Falta geografía para validación de publicación.
