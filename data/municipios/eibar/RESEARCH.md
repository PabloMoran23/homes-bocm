# Eibar — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Plone) | https://www.eibar.eus |
| Planeamiento | https://www.eibar.eus/es/ayuntamiento/planeamiento |
| Normativa en tramitación | https://www.eibar.eus/es/ayuntamiento/documentacion-en-exposicion-publica |
| PGOU (documentación histórica) | https://www.eibar.eus/pgou/aurkibidea.htm |
| Registro DUE Gipuzkoa (API) | https://w390w.gipuzkoa.net/WAS/CORP/DUERegistroPlaneamientoWEB/api/record/?municipality=eibar |
| Índice documental B5M | https://b5m.gipuzkoa.eus/planeamiento/GHE-{n}/INDICE_GHE-{n}.html |
| Sede UZT (ayto 30) | https://uzt.gipuzkoa.eus/WAS/AYTO/USCServicioCiudadanoVer15WEB/home.do?ayto=30 |
| Trámites urbanismo (Plone) | https://www.eibar.eus/es/tramites/tramites-servicios |
| Tablón provincial | https://erakunde.egoitza.gipuzkoa.eus?De=03015 |
| IDE Gipuzkoa (b5m) | https://b5m.gipuzkoa.eus/web5000/es |

## Proyectos / planeamiento

- La **API REST del Registro DUE** devuelve JSON (`resultadoBusqueda[]`) con expedientes de planeamiento del municipio (~40 registros): `registration_number` (GHE), `title`, fechas, enlace al índice B5M.
- La sección municipal **Planeamiento urbanístico** agrupa PGOU vigente, revisiones y modificaciones puntuales (Plone, sin API).
- **Documentación en exposición pública** no lista expedientes estructurados en HTML scrapeable (contenedor vacío en nov-2026).
- Estrategia del adapter: ingestar proyectos desde la API DUE (determinista).

## Licencias de obra

- No hay listado público de licencias concedidas en la web municipal.
- **Trámites Plone** bajo `urbanismo/` describen licencias/comunicaciones de obra, actividad, ocupación de vía, ITE, etc. (páginas informativas, no concesiones).
- La **sede UZT** de Eibar (`ayto=30`) expone recibos, padrón y validación de documentos; no incluye el bloque de trámites de obra visible en otros municipios (p. ej. Errenteria).
- El **tablón provincial** (`erakunde.egoitza.gipuzkoa.eus?De=03015`) puede publicar anuncios; sin API scrapeable en esta run.
- Estrategia: filas informativas desde enlaces Plone de urbanismo + enlace al tablón provincial.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** API DUE (solo metadatos), índices B5M (HTML/PDF), PGOU en PDF (`/pgou/`), capas regionales geo.euskadi.eus (PTP / planeamiento sin campo GHE enlazable al expediente).
- **Estrategia:** no hay MapServer/WFS municipal con código GHE o expediente queryable; documentación cartográfica en PDF.
- **Limitaciones:** el orquestador usará centroide municipal (`43.1847, -2.4719`) + jitter para coordenadas.

## Limitaciones generales

- CMS: Plone; sede y tablón en dominios Gipuzkoa (`uzt`, `erakunde.egoitza`).
- Consulta de expedientes propios en sede requiere certificado digital.
- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
