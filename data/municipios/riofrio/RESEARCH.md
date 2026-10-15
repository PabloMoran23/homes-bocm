# Riofrío — investigación portal ayuntamiento

**Municipio:** Riofrío (Castilla y León, Ávila)  
**Fecha:** 2026-10-15

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.riofrio.es | CMS estático DipuÁvila 2020-0.2b |
| Normas urbanísticas | https://www.riofrio.es/ayuntamiento/normas-urbanisticas/ | Ficha PLAU JCyL |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=195 | Archivo planeamiento (cód. municipio 195, `c_mun` 05195) |
| PLAU print | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlauPrint.do?provincia=05&municipio=195&bInfoPublica=N | Documentos PLAU scrapeables |
| Sede electrónica (espublico gestiona) | https://riofrio.sedelectronica.es/board | Tablón de anuncios (~5 filas) |
| Sede trámites | https://riofrio.sedelectronica.es/dossier/.0 | Catálogo de trámites (requiere sesión/cookies) |
| Sede info | https://riofrio.sedelectronica.es/info | Tablón informativo |

## Cómo se listan expedientes

- **Web DipuÁvila:** sección `/ayuntamiento/normas-urbanisticas/` con enlace a PLAU JCyL (`provincia=05&municipio=195`). Sin PDFs locales de planeamiento en `/docus/`.
- **PLAU CyL:** consulta pública HTML con `doOpen(docId, codigo)`; versión print con título, instrumento y fechas.
- **Tablón sede:** HTML espublico estándar (`preview-document`); anuncios locales (sin expedientes urbanísticos detallados en la muestra).
- **Sin visor municipal** de expedientes ni API JSON de información pública.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- El catálogo de trámites (`/dossier/.0`) incluye solicitudes de licencia urbanística de forma informativa.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Riofrío'` (`c_mun`: `05195`)
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=05195`
  - Resultado: 1 instrumento (SPG — Sin Planeamiento General) con `MultiPolygon`
- **Estrategia:** ingestar metadatos WFS como proyecto (`origen: idecyl_wfs`); polígono SPG no se persiste en `geom_geojson` porque el ámbito IDECyL sobresale ligeramente del límite IGN y el pipeline lo cuarentena (`outside_municipality_scope`). Coordenadas vía centroide municipal + jitter.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia en portal.
  - Polígono WFS disponible en IDECyL pero no importable tal cual al validador H03.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier/.0` responde lento y requiere cookie jar (JSESSIONID tras `/board`).
- `insecure_ssl: true` en adapter por compatibilidad con cadena TLS de sede en algunos entornos.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
