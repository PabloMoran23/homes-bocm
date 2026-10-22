# Molina de Segura — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Portal municipal | https://portal.molinadesegura.es |
| Sede electrónica | https://sedeelectronica.molinadesegura.es |
| Información urbanística (tabla documentos PGMO) | https://sedeelectronica.molinadesegura.es/informacion-urbanistica/ |
| Tablón de edictos (STA) | https://cciudadana.molinadesegura.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON |
| Carpeta ciudadana / catálogo trámites | https://cciudadana.molinadesegura.es/ |
| Trámites y servicios (WP) | https://sedeelectronica.molinadesegura.es/tramitesyservicios/ |
| Área urbanismo / PGMO | https://urbanismo.molinadesegura.es/pgmo/ |
| Transparencia | https://transparencia.molinadesegura.es |

## Proyectos / expedientes

- **Fuente principal:** tabla HTML en *Información urbanística* (WordPress en subdominio `sedeelectronica`). Columnas: tema/materia, denominación (con fecha y código de ámbito), detalle (fase + `EXPTE. YYYY/NNNN`), enlace **DESCARGAR** (PDF/ZIP en `/wp-content/uploads/` o `/download/476/informacion-urbanistica/...`).
- **Secundaria:** tablón STA (`PAGE_CODE=TABLON`) con dataset JavaScript embebido (`dataset_TABLON` / `dataset_PTS2_TABLON`), mismo patrón que otros municipios T-Systems.
- **Complementaria:** `urbanismo.molinadesegura.es/pgmo/` — documentación estática de PGMO, APIs y visor informativo de planos (sin API REST de expedientes).

## Licencias

- No hay listado público de licencias concedidas con dirección/coords.
- **Tablón STA:** edictos de licencia/obra cuando se publican.
- **Trámites informativos** en sede (área 020 urbanismo): licencia obra mayor, comunicación previa, declaración responsable, cédula urbanística, etc. (`/licencia-urbanistica-obra-mayor/`, …).

## Limitaciones

- Dominios `*.molinadesegura.es` pueden bloquear o degradar TLS desde algunos datacenters (handshake timeout); el adapter reintenta vía snapshot `web.archive.org/web/2id_/` solo para HTML de listados.
- PDFs siguen en el mismo host; descarga masiva no es necesaria para metadatos.
- `wp-json` REST devuelve 401 en sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM (accesible): `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs` — capa `plu_ze_37_mun_uso_suelo`, filtro `Municipio='Molina de Segura'`, campo `Ambito` (p. ej. `UAR-M9`, `ZI1-M1`, `SGEL-EVE`).
  - Visor PGMO informativo en `urbanismo.molinadesegura.es` (ArcGIS embebido / planos por referencia catastral) — sin enlace estable expediente→polígono para scraping.
- **Estrategia:** tras parsear título/detalle del expediente, extraer códigos de ámbito (`UAR-*`, `ZI*`, `PER-*`, …) y unir con polígonos WFS; centroide WGS84 en `geom_geojson`.
- **Limitaciones:** un expediente puede abarcar varios documentos sin polígono único; muchos anuncios BORM no incluyen código de ámbito → sin geometría (orquestador: centroide municipio + jitter).
