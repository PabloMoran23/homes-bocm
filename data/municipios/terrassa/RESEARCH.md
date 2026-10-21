# Terrassa — investigación portal ayuntamiento

## Fuentes

| Recurso | URL | Uso |
|---------|-----|-----|
| Sede electrónica (Administració Oberta) | https://aoberta.terrassa.cat | Trámites urbanismo, oficina Serveis d'Urbanisme |
| Sede principal (Cloudflare) | https://seuelectronica.terrassa.cat | Enlaces a fichas de planeamiento; bloqueado en CI |
| Carpeta ciudadana (Ariadna STA) | https://ariadnaseu.terrassa.cat/sta/CarpetaPublic/ | Consulta estado expedientes (login / interés legítimo) |
| e-map / visor POUM | https://emap.terrassa.cat/mapGIS/?modul=POUM | Visor planeamiento urbanístico |
| ArcGIS MapServer POUM | http://emap.terrassa.cat/arcgis/rest/services/Territori/iurb_terrassa/MapServer | Datos estructurados + geometría |
| Open Data | https://opendata.terrassa.cat | Catálogo CKAN (sin dataset de licencias históricas localizado) |
| GeoPortal IDE | https://emap.terrassa.cat/geoPortal/ | Metadatos servicios SIG municipales |

## Proyectos / planeamiento

- **Listado machine-readable:** capa **4** «Sectors de planejament» del servicio `Territori/iurb_terrassa` (POUM 2021, ~975 polígonos).
- **Campos útiles:** `idpoli`, `denominacio`, `sexpe`, `estat`, `tipop`, `ntinstr`, `Data_publicacio`, `urlseut`, `urlgenca`.
- **Paginación:** `resultOffset` / `resultRecordCount` (máx. 500–1000); geometría ESRI `rings` con `outSR=4326`.
- **Páginas sede:** `urlseut` apunta a rutas en `seuelectronica.terrassa.cat/web/seu/...` (Cloudflare).
- **Generalitat:** `urlgenca` enlaza RPUC (`dtes.gencat.cat`) para algunos instrumentos.

## Licencias de obra

- **No hay tablón público** con listado histórico de licencias concedidas (como Móstoles/Getafe).
- Trámites publicados en **Serveis d'Urbanisme** (`infoEntitatTramits.jsp?id=1899`): comunicación previa de obras, informes de estado de licencia, certificados, etc.
- Consulta de expedientes vía **Carpeta ciudadana** o trámite de informe (pago, interés legítimo).

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** ArcGIS MapServer `Territori/iurb_terrassa`, capa 4 «Sectors de planejament».
- **Estrategia:** query paginada `returnGeometry=true`, `outSR=4326`, conversión `rings` → GeoJSON Polygon/MultiPolygon; centroide en `lat`/`lon`.
- **Limitaciones:** geometría a nivel **sector/instrumento POUM**, no parcela de cada licencia individual; licencias sin GIS público enlazable; `seuelectronica.terrassa.cat` con Cloudflare; `www.terrassa.cat` 403 en algunos entornos.

## Limitaciones generales

- SSL/HTTP: el MapServer responde de forma fiable por **HTTP** en `emap.terrassa.cat`.
- Sin re-parse BOCM (municipio sin boletín asociado en cola).
