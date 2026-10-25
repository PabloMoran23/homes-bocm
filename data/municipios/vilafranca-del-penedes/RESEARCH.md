# Vilafranca del Penedès — investigación portal

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Sede / trámites STA | https://tramits.vilafranca.cat | Accesible desde cloud; catálogo `PAGE_CODE=CATALOGO`, dataset `CATSERV` |
| Seu electrónica | https://seu.vilafranca.cat | Tauler d'anuncis; **403 Cloudflare** desde agente |
| Urbanisme | https://urbanisme.vilafranca.cat | POUM, planejament derivat, visor; **403 Cloudflare** desde agente |
| Geoportal | https://geoportal.vilafranca.cat/geoportal/ | **403 Cloudflare** desde agente |
| Anuncis oficials (eixdiari) | https://www.eixdiari.cat/serveis/anuncis-oficials/vilafranca-del-penedes/ | Listado HTML con enlaces `/edicte/{id}.html` |
| CIDO (DIBA) | https://cido.diba.cat/normativa_local/6701777/planejament-urbanistic-ajuntament-de-vilafranca-del-penedes | Histórico normativa (referencia) |

## Expedientes / planeamiento

- **Catálogo STA:** 286 trámites en `dataset_CATSERV`; familia `Urbanisme` (~30) incluye llicències d'obres, certificats, plans parcials/PMU, etc. Detalle: `DETALLE={dboid}&PAGE_CODE=CATALOGO`.
- **Tablón STA:** `PTS_TABLON`, `URB_TABLON`, etc. → página no encontrada en esta sede (sin dataset embebido).
- **Tauler d'anuncis (seu):** publicaciones desde abril (no scrapeable por CF).
- **eixdiari:** anuncios de exposición pública recientes (habitatge, demanial, PEEU, etc.).
- **Planejament derivat (web):** listado estático de PAU, PP y SUD en urbanisme.vilafranca.cat (documentado; acceso directo bloqueado en cloud).

## Licencias

- No hay listado público de concesiones (solo trámites del catálogo STA y páginas informativas en urbanisme).
- Trámites relevantes: `Llicències d'obres majors/menors`, `Comunicació primera ocupació`, `Obres menors en règim d'assabentat`, `Llicència de parcel·lació`, etc.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Generalitat: `https://sig.gencat.cat/ows/PLANEJAMENT/wfs` capa `PLANEJAMENT:MUC_PDERIVAT_SECTOR`, filtro `CODI_INE='08305'` (15 sectores con polígono EPSG:4326).
  - Geoportal municipal / visor urbanístico (ArcGIS-like en portal propio) — no accesible desde cloud (403).
- **Estrategia:** ingestar sectores MUC como proyectos con `geom_geojson`; intentar cruce por tokens PAU/SUD en anuncios eixdiari.
- **Limitaciones:** User-Agent estricto en WFS gencat (requiere UA navegador). Portal ayuntamiento y geoportal detrás de Cloudflare. Sin join expediente↔parcela en tablón público.

## Limitaciones generales

- `www.vilafranca.cat` y subdominios urbanisme/seu/geoportal bloqueados por Cloudflare en el entorno del agente.
- `tramits.vilafranca.cat` y `eixdiari.cat` funcionan con urllib.
- Sin histórico de licencias concedidas en abierto.
