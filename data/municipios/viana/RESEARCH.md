# Viana — Navarra — INE 31251

Verificación y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y alcance

El inventario oficial elegido es [Plan de recuperación, transformación y
resiliencia](https://www.viana.es/plan-de-recuperacion-transformacion-y-resiliencia/),
enlazado desde los destacados de la web municipal. La sección **DUS 5000** enumera
actuaciones físicas concretas; no es una lista de licitaciones. Se recorre toda esa
lista, incluyendo entradas sin enlace. No se extraen el plan antifraude, la
modernización digital del servicio social ni el apartado Camino de Santiago:
cobertura deliberadamente parcial de DUS 5000, no del conjunto PRTR ni municipal.

Resultado real: **3 proyectos**:

- Renovación del alumbrado público: [ficha municipal](https://www.viana.es/prtyr-dus5000-alumbrado/).
  Describe sustitución de luminarias y reforma de cuadros. Identificador de ayuda
  publicado: PR-D5000-2021-000177. Conserva el [Plan Estratégico adjunto](https://www.viana.es/wp-content/uploads/2024/03/Plan-Estrategico.pdf).
- Instalación de generación térmica mediante aerotermia para la Casa Consistorial:
  título publicado en inventario, sin enlace de detalle. No se atribuye estado de
  ejecución, presupuesto ni fecha a esta entrada.
- Reforma de la envolvente térmica del Colegio Público Ricardo Campano e IESO El
  Camino: [ficha municipal](https://www.viana.es/reforma_envolvente_colegio/).
  Describe fachadas, cubierta y huecos. Identificador de ayuda publicado:
  PR-D5000-2021-002112.

Las fichas describen proyectos físicos y financiación. No se deduce que las obras
estén terminadas ni que las ayudas sean licencias. Las fechas de solicitud y de
resolución IDAE se conservan dentro de `descripcion` con su contexto; no se asignan
a `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob`. No hay fecha municipal de
publicación verificada. `expediente_ayuda` identifica financiación, no una licencia.

Cada actuación produce un registro con inventario, ficha y PDF adjunto agrupados en
`documentos`; el PDF no produce un cuarto proyecto. La descripción conserva texto
de la fuente, incluidos errores tipográficos. Los IDs se derivan de URL de ficha,
o de título para la actuación sin ficha, y no del orden de la lista. Una futura
renominación de la entrada sin ficha requerirá revisar su identidad.

## Otras fuentes oficiales revisadas

- [Transparencia: planeamiento](https://www.viana.es/transparencia/urbanismo-obras-publicas-y-medioambiente/planes-de-ordenacion-urbana-y-convenios-urbanisticos/):
  contiene etiquetas genéricas y un enlace a la normativa del Plan Municipal en
  [BON 104 de 2003](https://bon.navarra.es/es/anuncio/-/texto/2003/104/47).
  No ofrece un inventario completo actual de modificaciones. No se extrae aquí.
- [Anuncios y licitaciones de obras](https://www.viana.es/transparencia/urbanismo-obras-publicas-y-medioambiente/anuncios-y-licitaciones-de-obras-publicas/):
  etiquetas genéricas sin inventario usable de proyectos en la página revisada.
- [Tablón municipal antiguo](https://www.viana.es/actualidad/tablon/): indica
  expresamente histórico hasta 29/9/2023 y remite al
  [tablón de la sede](https://sedeelectronica.viana.es/tablondeanuncios/).
  La sede es accesible; sus anuncios generales no se interpretan como licencias
  concedidas ni como proyectos. Ninguno de estos tablones forma parte del scraper.

## Geometría y cobertura temporal

`geometry_status: unavailable`. Las fuentes seleccionadas no proporcionan una
geometría vectorial vinculada a estas actuaciones. No se geocodifican edificios,
no se inventan puntos ni se usa el centroide municipal. `publication_ready: false`.

Se obtiene una instantánea del inventario publicado en la actualidad, que puede
contener actuaciones históricas; no es un seguimiento de obras vigentes. No hay
paginación en esta lista. Si aparecen controles o enlaces de paginación, el
extractor falla explícitamente y exige revisión. No hay límite de registros ni
corte silencioso. Entradas DUS desconocidas, sección vacía, ficha sin descripción
de proyecto y errores HTTP también fallan antes de sustituir la salida existente.
`update_proyectos` repite la instantánea completa; no afirma cubrir bajas ni archivo.

## Validación y evidencias locales

`python -m unittest municipio.test_viana -v`: **3 pruebas pasan**. Verifican ámbito,
deduplicación, agrupación de documentos, ausencia de fechas inferidas/coordenadas,
rechazo de paginación/cambios de formato, resolución del manifest, actualización,
licencias desactivadas y conservación de salida ante fallo de detalle.

Extracción real mediante `load_portal_adapter(load_manifest('viana'))` y
`backfill_proyectos`: **3 registros**. Evidencias no versionadas en `evidence/`:
`proyectos.jsonl`, `validation.json`, HTML de descubrimiento, capturas HTML de cada
fuente extraída y PDF adjunto. El validador común de entidades devuelve estado
`ok`, pero clasifica las tres entidades como `unknown`: no se confunde esta
clasificación con un cambio del tipo de obra ni con permiso de publicación.

Manifest: licencias deshabilitadas, `schedule.enabled: false` y
`geocode.jitter_missing: false`. Sin cambios compartidos, dependencias ni despliegue.
