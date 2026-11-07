# Alcalá la Real (Jaén, INE 23002)

Investigación y prueba local: 2026-11-07. Estado: adapter verificable para integración
como código; refresco deshabilitado. No se ha publicado ni sincronizado información.

## Fuentes oficiales y extracción

- https://alcalalareal.es/urbanismo-y-patrimonio-municipal/ — HTTP 200 en prueba directa.
- https://transparencia.alcalalareal.es/obras-publicas-y-urbanismo/ — índice de transparencia.
- https://transparencia.alcalalareal.es/obras-publicas-y-urbanismo/modificaciones-del-pgou/ — documentación de planeamiento.

La página municipal contiene paneles HTML `vc_tta-panel` con procedimientos
individualizados. El adapter obtiene una página por snapshot y selecciona paneles
cuyo encabezado comienza por Plan Parcial o Plan Especial y cuyo cuerpo describe
información pública o consulta. Excluye el índice general del PGOU, información de
contacto, reglamentos y formularios. Conserva el texto de procedencia, enlace al
panel y documentos; los enlaces a sede para alegaciones no son documentos.
La pérdida de estructura o ausencia de expedientes causa error, no un éxito vacío.

Resultado de ejecución directa de `backfill_proyectos`: **3 proyectos**, **0 licencias**:

| Proyecto real publicado | Fecha del acuerdo explícita | Documentos enlazados |
| --- | --- | --- |
| Plan Parcial de Ordenación NS-2.1 | 2025-04-08 | 1 |
| Plan Especial Reforma Interior Sector UE-SA7 | No indicada | 2 |
| Plan parcial de ordenación del sector S-8 | 2026-07-21 | 5 |

Las fechas son acuerdos, no fechas de publicación: se exportan como `fecha_acuerdo`.
`fecha` queda nula y no se inventa fecha a partir de rutas de subida, leyes citadas
o fecha de lectura. Los identificadores dependen del título normalizado y son
estables entre ejecuciones con el mismo nombre. Un cambio del título podría
requerir reconciliación manual. Los documentos relacionados no se cuentan como
proyectos adicionales. El update vuelve a obtener la instantánea de esta página;
no representa un histórico completo de todos los instrumentos municipales.

Documentos concretos observados:
- NS-2.1: http://gofile.me/6VvP8/7pVPmLme3
- UE-SA7: https://aytoalcala.synology.me:5001/d/s/13dFP6BdggWnVxxHYT9oSskklVeaJ2zI/_eOoEQoofuXwfIm1wkC_a9NdikoO3s64-qrjgBkyEVAw
- S-8: https://alcalalareal.es/wp-content/uploads/2026/07/20260724_Otros_68.1PlanParcial.pdf

Son enlaces publicados por el ayuntamiento; el adapter conserva su procedencia,
pero no descarga ni verifica el contenido de cada PDF o almacenamiento Synology.

## Licencias

La web describe competencias de licencias y ofrece canales de tramitación, pero no
se ha verificado un registro estructurado de concesiones. `licencias.enabled: false`;
los métodos de licencias generan una lista vacía, sin convertir formularios en
licencias concedidas.

## Geometría / visor

- geometry_status: unavailable
- Fuentes revisadas: página municipal de urbanismo y resultados de búsqueda de
  `Alcalá la Real visor urbanístico GIS WFS geoportal` y búsqueda restringida al
  dominio oficial con `visor urbanismo`.
- El planeamiento municipal enlaza planos PDF; no se identificó un WFS, ArcGIS o
  GeoJSON público asociado inequívocamente a estos tres expedientes. Esta búsqueda
  no demuestra inexistencia de otros servicios. No se ha vectorizado cartografía PDF.
- No se exportan `lat`, `lon`, `geom_geojson` ni CRS porque no hay geometría verificada.
  `geocode.jitter_missing: false` evita suplirla con puntos del centro municipal.
- La validación de publicación que exige coordenadas no se satisface con este
  snapshot. Ello no impide integrar el código deshabilitado; obtener geografía real
  y revisar cobertura son tareas previas a activar su publicación.

## Validación y aislamiento

- Import del adapter y extracción directa limitada a timeout HTTP de 30 segundos:
  3 proyectos, 0 licencias; únicamente archivos temporales locales.
- Pruebas de fixture: exclusión de formularios, acuerdo frente a publicación,
  ausencia de fechas inventadas, ausencia de coordenadas inventadas, fallo ante
  cambio de estructura e identificadores deterministas.
- `schedule.enabled: false`: fuera del refresco programado. No se ejecutaron
  orquestador, `--step all`, geocode, sync, operaciones DB ni cambios de cola.
