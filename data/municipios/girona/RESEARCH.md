# Girona — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://web.girona.cat |
| Planejament PGOU vigent | https://web.girona.cat/urbanisme/planejament/pgou |
| Proxy expedientes (portlet) | Mismo URL con `ProxyController_INSTANCE_TFYoJoQx4j8W` + `idCat` / `idReg` |
| Sede electrónica (OpenCMS) | https://seu.girona.cat/portal/girona_es/ |
| Expedientes exposición pública | https://seu.girona.cat/portal/girona_es/expedients_exposicio/ |
| Trámites urbanismo y obras | https://seu.girona.cat/portal/girona_es/tramits/urbanisme/ |
| e-tauler transparencia | https://www.girona.cat/transparencia/cat/etauler.php |
| Clasificación obras | https://web.girona.cat/urbanisme/obres |

## Proyectos / planeamiento

- **CMS:** Liferay en `web.girona.cat`; listados HTML server-side en portlet *Proxy Portlet*.
- **Categorías:** índice PGOU con enlaces `idCat` (PGOU, modificaciones, PPU, PMU, PE, gestión urbanística, etc.).
- **Listado:** tabla `class="taula expedients"` con `fitxaPlanejament('<idReg>')`, año, título y fecha aprobación.
- **Ficha:** `idReg` + `idCat`; campos `planTxt` (nº expediente ajuntament / urbanisme), PDFs y enlace UMAT.
- **Búsqueda:** formulario en portlet (mín. 3 caracteres).

## Licencias de obra

- No hay dataset público de licencias concedidas (coordenadas/fechas).
- **Sede:** índice de *comunicaciones previas* y trámites de obras (`/tramits/urbanisme/` → fichas `e-registre/AaZ/*.html`).
- **Tablón** (`/tauler/`): anuncios generales; sin API JSON como sedes STA.
- El adapter ingiere páginas informativas de trámites (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor UMAT: https://umat.girona.cat/vu/mapa/planejament/ (`identifyURL` → `terra.girona.cat/servergis/.../Planejament/MapServer`)
  - En ficha expediente: enlace `Situació i àmbit` con `?q=<lat> <lon>&zoom=18`
  - ArcGIS REST identify en capa **Qualificació Zones** (id 27) devuelve polígono en EPSG:4326
- **Estrategia:** parsear coordenadas UMAT en ficha → `identify` MapServer → `geom_geojson` Polygon
- **Limitaciones:** no todas las fichas incluyen enlace UMAT; identify devuelve zona de calificación (aproximación al ámbito, no límite legal del expediente); capas no enlazan por código de expediente

## Limitaciones

- Volumen alto de expedientes históricos (~260+ filas en categorías PGOU); geometría solo en subconjunto reciente (`max_geometry_details`).
- Expedientes en exposición en sede sin listado automatizable en HTML estático (página vacía en crawl).
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
