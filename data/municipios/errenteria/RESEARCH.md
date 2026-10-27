# Errenteria — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://errenteria.eus |
| Planeamiento (tabla WP) | https://errenteria.eus/udala/planak-eta-proiektuak/hirigintza-garapenerako-planeamendua/ |
| Registro DUE Gipuzkoa (API) | https://w390w.gipuzkoa.net/WAS/CORP/DUERegistroPlaneamientoWEB/api/record/?municipality=errenteria |
| Índice documental B5M | https://b5m.gipuzkoa.eus/planeamiento/GHE-{n}/INDICE_GHE-{n}.html |
| Egoitza UZT (tramites, ayto 67) | https://uzt.gipuzkoa.eus/WAS/AYTO/USCServicioCiudadanoVer15WEB/home.do?ayto=67 |
| Iragarki taula (tablón provincial) | https://udal.egoitza.gipuzkoa.eus?De=eu06715 |
| HAPO / GIS municipal | https://errenteria.eus/hapo/orokorra/ |
| HAP / PGOU | https://errenteria.eus/hapos/orokorra/ |

## Proyectos / planeamiento

- La página **Hirigintza-garapenerako planeamendua** renderiza una tabla HTML (`errenteria-hirigintza-planeamendua`) con título, fecha, código GHE y enlace al índice B5M.
- La **API REST del Registro DUE** devuelve JSON (`resultadoBusqueda[]`) con los mismos expedientes (59 registros en oct-2026): `registration_number`, `title`, `checkin_date`, `inscription_date`, `links`.
- Estrategia del adapter: ingestar desde la API DUE (determinista, sin paginación).

## Licencias de obra

- No hay listado público de licencias concedidas en la web municipal.
- **UZT** expone trámites informativos (obra txikia/handia, lehen erabiler, lur betelan, etc.) vía `fncValoresAction(id)` → `segundaPag.do?ayto=67&elemento={id}`.
- El **tablón provincial** (`udal.egoitza.gipuzkoa.eus`) puede publicar anuncios de licencias, pero el listado requiere navegación en sede provincial (sin API scrapeable en esta run).
- Estrategia: filas informativas de trámites UZT relacionados con obra/licencia (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** HAPO (páginas informativas y cartografía base), índices B5M (HTML/PDF), API DUE (solo metadatos).
- **Estrategia:** no hay ArcGIS MapServer/WFS público con campo `GHE` o código de expediente enlazable; los documentos de planeamiento son PDF/HTML sin geometría machine-readable.
- **Limitaciones:** el orquestador usará centroide municipal (`43.3113, -1.9025`) + jitter para coordenadas.

## Limitaciones generales

- CMS: WordPress + Acorn (Laravel); tablón y sede en dominios Gipuzkoa (`uzt`, `udal.egoitza`).
- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
