# Reus — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal (Drupal) | https://www.reus.cat | Planejament, notícies, convocatòries |
| Planejament urbanístic | https://www.reus.cat/serveis/planejament-urbanistic | Enllaços a seu + RPUC |
| Sede electrónica | https://seu.reus.cat/seu/ | Tràmits, urbanisme (publicacions per categoria) |
| Publicacions urbanisme (seu) | `.../urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=1981` (1982, 1983, 1986, 1987) | Llistats d'expedients / documents |
| Tauler electrònic (XALOC) | https://tauler.seu.cat/inici.do?idens=4312330008&idioma=cat | idens Reus |
| Geoportal | https://geoportal.reus.cat/inici/ | Mapia / Giscube, API cerca parcel·les |
| RPUC (PGOU) | https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/267316 | Expedient planejament Reus |

## Listado de expedientes / proyectos

- **Sede Reus:** categories `urbanismeCategoriaPublic` (IDs 1981–1987) amb enllaços `mostrarPublicacion` (HTML). Des de l'entorn cloud de l'agent, `seu.reus.cat` pot **no respondre** (timeout TLS); en local/CI espanyol sol funcionar.
- **Web Drupal:** sitemap (`/sitemap.xml?page=1|2`) amb centenars de `/noticia/` i `/convocatoria/`; el adapter filtra URLs amb termes urbanístics (`modificacio-urban`, `transformacio-urban`, `reurbanitz`, etc.).
- **RPUC:** referència al PGOU vigent (expedient 267316); sense scrape massiu del portal SPA.

## Licencias

- No hi ha dataset obert de llicències concedides (com Madrid SIGMA).
- **Tràmits informatius:** catàleg seu (`carpetaCiutadana/perTemes/1474` arquitectura i urbanisme, tràmit 6654 planejament) + enllaços des de `serveis/tramits-i-llicencies`.
- Tauler `tauler.seu.cat` requereix navegació per edictes; no s'ha automatitzat en aquesta iteració.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** API `mapiareus_search` del geoportal (`?q=<ref>&e=parcella`) retorna `geom` GeoJSON (EPSG:4326) per referència cadastral / `CF****`.
- **Estrategia:** extreure referències de parcela del títol/cos de notícies o documents; consultar API i omplir `geom_geojson` quan hi ha coincidència.
- **Limitaciones:** capes de planejament per expedient no enllaçades públicament al codi d'expedient; `seu.reus.cat` inaccessible des d'alguns egress; sense polígon per la majoria de files (només centroid + jitter via orquestador).

## Limitaciones generales

- Sede `seu.reus.cat`: timeouts des de cloud agents (similar a altres sedes catalanes).
- No re-parse BOCM (municipi sense `boletin_source_id` associat a files locals).
- Sync Supabase: requereix `SUPABASE_DB_URL` a l'entorn d'execució.
