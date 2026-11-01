# Sant Feliu de Llobregat — portal ayuntamiento

## Fuentes

| Ámbito | URL | Formato |
|--------|-----|---------|
| Seu electrònica (base) | https://www.santfeliu.cat | JSF / PrimeFaces (widgetportal2) |
| Planejament en tràmit | https://www.santfeliu.cat/go.faces?xmid=22574 | Listado noticias `newid=` + detalle PDF |
| Planejament vigent | https://www.santfeliu.cat/go.faces?xmid=22575 | Igual |
| Projectes d'obres en tràmit | https://www.santfeliu.cat/go.faces?xmid=24146 | Igual |
| Visor planejament | https://www.santfeliu.cat/go.faces?map_name=planejament&xmid=22198 | OpenLayers + WMS |
| Tauler d'anuncis (e-Tauler) | https://tauler.seu.cat/inici.do?idens=821140003 | SPA React (sin listado HTML) |
| Tràmits urbanisme (hub) | https://www.santfeliu.cat/go.faces?xmid=43497&caseid=sf:9799 | caseid enlazados a llicències |
| AMB expedients GIS | https://geoportal.amb.cat/.../Planejament/Expedients/MapServer/3 | ArcGIS REST → GeoJSON |

### Listado de expedientes / proyectos

- Cada sección de planejament publica filas en `resultList` con enlaces `go.faces?xmid=…&newid=…` y título en `headlineText`.
- La fecha de publicación aparece en la ficha (`span.startDay`, formato `dd/mm/yyyy`).
- Documentos adjuntos en `documentList` (PDFs en `/documents/…`).

### Licencias

- No hay dataset masivo de concesiones en HTML público.
- El **e-Tauler** (Consorci AOC) es el canal oficial de edictos; la UI es SPA sin API documentada en el portal.
- El catálogo de trámites expone fichas de **llicència d'obra major/menor** (`caseid=sf:…`) — se ingestan como trámites informativos (patrón Pozuelo/L'Hospitalet).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - AMB `Planejament/Expedients` layer 3, filtro `CODI_INE='08211'` (Sant Feliu de Llobregat en nomenclatura AMB), `returnGeometry=true`, `outSR=4326`, `f=geojson`.
  - Visor municipal: WMS `http://gis.esantfeliu.org:8080/geoserver/wms` (zonificación vigente; sin campo de enlace a `newid` del portal).
- **Estrategia:** ingestar polígonos AMB como proyectos históricos; intentar cruce por similitud de título con noticias del ayuntamiento (`_amb_hit_for_blob`).
- **Limitaciones:** noticias recientes del ayuntamiento no siempre coinciden con expediente AMB; GeoServer municipal no expone WFS de forma fiable desde el entorno del agente; e-Tauler sin geometría.

## Limitaciones

- Expedientes individuales de obra en tramitación administrativa no son consultables sin identificación (carpeta ciudadana).
- Paginación de noticias acotada (~5–10 ítems por sección en el momento del scrape).
- Sync Supabase requiere `SUPABASE_DB_URL` en CI/local.
