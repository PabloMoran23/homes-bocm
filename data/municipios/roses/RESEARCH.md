# Roses — INE 17152

Prueba 2026-11-07. Alcance: planes parciales y modificaciones vigentes del inventario.

## Fuente oficial

https://www.roses.cat/la-vila/urbanisme/planejament/planejament-vigent/plans-parcials-pgou
HTTP200. Plone publica fichas individuales con descripción/fecha de aprobación y
sus PDF. El adapter descubre cada ficha, sigue paginación `listingNext` si existe
(máximo20 páginas, error ante ciclo/truncamiento), descarga detalles y documentos
como enlaces fuente. No cuenta cada documento como un instrumento distinto.

Resultado directo: **4 instrumentos reales, 0 licencias**: dos modificaciones del
sector Canigó/Santa Margarida (1984 y 1998, distintos actos), Els Grecs II y Marés.
Las fechas de aprobación aparecen expresamente en el inventario; se exportan como
`fecha_aprobacion`, no publicación. No se completan datos ausentes ni se infiere
concesión de obras. Los títulos y fechas son fuente municipal. El resto del
planeamiento general/especial y obras está fuera del alcance de este adapter.

## Geometría / visor

geometry_status: unavailable

Se inspeccionó https://www.roses.cat/la-vila/urbanisme/gis/enllacos-dinteres y sus
referencias reales al visor urbanístico y servidor de mapas:
- http://eajuntament.roses.cat:8080/geoexplorer/gdviewer?lang=ca — ConnectTimeout tras10s.
- http://delta.icc.es/ideLocal/IdecServ?codi=171523&tipus=u — ConnectionError.
Las fichas de plan contienen PDF, sin geometría vectorial directamente enlazada.
No se usan puntos del centro municipal ni se fabrican polígonos.

## Validación

2 pruebas pasan: separación aprobación/publicación, paginación detectada y fallo
ante estructura ausente. Import y check estático válidos. Prueba HTTP timeout25s y
pausa0,35s; JSONL/informe en `/home/pablo/homes/artifacts/municipio-local-batches-20261107/roses/`.
`schedule.enabled: false`, licencias deshabilitadas, `geocode.jitter_missing: false`.
Sin orquestador/DB/publicación/cola. Pendiente cartografía para controles de publicación.
