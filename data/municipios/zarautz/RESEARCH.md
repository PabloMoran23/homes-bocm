# Zarautz — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://www.zarautz.eus |
| Urbanismo e medio ambiente | https://www.zarautz.eus/es/-/hirigintza-eta-ingurumena |
| Registro DUE Gipuzkoa (API) | https://w390w.gipuzkoa.net/WAS/CORP/DUERegistroPlaneamientoWEB/api/record/?municipality=zarautz |
| Índice documental B5M | https://b5m.gipuzkoa.eus/planeamiento/GHE-{n}/INDICE_GHE-{n}.html |
| Egoitza UZT (tramites, ayto 79) | https://uzt.gipuzkoa.eus/WAS/AYTO/USCServicioCiudadanoVer15WEB/home.do?ayto=79 |
| Sede CA079 (enlace De=CA079) | https://uzt.gipuzkoa.eus/home.do?De=CA079 |
| Exposición pública provincial | https://udal.egoitza.gipuzkoa.eus?De=07915 |

## Proyectos / planeamiento

- La **API REST del Registro DUE** devuelve JSON (`resultadoBusqueda[]`) con expedientes de planeamiento del término (90 registros en nov-2026): `registration_number`, `title`, `checkin_date`, `inscription_date`, `links` → índice B5M por código GHE.
- La web municipal enlaza revisión del **ZHAPO** (plan general) pero no publica tabla scrapeable equivalente a Errenteria; la fuente determinista es la API DUE.

## Licencias de obra

- No hay listado público de licencias concedidas en www.zarautz.eus.
- **UZT (ayto=79)** expone trámites informativos de obra (obra txikia/handia, aurrekomunikatutako obrak, lizentziak, zatikatzea, etc.) vía `fncValoresAction(id)` → `segundaPag.do?ayto=79&elemento={id}`.
- **Exposición pública** provincial (`udal.egoitza.gipuzkoa.eus?De=07915`) requiere navegación en sede sin API scrapeable en esta run.
- Estrategia: filas informativas de trámites UZT relacionados con obra/licencia (patrón Errenteria/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** API DUE (solo metadatos + enlaces B5M HTML/PDF), sede UZT, página urbanismo Liferay, tablón provincial.
- **Estrategia:** no hay ArcGIS MapServer/WFS público del ayuntamiento con campo GHE o código de expediente enlazable; los documentos B5M son índices HTML/PDF sin geometría machine-readable.
- **Limitaciones:** el orquestador usará centroide municipal (`43.2857, -2.1748`) + jitter para coordenadas.

## Limitaciones generales

- CMS: Liferay Portal; sede en dominios Gipuzkoa (`uzt`, `udal.egoitza`).
- Sin boletín autonómico asociado en cola (`bocm_count: 0`, `boletin_source_id` ausente).
