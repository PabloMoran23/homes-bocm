# La Fregeneda — investigación portal ayuntamiento

Municipio fronterizo con Portugal (Arribes del Duero, Salamanca). INE **37132**.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://lafregeneda.com/ | WordPress Divi (turismo, corporación; **sin** urbanismo) |
| Sede electrónica | https://lafregeneda.sedelectronica.es/ | espublico gestiona (eHome/Wicket) |
| Tablón de anuncios | https://lafregeneda.sedelectronica.es/board/ | Tabla Wicket; **vacío** al scrape (2026-09) |
| Catálogo trámites | https://lafregeneda.sedelectronica.es/dossier | 113 trámites; urbanismo/licencias filtrables |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=132 | Archivo planeamiento aprobado |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=132 | IP activa (sin filas al scrape) |
| Visor SIUR | https://idecyl.jcyl.es/siur/index.html?id=37132 | Visor instrumentos CYL |
| Sede legacy | https://fregeneda.sedelectronica.es/ | «Sede indeterminada» (alias inactivo) |

## Expedientes / planeamiento

- **Tablón:** HTML tabla en `/board/`; sin filas publicadas actualmente.
- **Planeamiento histórico:** IDECyL WFS + PlanPublica documentan **Normas Subsidiarias** (NS, BOCL 1998) y **sectores S-1 / S-2**.
- **Listado:** GeoJSON vía WFS (`urbanismo:plau_cyl_*`); metadatos con `n_mun='La Fregeneda'`, `c_mun='37132'`.
- **PlanPublica:** código municipio **132** en provincia Salamanca (37).

## Licencias de obra

- No hay concesiones publicadas en tablón.
- Catálogo sede incluye trámites tipo «Solicitud de Licencia o Autorización Urbanística», «Declaración Responsable…», «Licencia de Ocupación», etc. (páginas informativas, no resoluciones).
- Estrategia adapter: filas `licencias.jsonl` desde catálogo + tablón cuando aparezcan anuncios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `plau_cyl_instrumentos_ambito` (1 NS municipal), `plau_cyl_sectores` (S-1, S-2)
  - Filtro: `CQL_FILTER=n_mun='La Fregeneda'`, `srsName=EPSG:4326`
  - Visor SIUR: enlace documentación NS (`url_doc_info` → PlanPublica cDocId=278431)
- **Estrategia:** ingestar features WFS con `geom_geojson`; enriquecer anuncios futuros por código sector (`S-1`, `S-2`, `Sector N`).
- **Limitaciones:**
  - Tablón sin anuncios → licencias sin coords hasta geocode municipio.
  - Sin visor ArcGIS municipal propio; dependencia IDECyL regional.
  - Web municipal sin PDFs urbanísticos.

## Limitaciones generales

- Municipio pequeño: poca actividad urbanística publicada online.
- `fregeneda.sedelectronica.es` (sin prefijo «la») no resuelve sede activa.
- Dossier sede responde lento (~15 s); requiere sesión cookie (bootstrap vía tablón).
