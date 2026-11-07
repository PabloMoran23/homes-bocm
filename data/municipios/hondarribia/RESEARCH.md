# Hondarribia — INE 20036, Gipuzkoa

Verificación en vivo: 2026-11-07. Adaptador: `HondarribiaAyuntamientoAdapter`.

## Descubrimiento y cobertura

La [portada municipal](https://www.hondarribia.eus/es/) enlaza
[Urbanismo](https://www.hondarribia.eus/es/urbanismo), que enlaza el inventario
[Recursos Geográficos y de Urbanismo](https://www.hondarribia.eus/es/recursos-geograficos-urbanismo).
Se revisaron también [Planes y Proyectos](https://www.hondarribia.eus/es/planes-proyectos),
[HAPO](https://www.hondarribia.eus/es/hapo), el planeamiento vigente y la cartografía.
Las páginas fueron accesibles mediante requests (HTTP 200); el buscador web tenía
restricciones robots para algunas páginas, sin impedir la extracción HTTP real.

El scraper vuelve a consultar el inventario en cada ejecución y exige que sigan
presentes los dos instrumentos cubiertos. No utiliza noticias como registros.
Extrae **2 instrumentos y 115 enlaces documentales**, agrupados así:

* **Nuevo PGOU, aprobación provisional:** [colección técnica](https://www.hondarribia.eus/es/hapo/contenido-aprobacion-provisional-plan)
  y [información pública y documentos](https://www.hondarribia.eus/es/hapo/documentacion-recursos),
  esta última descubierta mediante el menú de la colección técnica. **100 documentos**
  en un solo registro: memorias, planos, normas, ZIP, acuerdos, alegaciones,
  evaluaciones, informes y materiales participativos. La narrativa explícita dice
  que el Pleno acordó la aprobación provisional el **19 de junio de 2025**:
  `fecha_acuerdo` y `fecha_aprob` = 2025-06-19. El enlace «30-06-2025 Anuncio en
  el BOG de la aprobación provisional del PGOU» acredita `fecha_publicacion` =
  2025-06-30 para ese anuncio. No es la fecha de publicación HTML ni la de todos
  los documentos. `fecha` genérica permanece nula. Los informes COTPV de marzo y
  julio de 2026 y la corrección de julio de 2026 se retienen con sus rótulos,
  sin convertir el «informe definitivo» en aprobación definitiva del PGOU.
* **[Plan Director Muralla de Hondarribia](https://www.hondarribia.eus/es/plan-director-muralla-hondarribia):**
  **15 documentos** de fases 1, 2 y 3, con `seccion` para preservar la fase
  documental incluso en títulos repetidos como «Memoria» y «Planos».
  No se atribuyen aprobación, publicación ni estado de ejecución a las obras.

Cada documento conserva título, URL con versión/query publicado y `source_url` de
la página que lo enlaza. La deduplicación dentro de cada colección usa el UUID
Liferay del archivo; IDs de los instrumentos estables e independientes de fechas.
Los enlaces documentales no generan proyectos adicionales.

**Cobertura parcial deliberada.** El inventario también enlaza el PGOU antiguo
«Formalmente no vigente», el [planeamiento vigente](https://www.hondarribia.eus/es/normas-subsidiarias-vigentes)
(NNSS, modificaciones, planes y estudios de detalle), convenios, cartografía y un
estudio hidráulico de Mendelu. No se extraen en esta versión. No se afirma cubrir
todas las obras, todo el planeamiento, ni un histórico de expedientes municipal.
No se han verificado licencias concedidas: extracción deshabilitada y vacía.
Las ordenanzas, campañas y formularios no se convierten en proyectos/licencias.

## Paginación y cambios de fuente

Las cuatro páginas consultadas por el adaptador presentan listas documentales
estáticas completas, sin paginación activa ni límite de resultados aplicado.
El parser rechaza controles de siguiente página y parámetros de paginación
reconocidos, en vez de aceptar una primera página truncada. Cambios futuros a
paginación, desaparición de inventario, narrativa de aprobación o documentos
provocan error y requieren revisión. Las actualizaciones son snapshots completos;
no se atribuye significado de baja a registros ausentes ni se mantiene estado
incremental. La fase provisional está vinculada a esta colección concreta;
una futura colección de aprobación definitiva requerirá ampliar el alcance.

## Geometría

`geometry_status: unavailable`. La [cartografía municipal](https://www.hondarribia.eus/es/cartografia)
publica cartografía base DWG/DGN, bases UTM ETRS89, ortofotos y GeoHondarribia.
No se verificó una geometría vectorial enlazable a estos dos instrumentos.
Los planos PDF/ZIP se conservan como fuentes, sin convertirlos en polígonos.
`lat`, `lon` y `geometry` nulos; `publication_ready: false`.
No se inventan coordenadas ni CRS; `geocode.jitter_missing: false`.

## Validación y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_hondarribia -v
```

Cinco pruebas offline: descubrimiento de ambos instrumentos, fechas semánticas,
agrupación/deduplicación/proveniencia, rechazo de paginación/fuentes inválidas,
manifest y licencias deshabilitadas. La extracción real se ejecutó mediante
`HondarribiaAyuntamientoAdapter('hondarribia', {'capture_dir': 'evidence/live'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local sin incorporar a fuentes: `evidence/proyectos.jsonl` (2 registros),
`evidence/validation.json` (conteo, URLs, limitaciones, pruebas y comprobaciones
PDF), HTML originales en `evidence/live/` y capturas de descubrimiento en
`evidence/`. Se descargaron para comprobar contenido PDF el anuncio BOG, el resumen
ejecutivo del PGOU y el cuadro de inversiones de la Muralla. El resto de binarios
están enlazados, sin descarga/interpretación individual; sus fechas de contenido
no se infieren. La extracción depende de las páginas oficiales vivas.

`schedule.enabled: false`, `licencias.enabled: false`. Sin cambios compartidos,
dependencias nuevas, publicación, base de datos ni despliegue.
